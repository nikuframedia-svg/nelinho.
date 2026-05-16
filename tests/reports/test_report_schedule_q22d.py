"""Sprint Q.22.D — `/v1/reports/schedule` CRUD + audit trail.

Covers the lifecycle of a ``ReportSchedule`` plus the invariant-7
guarantee: every mutating operation writes a ``core.audit_log`` row in
the same transaction.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.reports.api import router as reports_router
from src.shared.database import get_session
from tests.reports.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")
USER = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_session] = _fake_session
    return TestClient(app)


def _headers():
    return {"X-Tenant-Id": str(TENANT), "X-User-Id": str(USER)}


def _payload(**overrides):
    body = {
        "report_type": "payroll",
        "cron": "0 6 * * 1",
        "recipients": ["luis@nikufra.ai"],
        "format": "csv",
        "enabled": True,
        "retention_days": 60,
    }
    body.update(overrides)
    return body


def test_create_schedule_persists_and_audits(client, session):
    resp = client.post("/v1/reports/schedule", json=_payload(), headers=_headers())

    assert resp.status_code == 201
    body = resp.json()
    assert body["report_type"] == "payroll"
    assert body["retention_days"] == 60
    assert body["recipients"] == ["luis@nikufra.ai"]
    assert len(session.schedules) == 1
    # Invariant 7: one audit row, same transaction.
    assert len(session.audit) == 1
    assert session.audit[0].action == "INSERT"
    assert session.audit[0].entity_type == "report_schedule"
    assert session.commits == 1


def test_create_rejects_unknown_report_type(client):
    resp = client.post(
        "/v1/reports/schedule",
        json=_payload(report_type="not_a_real_type"),
        headers=_headers(),
    )
    assert resp.status_code == 422  # Literal enforcement


def test_list_and_get_schedule(client, session):
    created = client.post("/v1/reports/schedule", json=_payload(), headers=_headers()).json()

    listed = client.get("/v1/reports/schedule", headers=_headers())
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/v1/reports/schedule/{created['id']}", headers=_headers())
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_update_schedule_audits_change(client, session):
    created = client.post("/v1/reports/schedule", json=_payload(), headers=_headers()).json()

    resp = client.patch(
        f"/v1/reports/schedule/{created['id']}",
        json={"enabled": False, "retention_days": 30},
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["retention_days"] == 30
    update_rows = [a for a in session.audit if a.action == "UPDATE"]
    assert len(update_rows) == 1
    assert update_rows[0].old_values["enabled"] is True


def test_update_with_no_fields_is_400(client):
    created = client.post("/v1/reports/schedule", json=_payload(), headers=_headers()).json()
    resp = client.patch(
        f"/v1/reports/schedule/{created['id']}", json={}, headers=_headers()
    )
    assert resp.status_code == 400


def test_delete_schedule_audits(client, session):
    created = client.post("/v1/reports/schedule", json=_payload(), headers=_headers()).json()

    resp = client.delete(f"/v1/reports/schedule/{created['id']}", headers=_headers())
    assert resp.status_code == 204
    assert session.schedules == []
    assert any(a.action == "DELETE" for a in session.audit)


def test_get_missing_schedule_is_404(client):
    resp = client.get(
        "/v1/reports/schedule/22222222-2222-2222-2222-222222222222",
        headers=_headers(),
    )
    assert resp.status_code == 404
