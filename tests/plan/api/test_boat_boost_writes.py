"""Q.116.D — tests para PATCH /v1/plan/boat-boost/{boat_id}.

Mirror de test_order_writes.py (Q.116.C):
  1. INSERT happy path — sem row existente
  2. UPDATE happy path — com row existente; old_values populado
  3. Boost > 100 -> 422 (Pydantic)
  4. Boost < 0 -> 422 (Pydantic)

Strategy: FastAPI TestClient + FakeSession (tests/conftest.py). Override
require_tenant_header + require_user_header + get_session + RBAC dep.
Nao toca DB real.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.models.audit import AuditLog
from src.plan.api.boat_boost_writes import (
    _require_schedule_write,
    router as boat_boost_router,
)
from src.plan.models.boat_boost import BoatBoost
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_USER = "operador_teste"
_HEADERS = {"X-Tenant-Id": _TENANT, "X-User-Id": _USER}


# ─── App factory ─────────────────────────────────────────────────────────────


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(boat_boost_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: _USER
    # RBAC bypass — testes nao exercitam a politica RBAC, so o handler.
    app.dependency_overrides[_require_schedule_write] = lambda: None
    return TestClient(app, raise_server_exceptions=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _existing_boost(boat_id: str = "B-12345", boost: int = 50, reason: str = "antigo") -> SimpleNamespace:
    """Stand-in para um BoatBoost ja persistido — mutavel como o ORM real."""
    return SimpleNamespace(
        tenant_id=TEST_TENANT_ID,
        boat_id=boat_id,
        boost=boost,
        reason=reason,
        updated_by="utilizador_antigo",
        updated_at=datetime.now(timezone.utc),
    )


def _added_of_type(session: FakeSession, cls: type) -> list:
    return [o for o in session.added if isinstance(o, cls)]


# ─── 1. INSERT happy path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_boat_boost_insert_happy():
    """Sem row existente -> INSERT: flush + audit chamados, old_values=None."""
    session = FakeSession()
    session.queue_scalar(None)  # SELECT existing BoatBoost -> None

    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/boat-boost/B-99999",
        json={"boost": 75, "reason": "barco prioritario — entrega VIP"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boat_id"] == "B-99999"
    assert body["boost"] == 75
    assert body["reason"] == "barco prioritario — entrega VIP"
    assert body["updated_by"] == _USER

    # Flush ocorreu uma vez (do handler — audit_service nao chama flush).
    assert session.flush_calls == 1

    # BoatBoost row foi adicionada.
    added_boosts = _added_of_type(session, BoatBoost)
    assert len(added_boosts) == 1
    assert added_boosts[0].boost == 75
    assert added_boosts[0].boat_id == "B-99999"
    assert added_boosts[0].tenant_id == TEST_TENANT_ID

    # Audit row INSERT criada na mesma session.
    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "INSERT"
    assert audits[0].entity_type == "boat_boost"
    assert audits[0].old_values is None
    assert audits[0].new_values == {
        "boost": 75,
        "reason": "barco prioritario — entrega VIP",
    }
    assert audits[0].reason == "upsert_boat_boost"


# ─── 2. UPDATE happy path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_boat_boost_update_old_values():
    """Row existente -> UPDATE: mutate in-place, audit com old_values populado."""
    session = FakeSession()
    existing = _existing_boost(boat_id="B-77777", boost=30, reason="razao antiga")
    session.queue_scalar(existing)  # SELECT existing BoatBoost -> existing

    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/boat-boost/B-77777",
        json={"boost": 90, "reason": "subiu para urgencia"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boat_id"] == "B-77777"
    assert body["boost"] == 90
    assert body["reason"] == "subiu para urgencia"
    assert body["updated_by"] == _USER

    # Existing row foi mutado em vez de criada de novo.
    assert existing.boost == 90
    assert existing.reason == "subiu para urgencia"
    assert existing.updated_by == _USER

    # Nada de NOVO BoatBoost adicionado a sessao (so o audit).
    added_boosts = _added_of_type(session, BoatBoost)
    assert len(added_boosts) == 0

    # Audit UPDATE com old_values do estado anterior.
    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "UPDATE"
    assert audits[0].old_values == {"boost": 30, "reason": "razao antiga"}
    assert audits[0].new_values == {"boost": 90, "reason": "subiu para urgencia"}
    assert audits[0].reason == "upsert_boat_boost"


# ─── 3. Boost > 100 -> 422 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_boat_boost_above_100_returns_422():
    """Boost > 100 -> Pydantic 422 antes de tocar no handler."""
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/boat-boost/B-12345",
        json={"boost": 150},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    # Nem audit nem boost adicionados (request rejeitado antes do handler).
    assert _added_of_type(session, AuditLog) == []
    assert _added_of_type(session, BoatBoost) == []


# ─── 4. Boost < 0 -> 422 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_boat_boost_negative_returns_422():
    """Boost < 0 -> Pydantic 422 antes de tocar no handler."""
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/boat-boost/B-12345",
        json={"boost": -5},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert _added_of_type(session, AuditLog) == []
    assert _added_of_type(session, BoatBoost) == []
