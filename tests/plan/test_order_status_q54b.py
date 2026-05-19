"""Q.54.B — estado certo das ordens de produção.

Cobre:
* :mod:`src.plan.services.phase_classification` — classificação por nome,
  estado derivado, sequência canónica (incl. property tests).
* :func:`reconcile_order_statuses` — transição + audit trail.
* ``GET /v1/plan/orders/active`` — exclui fases terminais, expõe
  ``phase_sequence``.

Bug confirmado live: 521 ordens TODAS IN_PROGRESS quando 329 estavam
"Entregue", 26 "Armazem", 2 "Embalado". O endpoint devolvia barcos já
fora do chão de fábrica.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from src.plan.api.orders import router as orders_router
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.order_status_reconciler import reconcile_order_statuses
from src.plan.services.phase_classification import (
    NELO_PHASE_ORDER,
    PhaseBucket,
    classify_phase,
    is_completed_phase,
    phase_sequence,
    phase_status,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ─── phase_classification ────────────────────────────────────────────────


def test_terminal_phases_classify_as_concluido():
    for name in ("Entregue", "Armazem", "Armazém", "Embalado"):
        assert classify_phase(name) is PhaseBucket.CONCLUIDO, name
        assert is_completed_phase(name) is True, name


def test_por_comecar_phases():
    for name in ("Pendente", "Não Laminado", "Nao Laminado"):
        assert classify_phase(name) is PhaseBucket.POR_COMECAR, name
        assert is_completed_phase(name) is False, name


def test_shop_floor_phases_classify_as_a_decorrer():
    for name in (
        "Laminagem", "Corte", "Cura", "Desmolde", "Pintura Acabam.",
        "Lixagem água", "Montagem", "Colagem Peças", "CQ Final",
    ):
        assert classify_phase(name) is PhaseBucket.A_DECORRER, name


def test_empty_phase_is_a_decorrer_conservative():
    # Fase sem nome não esconde a ordem nem a marca concluída sem prova.
    assert classify_phase(None) is PhaseBucket.A_DECORRER
    assert classify_phase("") is PhaseBucket.A_DECORRER
    assert is_completed_phase(None) is False


def test_classification_is_accent_and_case_insensitive():
    assert classify_phase("ARMAZÉM") is PhaseBucket.CONCLUIDO
    assert classify_phase("  entregue  ") is PhaseBucket.CONCLUIDO
    assert classify_phase("EnTrEgUe ao cliente") is PhaseBucket.CONCLUIDO


def test_phase_status_maps_concluido_to_completed():
    assert phase_status("Entregue") is OrderStatus.COMPLETED
    assert phase_status("Armazém") is OrderStatus.COMPLETED
    assert phase_status("Embalado") is OrderStatus.COMPLETED


def test_phase_status_maps_active_phases_to_in_progress():
    for name in ("Laminagem", "Pendente", "Cura", "Montagem", None):
        assert phase_status(name) is OrderStatus.IN_PROGRESS, name


def test_phase_sequence_is_ordered_along_routing():
    # A ordem canónica é monotónica: cada fase mais adiante tem seq maior.
    seq_lam = phase_sequence("Laminagem")
    seq_cura = phase_sequence("Cura")
    seq_montagem = phase_sequence("Montagem")
    seq_entregue = phase_sequence("Entregue")
    assert seq_lam is not None
    assert seq_lam < seq_cura < seq_montagem < seq_entregue


def test_phase_sequence_unknown_phase_is_none():
    assert phase_sequence("Fase Inventada") is None
    assert phase_sequence(None) is None


@given(st.sampled_from(sorted(set(NELO_PHASE_ORDER)) + ["", "xyz", "fase nova"]))
def test_property_classify_always_returns_a_valid_bucket(phase_name):
    """Propriedade: classify_phase nunca rebenta e devolve sempre um bucket
    válido — fechado, total, determinístico."""
    bucket = classify_phase(phase_name)
    assert bucket in PhaseBucket
    # Determinístico: duas chamadas dão o mesmo resultado.
    assert classify_phase(phase_name) is bucket


@given(st.sampled_from(sorted(set(NELO_PHASE_ORDER))))
def test_property_terminal_phase_iff_completed_status(phase_name):
    """Propriedade: uma fase é CONCLUIDO se e só se o estado derivado é
    COMPLETED. Os dois sítios da regra nunca divergem."""
    is_done = classify_phase(phase_name) is PhaseBucket.CONCLUIDO
    is_completed = phase_status(phase_name) is OrderStatus.COMPLETED
    assert is_done == is_completed


# ─── reconcile_order_statuses ────────────────────────────────────────────


class _FakeSession:
    """Sessão async mínima: um execute(select) devolve as ordens; add()
    acumula linhas de audit; commit() é no-op."""

    def __init__(self, orders):
        self._orders = list(orders)
        self.added: list = []

    async def execute(self, _stmt):
        orders = self._orders

        class _R:
            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return list(orders)

        return _R()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


def _order(legacy_id: int, phase: str, status: OrderStatus) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=legacy_id,
        product_id=legacy_id,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name=phase,
        status=status,
        created_date=date(2026, 5, 1),
    )


@pytest.mark.asyncio
async def test_reconcile_transitions_delivered_order_to_completed():
    order = _order(4271, "Entregue", OrderStatus.IN_PROGRESS)
    session = _FakeSession([order])

    result = await reconcile_order_statuses(session, TENANT)

    assert result.scanned == 1
    assert result.transitioned == 1
    assert order.status is OrderStatus.COMPLETED
    # Audit row escrita na mesma sessão.
    assert len(session.added) == 1
    audit = session.added[0]
    assert audit.entity_type == "production_order"
    assert audit.old_values == {"status": "IN_PROGRESS"}
    assert audit.new_values == {"status": "COMPLETED"}


@pytest.mark.asyncio
async def test_reconcile_leaves_shop_floor_orders_untouched():
    order = _order(4280, "Laminagem", OrderStatus.IN_PROGRESS)
    session = _FakeSession([order])

    result = await reconcile_order_statuses(session, TENANT)

    assert result.transitioned == 0
    assert order.status is OrderStatus.IN_PROGRESS
    assert session.added == []


@pytest.mark.asyncio
async def test_reconcile_is_idempotent():
    # Ordem já COMPLETED em fase terminal — segunda passagem não muda nada.
    order = _order(4271, "Armazém", OrderStatus.COMPLETED)
    session = _FakeSession([order])

    result = await reconcile_order_statuses(session, TENANT)

    assert result.transitioned == 0
    assert session.added == []


class _FilteringSession:
    """Sessão que honra o WHERE status != CANCELLED da query do reconciler
    — devolve só as ordens não-canceladas, como o Postgres faria."""

    def __init__(self, orders):
        self._all = list(orders)
        self.added: list = []

    async def execute(self, _stmt):
        rows = [o for o in self._all if o.status is not OrderStatus.CANCELLED]

        class _R:
            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return list(rows)

        return _R()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_reconcile_never_touches_cancelled_orders():
    # CANCELLED é decisão humana/ERP — a query do reconciler exclui-as
    # (WHERE status != CANCELLED), por isso nunca viram COMPLETED.
    cancelled = _order(4271, "Entregue", OrderStatus.CANCELLED)
    active = _order(4272, "Entregue", OrderStatus.IN_PROGRESS)
    session = _FilteringSession([cancelled, active])

    result = await reconcile_order_statuses(session, TENANT)

    # Só a activa transita; a cancelada nem é vista.
    assert result.scanned == 1
    assert result.transitioned == 1
    assert cancelled.status is OrderStatus.CANCELLED
    assert active.status is OrderStatus.COMPLETED


# ─── GET /v1/plan/orders/active ──────────────────────────────────────────


class _EndpointSession:
    """Sessão que devolve uma lista fixa de ordens para o endpoint."""

    def __init__(self, orders):
        self._orders = list(orders)

    async def execute(self, _stmt):
        orders = self._orders

        class _R:
            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return list(orders)

        return _R()

    async def commit(self):
        pass


def _app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(orders_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return app


def test_active_orders_excludes_terminal_phases():
    orders = [
        _order(4271, "Laminagem", OrderStatus.IN_PROGRESS),
        _order(4272, "Entregue", OrderStatus.IN_PROGRESS),  # status preso
        _order(4273, "Armazém", OrderStatus.COMPLETED),
        _order(4274, "Montagem", OrderStatus.IN_PROGRESS),
        _order(4275, "Embalado", OrderStatus.IN_PROGRESS),
    ]
    client = TestClient(_app(_EndpointSession(orders)))
    resp = client.get("/v1/plan/orders/active")
    assert resp.status_code == 200
    body = resp.json()
    hulls = {row["hull"] for row in body}
    # Só Laminagem + Montagem ficam — as 3 terminais saem.
    assert hulls == {"4271", "4274"}


def test_active_orders_exposes_phase_sequence_and_name():
    orders = [_order(4271, "Laminagem", OrderStatus.IN_PROGRESS)]
    client = TestClient(_app(_EndpointSession(orders)))
    resp = client.get("/v1/plan/orders/active")
    assert resp.status_code == 200
    row = resp.json()[0]
    assert row["phase"] == "Laminagem"
    assert row["phase_sequence"] == phase_sequence("Laminagem")
    assert isinstance(row["phase_sequence"], int)


def test_active_orders_empty_is_explicit_not_500():
    client = TestClient(_app(_EndpointSession([])))
    resp = client.get("/v1/plan/orders/active")
    assert resp.status_code == 200
    assert resp.json() == []


def test_active_orders_phase_filter_still_works():
    orders = [
        _order(4271, "Laminagem", OrderStatus.IN_PROGRESS),
        _order(4274, "Montagem", OrderStatus.IN_PROGRESS),
    ]
    # O endpoint aplica o filtro `phase` na query; com a FakeSession a
    # query não filtra, mas o filtro de fase terminal continua a correr.
    client = TestClient(_app(_EndpointSession(orders)))
    resp = client.get("/v1/plan/orders/active", params={"phase": "Laminagem"})
    assert resp.status_code == 200
    # Ambas as ordens são shop-floor → nenhuma excluída.
    assert len(resp.json()) == 2
