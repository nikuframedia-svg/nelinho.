"""Q.116.C — tests for PATCH /v1/plan/order-boost + /v1/plan/work-orders/.../transport-date.

Cobertura:
  1. INSERT happy path (sem row existente) — boost
  2. UPDATE happy path (com row existente) — boost; old_values populado
  3. Boost > 100 → 422 Pydantic
  4. Boost < 0 → 422 Pydantic
  5. INSERT happy path — transport-date
  6. transport_date=None (clear override) com row existente → UPDATE com NULL

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
from src.plan.api.order_writes import _require_schedule_write, router as writes_router
from src.plan.models.order_boost import OrderBoost
from src.plan.models.work_order_override import WorkOrderOverride
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.database import get_session
from tests.conftest import FakeSession, TEST_TENANT_ID

_TENANT = str(TEST_TENANT_ID)
_USER = "operador_teste"
_HEADERS = {"X-Tenant-Id": _TENANT, "X-User-Id": _USER}


# ─── App factory ─────────────────────────────────────────────────────────────


def _minimal_app(session: FakeSession) -> TestClient:
    app = FastAPI()
    app.include_router(writes_router)

    async def _s():
        yield session

    app.dependency_overrides[get_session] = _s
    app.dependency_overrides[require_tenant_header] = lambda: TEST_TENANT_ID
    app.dependency_overrides[require_user_header] = lambda: _USER
    # RBAC bypass — testes nao exercitam a politica RBAC, so o handler.
    app.dependency_overrides[_require_schedule_write] = lambda: None
    return TestClient(app, raise_server_exceptions=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _existing_boost(work_order_id: int, boost: int = 50, reason: str = "antigo") -> SimpleNamespace:
    """Stand-in para um OrderBoost ja persistido — mutavel como o ORM real."""
    return SimpleNamespace(
        work_order_id=work_order_id,
        tenant_id=TEST_TENANT_ID,
        boost=boost,
        reason=reason,
        updated_by="utilizador_antigo",
        updated_at=datetime.now(timezone.utc),
    )


def _existing_override(
    work_order_id: int,
    transport_date_override: datetime | None = None,
    reason: str = "antigo",
) -> SimpleNamespace:
    return SimpleNamespace(
        work_order_id=work_order_id,
        tenant_id=TEST_TENANT_ID,
        transport_date_override=transport_date_override,
        reason=reason,
        updated_by="utilizador_antigo",
        updated_at=datetime.now(timezone.utc),
    )


def _added_of_type(session: FakeSession, cls: type) -> list:
    return [o for o in session.added if isinstance(o, cls)]


# ─── 1. INSERT happy path — boost ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_order_boost_insert_happy_path():
    """Sem row existente → INSERT: flush + audit chamados, old_values=None."""
    session = FakeSession()
    session.queue_scalar(None)  # SELECT existing OrderBoost → None

    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/order-boost/1001",
        json={"boost": 75, "reason": "encomenda urgente — cliente VIP"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["work_order_id"] == 1001
    assert body["boost"] == 75
    assert body["reason"] == "encomenda urgente — cliente VIP"
    assert body["updated_by"] == _USER

    # Flush ocorreu uma vez (do handler — audit_service nao chama flush).
    assert session.flush_calls == 1

    # OrderBoost row foi adicionada.
    added_boosts = _added_of_type(session, OrderBoost)
    assert len(added_boosts) == 1
    assert added_boosts[0].boost == 75
    assert added_boosts[0].work_order_id == 1001
    assert added_boosts[0].tenant_id == TEST_TENANT_ID

    # Audit row INSERT criada na mesma session.
    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "INSERT"
    assert audits[0].entity_type == "order_boost"
    assert audits[0].old_values is None
    assert audits[0].new_values == {"boost": 75, "reason": "encomenda urgente — cliente VIP"}
    assert audits[0].reason == "upsert_order_boost"


# ─── 2. UPDATE happy path — boost ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_order_boost_update_populates_old_values():
    """Row existente → UPDATE: mutate in-place, audit com old_values populado."""
    session = FakeSession()
    existing = _existing_boost(work_order_id=2002, boost=30, reason="razao antiga")
    session.queue_scalar(existing)  # SELECT existing OrderBoost → existing

    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/order-boost/2002",
        json={"boost": 90, "reason": "nova razao economica"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boost"] == 90
    assert body["reason"] == "nova razao economica"
    assert body["updated_by"] == _USER

    # Existing row foi mutado em vez de criada de novo.
    assert existing.boost == 90
    assert existing.reason == "nova razao economica"
    assert existing.updated_by == _USER

    # Nada de NOVO adicionado a sessao (so o audit).
    added_boosts = _added_of_type(session, OrderBoost)
    assert len(added_boosts) == 0

    # Audit UPDATE com old_values do estado anterior.
    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "UPDATE"
    assert audits[0].old_values == {"boost": 30, "reason": "razao antiga"}
    assert audits[0].new_values == {"boost": 90, "reason": "nova razao economica"}


# ─── 3. Boost > 100 → 422 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_order_boost_above_100_returns_422():
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/order-boost/3003",
        json={"boost": 150},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    # Nem audit nem boost adicionados (request rejeitado antes do handler).
    assert _added_of_type(session, AuditLog) == []
    assert _added_of_type(session, OrderBoost) == []


# ─── 4. Boost < 0 → 422 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_order_boost_negative_returns_422():
    session = FakeSession()
    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/order-boost/4004",
        json={"boost": -5},
        headers=_HEADERS,
    )
    assert resp.status_code == 422
    assert _added_of_type(session, AuditLog) == []
    assert _added_of_type(session, OrderBoost) == []


# ─── 5. INSERT happy path — transport-date ───────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_transport_date_insert_happy_path():
    """Sem override existente → INSERT com transport_date_override populado."""
    session = FakeSession()
    session.queue_scalar(None)  # SELECT existing WorkOrderOverride → None

    new_date = datetime(2026, 7, 15, 9, 0, 0, tzinfo=timezone.utc)
    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/work-orders/5005/transport-date",
        json={
            "transport_date": new_date.isoformat(),
            "reason": "cliente pediu antecipacao",
        },
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["work_order_id"] == 5005
    # Pydantic devolve ISO-8601; comparamos pelo prefixo da data.
    assert body["transport_date_override"] is not None
    assert body["transport_date_override"].startswith("2026-07-15")
    assert body["reason"] == "cliente pediu antecipacao"
    assert body["updated_by"] == _USER

    added_overrides = _added_of_type(session, WorkOrderOverride)
    assert len(added_overrides) == 1
    assert added_overrides[0].work_order_id == 5005
    assert added_overrides[0].transport_date_override == new_date
    assert added_overrides[0].tenant_id == TEST_TENANT_ID

    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "INSERT"
    assert audits[0].entity_type == "work_order_override"
    assert audits[0].old_values is None
    assert audits[0].new_values["transport_date_override"] == new_date.isoformat()
    assert audits[0].new_values["reason"] == "cliente pediu antecipacao"
    assert audits[0].reason == "upsert_transport_date_override"


# ─── 6. Clear override (None) → UPDATE com NULL ──────────────────────────────


@pytest.mark.asyncio
async def test_upsert_transport_date_clear_with_existing_row():
    """Row existente + transport_date=None → UPDATE com NULL (limpa override)."""
    session = FakeSession()
    old_date = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    existing = _existing_override(
        work_order_id=6006,
        transport_date_override=old_date,
        reason="razao antiga",
    )
    session.queue_scalar(existing)

    client = _minimal_app(session)
    resp = client.patch(
        "/v1/plan/work-orders/6006/transport-date",
        json={"transport_date": None, "reason": "voltar ao calendario auto"},
        headers=_HEADERS,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["work_order_id"] == 6006
    assert body["transport_date_override"] is None
    assert body["reason"] == "voltar ao calendario auto"

    # Mutated in-place.
    assert existing.transport_date_override is None
    assert existing.reason == "voltar ao calendario auto"

    # Nenhum novo override adicionado a sessao — so o audit.
    added_overrides = _added_of_type(session, WorkOrderOverride)
    assert len(added_overrides) == 0

    audits = _added_of_type(session, AuditLog)
    assert len(audits) == 1
    assert audits[0].action == "UPDATE"
    assert audits[0].old_values == {
        "transport_date_override": old_date.isoformat(),
        "reason": "razao antiga",
    }
    assert audits[0].new_values == {
        "transport_date_override": None,
        "reason": "voltar ao calendario auto",
    }
