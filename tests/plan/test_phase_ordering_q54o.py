"""Q.54.O — ordem das fases derivada do routing real.

Cobre :mod:`src.plan.services.phase_ordering` (funções puras + serviço) e
a ligação ao endpoint ``GET /v1/plan/orders/active``.

Bug que motiva: o endpoint ordenava as colunas Kanban da Fábrica por um
dicionário fixo de 16 fases com correspondência EXACTA. Os nomes reais do
ERP — "Laminagem peças" (64 barcos), "Corte peças" (55) — não batiam
certo, ficavam com ``phase_sequence = None`` e o frontend mandava as
colunas maiores para o fim. A ordem passa a vir de ``routing_template_phase``.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.plan.api.orders import router as orders_router
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.phase_classification import phase_sequence
from src.plan.services.phase_ordering import (
    PhaseOrderingService,
    build_phase_order,
    normalise_phase_name,
    resolve_phase_sequence,
)
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ─── normalise_phase_name ────────────────────────────────────────────────


def test_normalise_strips_accents_punctuation_and_collapses_spaces():
    # "Lixagem - água" (routing) e "Lixagem água" (ERP) têm de colar.
    assert normalise_phase_name("Lixagem - água") == "lixagem agua"
    assert normalise_phase_name("Lixagem água") == "lixagem agua"
    assert normalise_phase_name("Pintura Acabam.") == "pintura acabam"
    assert normalise_phase_name("  CONTROLO   de  Qualidade ") == "controlo de qualidade"


def test_normalise_empty_is_empty_string():
    assert normalise_phase_name(None) == ""
    assert normalise_phase_name("") == ""
    assert normalise_phase_name("   ") == ""


# ─── build_phase_order ───────────────────────────────────────────────────


def test_build_phase_order_ranks_by_average_position():
    rows = [
        ("Cura", 0.5),
        ("Laminagem", 0.2),
        ("Laminagem", 0.3),  # média 0.25 < 0.5
        ("Entregue", 0.95),
    ]
    order = build_phase_order(rows)
    assert order == {"laminagem": 0, "cura": 1, "entregue": 2}


def test_build_phase_order_ignores_null_name_and_position():
    rows = [("Laminagem", 0.2), (None, 0.1), ("Cura", None), ("", 0.4)]
    order = build_phase_order(rows)
    assert set(order) == {"laminagem"}


def test_build_phase_order_is_deterministic_on_ties():
    # Empate na posição → desempate estável pelo nome normalizado.
    rows = [("Beta", 0.5), ("Alfa", 0.5)]
    assert build_phase_order(rows) == {"alfa": 0, "beta": 1}


# ─── resolve_phase_sequence ──────────────────────────────────────────────


def test_resolve_exact_match_after_normalisation():
    order = {"lixagem agua": 5}
    # ERP escreve "Lixagem água"; depois de normalizar é match exacto.
    assert resolve_phase_sequence("Lixagem água", order) == 5


def test_resolve_substring_fallback():
    # "Pintura Acabam." (ERP) é prefixo de "Pintura Acabamento" (routing).
    order = {"pintura acabamento": 9}
    assert resolve_phase_sequence("Pintura Acabam.", order) == 9


def test_resolve_unknown_phase_is_none():
    order = {"laminagem": 0}
    assert resolve_phase_sequence("Fase Inventada", order) is None
    assert resolve_phase_sequence(None, order) is None


def test_resolve_against_empty_map_is_none():
    assert resolve_phase_sequence("Laminagem", {}) is None


# ─── PhaseOrderingService ────────────────────────────────────────────────


class _RoutingSession:
    """Sessão que devolve linhas ``(phase_name, posição)`` para a query
    agregada de routing."""

    def __init__(self, rows):
        self._rows = list(rows)

    async def execute(self, _stmt):
        rows = self._rows

        class _R:
            def all(self_inner):
                return list(rows)

        return _R()


@pytest.mark.asyncio
async def test_service_builds_order_map_from_routing_rows():
    rows = [
        ("Laminagem peças", 0.10),
        ("Corte peças", 0.20),
        ("Cura", 0.60),
    ]
    svc = PhaseOrderingService(_RoutingSession(rows), TENANT)
    order = await svc.phase_order_map()
    assert order == {"laminagem pecas": 0, "corte pecas": 1, "cura": 2}


@pytest.mark.asyncio
async def test_service_empty_routing_gives_empty_map():
    svc = PhaseOrderingService(_RoutingSession([]), TENANT)
    assert await svc.phase_order_map() == {}


# ─── GET /v1/plan/orders/active — integração ─────────────────────────────


class _EndpointSession:
    """Ordens para a query principal; linhas de routing para a query de
    ordenação. `routing` vazio → o endpoint cai no dicionário estático."""

    def __init__(self, orders, routing=None):
        self._orders = list(orders)
        self._routing = list(routing or [])

    async def execute(self, stmt):
        if "routing_template_phase" in str(stmt).lower():
            rows = self._routing

            class _RoutingResult:
                def all(self_inner):
                    return list(rows)

            return _RoutingResult()

        orders = self._orders

        class _R:
            def scalars(self_inner):
                return self_inner

            def all(self_inner):
                return list(orders)

        return _R()

    async def commit(self):
        pass


def _order(legacy_id: int, phase: str) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=legacy_id,
        product_id=legacy_id,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name=phase,
        status=OrderStatus.IN_PROGRESS,
        created_date=date(2026, 5, 1),
    )


def _app(session) -> FastAPI:
    app = FastAPI()
    app.include_router(orders_router, prefix="/v1/plan")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_tenant_header] = lambda: TENANT
    return app


# Ordem real do routing — as fases que o dicionário estático não conhecia.
_ROUTING_ROWS = [
    ("Laminagem peças", 0.05),
    ("Corte peças", 0.12),
    ("Laminagem", 0.25),
    ("Cura", 0.40),
    ("Montagem / Finalização", 0.80),
]


def test_active_orders_uses_routing_order_for_phase_sequence():
    orders = [
        _order(5001, "Laminagem peças"),
        _order(5002, "Corte peças"),
        _order(5003, "Laminagem"),
    ]
    client = TestClient(_app(_EndpointSession(orders, routing=_ROUTING_ROWS)))
    resp = client.get("/v1/plan/orders/active")
    assert resp.status_code == 200
    by_hull = {r["hull"]: r["phase_sequence"] for r in resp.json()}
    # Antes do Q.54.O estas duas fases davam None (não estavam no dict);
    # agora têm posição real e na ordem certa do fabrico.
    assert by_hull["5001"] == 0  # Laminagem peças
    assert by_hull["5002"] == 1  # Corte peças
    assert by_hull["5003"] == 2  # Laminagem
    assert by_hull["5001"] < by_hull["5002"] < by_hull["5003"]


def test_active_orders_phase_sequence_is_int_not_none_with_routing():
    orders = [_order(5005, "Corte peças")]
    client = TestClient(_app(_EndpointSession(orders, routing=_ROUTING_ROWS)))
    row = client.get("/v1/plan/orders/active").json()[0]
    assert isinstance(row["phase_sequence"], int)


def test_active_orders_falls_back_to_static_dict_without_routing():
    # Routing não-semeado → comportamento antigo (dicionário estático).
    orders = [_order(5006, "Laminagem")]
    client = TestClient(_app(_EndpointSession(orders)))
    row = client.get("/v1/plan/orders/active").json()[0]
    assert row["phase_sequence"] == phase_sequence("Laminagem")


def test_active_orders_unknown_phase_with_routing_is_none():
    # Fase que não existe no routing nem por substring → None honesto.
    orders = [_order(5007, "Fase Que Não Existe")]
    client = TestClient(_app(_EndpointSession(orders, routing=_ROUTING_ROWS)))
    row = client.get("/v1/plan/orders/active").json()[0]
    assert row["phase_sequence"] is None
