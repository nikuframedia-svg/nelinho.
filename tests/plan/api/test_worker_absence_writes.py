"""Q.174.F4 — tests dos endpoints de ausências de operadores.

Endpoints:
  POST   /v1/plan/absences              → cria override (INSERT + audit + evento)
  DELETE /v1/plan/absences/{id}         → remove (DELETE + audit, idempotente)
  GET    /v1/plan/absences              → lista

Mirror de test_q153c_plan_exclusion.py: FastAPI TestClient + FakeSession.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.audit import AuditLog
from src.plan.api.worker_absence_writes import (
    _require_schedule_write,
    router as absence_router,
)
from src.plan.models.worker_absence import WorkerAbsence
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_USER = "operador_teste"
_HEADERS = {"X-Tenant-Id": _TENANT, "X-User-Id": _USER}


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(absence_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: _USER
    app.dependency_overrides[_require_schedule_write] = lambda: None
    return TestClient(app, raise_server_exceptions=True)


def _added(session: FakeSession, cls: type) -> list:
    return [o for o in session.added if isinstance(o, cls)]


@pytest.mark.asyncio
async def test_create_absence_add_happy():
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.post(
        "/v1/plan/absences",
        json={
            "employee_code": "24589",
            "date_start": "2026-06-15",
            "date_end": "2026-06-20",
            "kind": "doença",
            "reason": "ligou de manhã",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["employee_code"] == "24589"
    assert body["mode"] == "add"
    rows = _added(session, WorkerAbsence)
    assert len(rows) == 1 and rows[0].created_by == _USER
    audits = _added(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].entity_type == "worker_absence"
    assert audits[0].action == "INSERT"


@pytest.mark.asyncio
async def test_create_absence_ignore_erp_exige_movent_id():
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.post(
        "/v1/plan/absences",
        json={
            "employee_code": "24589",
            "date_start": "2026-06-15",
            "date_end": "2026-06-20",
            "mode": "ignore_erp",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422  # erp_movent_id em falta


@pytest.mark.asyncio
async def test_create_absence_datas_invertidas_422():
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.post(
        "/v1/plan/absences",
        json={
            "employee_code": "24589",
            "date_start": "2026-06-20",
            "date_end": "2026-06-15",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_absence_idempotente():
    session = FakeSession()
    session.queue_scalar(None)  # SELECT → não existe
    client = _minimal_app(session)
    resp = client.delete(f"/v1/plan/absences/{uuid4()}", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is False


@pytest.mark.asyncio
async def test_delete_absence_remove_e_audita():
    session = FakeSession()
    existing = SimpleNamespace(
        id=uuid4(), tenant_id=TEST_TENANT_ID, employee_code="24589",
        date_start=date(2026, 6, 15), date_end=date(2026, 6, 20),
        kind="doença", mode="add", erp_movent_id=None, reason=None,
        created_by="x", created_at=datetime.now(timezone.utc),
    )
    session.queue_scalar(existing)
    client = _minimal_app(session)
    resp = client.delete(f"/v1/plan/absences/{existing.id}", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    audits = _added(session, AuditLog)
    assert len(audits) == 1 and audits[0].action == "DELETE"
