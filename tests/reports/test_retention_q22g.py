"""Sprint Q.22.G — report retention cleanup + `/v1/reports/retention`.

``cleanup_expired_runs`` prunes ``ReportRun`` rows past their owning
schedule's ``retention_days`` (ad-hoc runs use a 90-day default), and
audits each deletion. Tests cover the age boundary, per-schedule
retention, the audit trail, and the two endpoints.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.reports.api import router as reports_router
from src.reports.cleanup import cleanup_expired_runs
from src.reports.models import ReportRun, ReportSchedule
from src.shared.database import get_session
from tests.reports.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("11111111-1111-1111-1111-111111111111")


def _headers():
    return {"X-Tenant-Id": str(TENANT), "X-User-Id": str(USER)}


def _run(*, days_old: int, schedule_id=None):
    run = ReportRun(
        tenant_id=TENANT,
        schedule_id=schedule_id,
        report_type="cogs",
        status="generated",
        generated_at=datetime.utcnow() - timedelta(days=days_old),
        delivered_to=[],
        payload={},
    )
    run.id = uuid4()
    return run


def _schedule(*, retention_days: int):
    sched = ReportSchedule(
        tenant_id=TENANT,
        report_type="cogs",
        cron="0 6 * * 1",
        recipients=[],
        format="csv",
        enabled=True,
        retention_days=retention_days,
    )
    sched.id = uuid4()
    return sched


async def test_cleanup_deletes_only_expired_adhoc_runs():
    session = FakeSession()
    fresh = _run(days_old=10)      # within default 90d
    stale = _run(days_old=120)     # past default 90d
    session.runs = [fresh, stale]

    deleted = await cleanup_expired_runs(session, TENANT)

    assert deleted == 1
    assert session.runs == [fresh]
    assert any(a.action == "DELETE" and a.entity_type == "report_run" for a in session.audit)
    assert session.commits == 1


async def test_cleanup_uses_schedule_retention():
    session = FakeSession()
    sched = _schedule(retention_days=7)   # tight retention
    session.schedules = [sched]
    # 30 days old: kept under the 90d default, but expired under the
    # schedule's 7-day retention.
    run = _run(days_old=30, schedule_id=sched.id)
    session.runs = [run]

    deleted = await cleanup_expired_runs(session, TENANT)

    assert deleted == 1
    assert session.runs == []


async def test_cleanup_noop_when_all_fresh():
    session = FakeSession()
    session.runs = [_run(days_old=1), _run(days_old=5)]

    deleted = await cleanup_expired_runs(session, TENANT)

    assert deleted == 0
    assert len(session.runs) == 2
    assert session.commits == 0  # nothing to commit


def _build_client(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_session] = _fake_session
    return TestClient(app)


def test_retention_post_triggers_cleanup():
    session = FakeSession()
    session.runs = [_run(days_old=200), _run(days_old=1)]
    resp = _build_client(session).post("/v1/reports/retention", headers=_headers())

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1


def test_retention_get_returns_policy():
    session = FakeSession()
    session.schedules = [_schedule(retention_days=30)]
    session.runs = [_run(days_old=1), _run(days_old=2)]
    resp = _build_client(session).get("/v1/reports/retention", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["default_retention_days"] == 90
    assert body["total_runs"] == 2
    assert len(body["schedules"]) == 1
    assert body["schedules"][0]["retention_days"] == 30
