"""Sprint Q.22.D — `POST /v1/reports/schedule` persistence.

Before Q.22.D the endpoint logged + echoed ``status="stubbed"`` with
no persistence. Now it writes a ``reports.report_schedule`` row and an
accompanying ``core.audit_log`` INSERT in the same transaction.

Covered:
* POST → 201, row persisted, audit_log INSERT written, committed
* the response carries the generated id + the stored fields
* GET → lists the tenant's schedules
* an invalid template_id is rejected by the Pydantic Literal (422)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.reports.api import router
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


def test_schedule_persists_row_and_writes_audit():
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/schedule",
        headers=_headers(),
        json={
            "template_id": "payroll",
            "cron": "0 8 * * MON",
            "enabled": True,
            "retention_days": 120,
        },
    )

    assert resp.status_code == 201
    # Row persisted.
    assert len(session.schedules) == 1
    schedule = session.schedules[0]
    assert schedule.report_type == "payroll"
    assert schedule.cron == "0 8 * * MON"
    assert schedule.retention_days == 120
    assert schedule.tenant_id == TENANT
    # Audit trail intact — one INSERT row, committed.
    assert len(session.audit) == 1
    assert session.audit[0].action == "INSERT"
    assert session.audit[0].entity_type == "report_schedule"
    assert session.commits == 1


def test_schedule_response_carries_generated_id_and_fields():
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/schedule",
        headers=_headers(),
        json={"template_id": "cogs", "cron": "0 6 1 * *"},
    )

    assert resp.status_code == 201
    body = resp.json()
    # id is a real UUID, matches the persisted row.
    assert UUID(body["id"]) == session.schedules[0].id
    assert body["template_id"] == "cogs"
    assert body["cron"] == "0 6 1 * *"
    assert body["retention_days"] == 90  # default
    assert body["format"] == "csv"  # default


def test_list_schedules_returns_tenant_schedules():
    session = FakeSession()
    client = TestClient(_build_app(session))

    client.post(
        "/v1/reports/schedule",
        headers=_headers(),
        json={"template_id": "inventario", "cron": "0 7 * * *"},
    )
    resp = client.get("/v1/reports/schedule", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["template_id"] == "inventario"


def test_schedule_rejects_unknown_template():
    """template_id outside the closed Literal whitelist → 422."""
    session = FakeSession()
    client = TestClient(_build_app(session))

    resp = client.post(
        "/v1/reports/schedule",
        headers=_headers(),
        json={"template_id": "not_a_template", "cron": "0 8 * * *"},
    )

    assert resp.status_code == 422
    assert session.schedules == []
