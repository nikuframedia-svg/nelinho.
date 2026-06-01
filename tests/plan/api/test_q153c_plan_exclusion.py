"""Q.153.C1 — tests para exclusão reversível de barco do plano.

Endpoints:
  POST   /v1/plan/boats/{order_id}/exclude  → exclui/adia (INSERT/UPDATE + audit)
  DELETE /v1/plan/boats/{order_id}/exclude  → repõe (DELETE + audit, idempotente)
  GET    /v1/plan/boats/excluded            → lista

Mirror de test_boat_boost_writes.py: FastAPI TestClient + FakeSession.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.audit import AuditLog
from src.plan.api.plan_exclusion_writes import (
    _require_schedule_write,
    router as exclusion_router,
)
from src.plan.models.plan_exclusion import PlanExclusion
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_USER = "operador_teste"
_HEADERS = {"X-Tenant-Id": _TENANT, "X-User-Id": _USER}


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(exclusion_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: _USER
    app.dependency_overrides[_require_schedule_write] = lambda: None
    return TestClient(app, raise_server_exceptions=True)


def _existing(order_id="OF-123", reason="em espera") -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=TEST_TENANT_ID, order_id=order_id, reason=reason,
        excluded_by="alguem", excluded_at=datetime.now(timezone.utc),
    )


def _added(session: FakeSession, cls: type) -> list:
    return [o for o in session.added if isinstance(o, cls)]


@pytest.mark.asyncio
async def test_exclude_boat_insert_happy():
    session = FakeSession()
    session.queue_scalar(None)  # SELECT existing → None

    client = _minimal_app(session)
    resp = client.post(
        "/v1/plan/boats/OF-999/exclude",
        json={"reason": "casco em espera de decisão"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_id"] == "OF-999"
    assert body["reason"] == "casco em espera de decisão"
    assert body["excluded_by"] == _USER

    added = _added(session, PlanExclusion)
    assert len(added) == 1 and added[0].order_id == "OF-999"
    audits = _added(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "INSERT"
    assert audits[0].entity_type == "plan_exclusion"
    assert audits[0].new_values == {"excluded": True, "reason": "casco em espera de decisão"}


@pytest.mark.asyncio
async def test_exclude_boat_update_when_already_excluded():
    session = FakeSession()
    existing = _existing(order_id="OF-77", reason="razão antiga")
    session.queue_scalar(existing)

    client = _minimal_app(session)
    resp = client.post(
        "/v1/plan/boats/OF-77/exclude",
        json={"reason": "novo motivo"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    assert existing.reason == "novo motivo"          # mutate in-place
    assert _added(session, PlanExclusion) == []      # sem nova row
    audits = _added(session, AuditLog)
    assert audits[0].action == "UPDATE"
    assert audits[0].old_values == {"excluded": True, "reason": "razão antiga"}


@pytest.mark.asyncio
async def test_reinclude_boat_deletes_and_audits():
    session = FakeSession()
    session.queue_scalar(_existing(order_id="OF-55"))

    client = _minimal_app(session)
    resp = client.delete("/v1/plan/boats/OF-55/exclude", headers=_HEADERS)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"order_id": "OF-55", "reincluded": True}
    audits = _added(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "DELETE"
    assert audits[0].new_values == {"excluded": False}


@pytest.mark.asyncio
async def test_reinclude_when_not_excluded_is_idempotent():
    session = FakeSession()
    session.queue_scalar(None)  # não existe

    client = _minimal_app(session)
    resp = client.delete("/v1/plan/boats/OF-404/exclude", headers=_HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {"order_id": "OF-404", "reincluded": False}
    assert _added(session, AuditLog) == []  # nada a auditar


@pytest.mark.asyncio
async def test_list_excluded_boats():
    session = FakeSession()
    session.queue_scalars([_existing("OF-1", "a"), _existing("OF-2", "b")])

    client = _minimal_app(session)
    resp = client.get("/v1/plan/boats/excluded", headers=_HEADERS)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {b["order_id"] for b in body} == {"OF-1", "OF-2"}
