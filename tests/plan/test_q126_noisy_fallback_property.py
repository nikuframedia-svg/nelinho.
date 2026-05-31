"""Q.126.E — fallback ruidoso: o scheduler avisa (soft-warn) e marca o plano
`degraded` quando demasiadas operações caem no buffer 2x sintético.

Property tests (hypothesis) sobre a matemática do `fallback_fraction` + a
fronteira de decisão do limiar, mais um teste de contagem do `resolve()` a
provar que a rota real (source="history_db") NÃO conta como fallback. O
axioma Spelke relevante: durações vêm do histórico real — o 2x sintético é a
exceção que tem de ser RUIDOSA, nunca silenciosa.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.plan.cpo.scheduler_run import _DURATION_FALLBACK_ALERT_THRESHOLD
from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import RoutingResolver


def _resolver() -> RoutingResolver:
    return RoutingResolver(FactoryState(tenant_id=uuid4()))


@given(real=st.integers(min_value=0, max_value=2000),
       fb=st.integers(min_value=0, max_value=2000))
def test_fallback_fraction_invariants(real: int, fb: int):
    r = _resolver()
    r.resolved_ops = real + fb
    r.fallback_ops = fb
    frac = r.fallback_fraction
    assert 0.0 <= frac <= 1.0
    if r.resolved_ops == 0:
        assert frac == 0.0
    else:
        assert frac == pytest.approx(fb / (real + fb))


@given(fb=st.integers(min_value=0, max_value=1000))
def test_all_real_history_is_never_degraded(fb: int):
    """Cobertura total por histórico real (0 fallback) => fração 0 => nunca
    dispara o aviso, qualquer que seja o número de ops."""
    r = _resolver()
    r.resolved_ops = fb  # todas reais
    r.fallback_ops = 0
    assert r.fallback_fraction == 0.0
    assert not (r.fallback_fraction > _DURATION_FALLBACK_ALERT_THRESHOLD)


def test_threshold_boundary_decision():
    r = _resolver()
    r.resolved_ops = 100
    # exatamente no limiar (20/100 = 0.20) NÃO dispara (> estrito)
    r.fallback_ops = 20
    assert not (r.fallback_fraction > _DURATION_FALLBACK_ALERT_THRESHOLD)
    # acima do limiar dispara
    r.fallback_ops = 21
    assert r.fallback_fraction > _DURATION_FALLBACK_ALERT_THRESHOLD


def test_resolve_counts_history_db_as_real_not_fallback():
    """A rota real reconstruída de factory_raw (source="history_db") conta
    como REAL — fallback_ops fica 0, plano não degradado."""
    state = FactoryState(tenant_id=uuid4())
    state.historical_routes_by_model = {
        "M1": [
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 10, "duration_hours": 4.32},
            {"fase_id": "2", "fase_nome": "Cura", "sequence": 11, "duration_hours": 17.38},
        ]
    }
    r = RoutingResolver(state)
    ops = r.resolve({"of_id": "O1", "modelo_id": "M1"})

    assert len(ops) == 2
    assert r.resolved_ops == 2
    assert r.fallback_ops == 0
    assert r.fallback_fraction == 0.0
