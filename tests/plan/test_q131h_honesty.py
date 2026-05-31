"""Q.131.H — honestidade: o scheduler NUNCA salta uma ordem em silêncio.

Toda a ordem submetida ou é planeada (≥1 operação) ou é registada em
`resolver.unplanned` com a razão — nunca desaparece. O scheduler expõe isto em
`unplanned_orders` + `orders_coverage` + um CopilotAlert(ORDERS_WITHOUT_ROUTING).

Property central (invariante de honestidade): planeadas ∪ não-planeadas == total.
"""
from __future__ import annotations

from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import RoutingResolver


def _state_with_route_for(model_ids):
    state = FactoryState(tenant_id=uuid4())
    state.historical_routes_by_model = {
        m: [
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1, "duration_hours": 4.32},
            {"fase_id": "2", "fase_nome": "Cura", "sequence": 2, "duration_hours": 17.38},
        ]
        for m in model_ids
    }
    return state


def test_unplanned_order_is_recorded_not_silently_dropped():
    state = _state_with_route_for({"42366"})  # só este modelo tem rota
    resolver = RoutingResolver(state)
    orders = [
        {"of_id": "OF-1", "modelo_id": "42366"},   # planeável
        {"of_id": "OF-2", "modelo_id": "99999"},   # sem rota -> unplanned
    ]
    ops = resolver.resolve_many(orders)

    assert len(ops) == 2                       # só OF-1 (2 fases)
    assert resolver.planned_order_ids == {"OF-1"}
    assert resolver.unplanned_count == 1
    assert resolver.unplanned[0]["order_id"] == "OF-2"
    assert resolver.unplanned[0]["reason"] == "no_route"
    assert resolver.orders_coverage == 0.5


def test_missing_of_id_recorded_with_reason():
    resolver = RoutingResolver(_state_with_route_for(set()))
    resolver.resolve({"modelo_id": "42366"})  # sem of_id
    assert resolver.unplanned_count == 1
    assert resolver.unplanned[0]["reason"] == "missing_of_id"


def test_coverage_is_one_when_all_planned():
    state = _state_with_route_for({"A", "B"})
    resolver = RoutingResolver(state)
    resolver.resolve_many([
        {"of_id": "OF-1", "modelo_id": "A"},
        {"of_id": "OF-2", "modelo_id": "B"},
    ])
    assert resolver.orders_coverage == 1.0
    assert resolver.unplanned_count == 0


@settings(max_examples=60, deadline=None)
@given(
    n_planeaveis=st.integers(min_value=0, max_value=8),
    n_orfas=st.integers(min_value=0, max_value=8),
)
def test_honesty_invariant_planned_plus_unplanned_equals_total(n_planeaveis, n_orfas):
    """INVARIANTE: nenhuma ordem desaparece. planeadas + não-planeadas == total,
    e a cobertura é exactamente planeadas/total ∈ [0,1]."""
    state = _state_with_route_for({"COM_ROTA"})
    resolver = RoutingResolver(state)
    orders = []
    for i in range(n_planeaveis):
        orders.append({"of_id": f"P-{i}", "modelo_id": "COM_ROTA"})
    for i in range(n_orfas):
        orders.append({"of_id": f"X-{i}", "modelo_id": "SEM_ROTA"})

    resolver.resolve_many(orders)

    total = len(orders)
    planeadas = len(resolver.planned_order_ids)
    nao_planeadas = len({u["order_id"] for u in resolver.unplanned})
    # cada ordem está exactamente num lado — nunca saltada em silêncio
    assert planeadas + nao_planeadas == total
    assert planeadas == n_planeaveis
    assert nao_planeadas == n_orfas
    if total:
        assert resolver.orders_coverage == n_planeaveis / total
        assert 0.0 <= resolver.orders_coverage <= 1.0
