"""Sprint Q.22.G — retention cleanup + `POST /v1/reports/retention`.

Before Q.22.G the endpoint logged + echoed ``status="stubbed"``. Now it
updates the schedules' ``retention_days`` and runs
:func:`cleanup_expired_runs`, which prunes ``report_run`` rows past
their retention window and audits every delete.

Covered:
* cleanup deletes only runs older than the retention window
* ad-hoc runs (no schedule) use the default retention
* every delete writes a ``core.audit_log`` DELETE row
* the endpoint updates schedule retention + reports counts
* an unknown template_id is rejected (422)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.reports.api import router
from src.reports.cleanup import cleanup_expired_runs
from src.reports.models import ReportRun, ReportSchedule
from src.shared.database import get_session
from tests.reports.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _build_app(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers():
    return {"X-Tenant-Id": str(TENANT)}


def _run(*, schedule_id=None, days_ago=0, report_type="cogs"):
    r = ReportRun(
        tenant_id=TENANT,
        schedule_id=schedule_id,
        report_type=report_type,
        status="generated",
        generated_at=datetime.utcnow() - timedelta(days=days_ago),
        delivered_to=[],
        payload={},
    )
    r.id = uuid4()
    return r


def _schedule(*, retention_days=90, report_type="cogs"):
    s = ReportSchedule(
        tenant_id=TENANT,
        report_type=report_type,
        cron="0 8 * * *",
        recipients=[],
        format="csv",
        enabled=True,
        retention_days=retention_days,
    )
    s.id = uuid4()
    return s


# --- cleanup_expired_runs unit ---------------------------------------------


async def test_cleanup_deletes_only_runs_past_retention():
    session = FakeSession()
    fresh = _run(days_ago=10)
    stale = _run(days_ago=200)
    session.runs = [fresh, stale]

    deleted = await cleanup_expired_runs(session, TENANT, default_retention_days=90)

    assert deleted == 1
    assert fresh in session.runs
    assert stale not in session.runs


async def test_cleanup_uses_schedule_retention_when_run_has_schedule():
    """A run owned by a 30-day schedule expires at 30 days, not the default."""
    session = FakeSession()
    sched = _schedule(retention_days=30)
    session.schedules = [sched]
    # 45 days old — fresh under the 90d default, stale under the 30d schedule.
    owned_run = _run(schedule_id=sched.id, days_ago=45)
    session.runs = [owned_run]

    deleted = await cleanup_expired_runs(session, TENANT, default_retention_days=90)

    assert deleted == 1
    assert owned_run not in session.runs


async def test_cleanup_writes_audit_delete_per_run():
    session = FakeSession()
    session.runs = [_run(days_ago=300), _run(days_ago=300)]

    deleted = await cleanup_expired_runs(session, TENANT, default_retention_days=90)

    assert deleted == 2
    # Audit trail intact — one DELETE row per deleted run.
    assert len(session.audit) == 2
    assert all(a.action == "DELETE" for a in session.audit)
    assert all(a.entity_type == "report_run" for a in session.audit)


async def test_cleanup_no_expired_runs_returns_zero():
    session = FakeSession()
    session.runs = [_run(days_ago=5)]

    deleted = await cleanup_expired_runs(session, TENANT, default_retention_days=90)

    assert deleted == 0
    assert len(session.audit) == 0


# --- POST /v1/reports/retention endpoint -----------------------------------


def test_retention_endpoint_updates_schedule_and_runs_cleanup():
    session = FakeSession()
    session.schedules = [_schedule(retention_days=365, report_type="cogs")]
    session.runs = [_run(days_ago=200, report_type="cogs")]
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/retention",
        headers=_headers(),
        json={"template_id": "cogs", "retention_days": 30},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["retention_days"] == 30
    assert body["schedules_updated"] == 1
    # 200-day-old run is now past the new 30d window → deleted.
    assert body["runs_deleted"] == 1
    # Schedule retention was actually updated + audited.
    assert session.schedules[0].retention_days == 30
    assert any(a.action == "UPDATE" for a in session.audit)


def test_retention_endpoint_can_skip_cleanup():
    session = FakeSession()
    session.schedules = [_schedule(report_type="payroll")]
    session.runs = [_run(days_ago=999, report_type="payroll")]
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/retention",
        headers=_headers(),
        json={"template_id": "payroll", "retention_days": 30, "run_cleanup": False},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["runs_deleted"] == 0  # cleanup skipped
    assert len(session.runs) == 1  # run untouched


def test_retention_endpoint_rejects_unknown_template():
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/retention",
        headers=_headers(),
        json={"template_id": "not_a_template", "retention_days": 30},
    )

    assert resp.status_code == 422
