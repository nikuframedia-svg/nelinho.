"""Q.153.A3 — de-saturar a fitness v2 para o GA ter gradiente.

Bug: `_v2_fitness` normalizava tardiness ÷500h e makespan ÷1000h e clampava
a [0,1]. Com a dívida herdada (~619 000h) ambos colavam em 1.0 → o GA não
distinguia um plano mais pontual de um menos pontual. Mais gerações/tempo
nunca tornavam o plano mais pontual.

Fix: (a) usar o atraso EVITÁVEL `tardiness_beyond_today_h` (Q.153.A2) em vez
do cru; (b) referência de normalização DINÂMICA escalada ao baseline
(`ref = max(constante, baseline)`), injectada pelo engine.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.fitness import FitnessConfig, _v2_fitness
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

HORIZON_START = datetime(2026, 6, 1, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=14)


def test_static_refs_saturate_no_gradient():
    """Controlo: com a referência estática (constante), dois planos com
    atraso muito acima de 500h empatam — o bug que cegava o GA."""
    cfg = FitnessConfig(use_v2_weights=True)
    big = {"tardiness_beyond_today_h": 50_000.0, "makespan_hours": 4_000.0}
    less = {"tardiness_beyond_today_h": 40_000.0, "makespan_hours": 4_000.0}
    assert _v2_fitness(big, cfg) == _v2_fitness(less, cfg)  # saturado → empate


def test_dynamic_ref_restores_gradient():
    """Com a referência dinâmica escalada ao baseline, menos atraso
    evitável pontua estritamente melhor (fitness menor)."""
    cfg = FitnessConfig(use_v2_weights=True, norm_ref_tardiness_h=50_000.0)
    big = {"tardiness_beyond_today_h": 50_000.0, "makespan_hours": 4_000.0}
    less = {"tardiness_beyond_today_h": 40_000.0, "makespan_hours": 4_000.0}
    assert _v2_fitness(less, cfg) < _v2_fitness(big, cfg)


def test_prefers_beyond_today_over_raw_tardiness():
    """O termo usa o atraso evitável, não o cru: um plano com dívida
    herdada gigante mas pouco atraso evitável pontua melhor."""
    cfg = FitnessConfig(use_v2_weights=True, norm_ref_tardiness_h=1_000.0)
    avoidable = {"total_tardiness_hours": 600_000.0, "tardiness_beyond_today_h": 100.0}
    raw_only = {"total_tardiness_hours": 600_000.0}  # sem beyond_today → satura
    assert _v2_fitness(avoidable, cfg) < _v2_fitness(raw_only, cfg)


def _state_with_workers(workers_per_phase):
    s = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    s.skill_matrix = {p: set(w) for p, w in workers_per_phase.items()}
    return s


def _op(op_id, order_id, seq, **kw):
    return SchedulingOperation(
        operation_id=op_id, order_id=order_id, product_id="P1",
        sequence=seq, operation_code="OP", duration_minutes=30,
        machine_id=kw.pop("machine", "M1"), **kw,
    )


def test_engine_sets_dynamic_refs_from_baseline():
    """O engine injecta as referências dinâmicas no fitness_config a partir
    do baseline (ficam > 0 após schedule())."""
    state = _state_with_workers({"P": ["W1"]})
    ops = [_op(f"o-s{i}", "O1", i, phase_id="P", team_size=1) for i in range(1, 4)]
    engine = CPOv4Engine(
        state=state,
        config=CPOConfig(population_size=6, generations=3, time_limit_sec=5, seed=1),
    )
    engine.schedule(ops, [SchedulingMachine(machine_id="M1", name="M1")],
                    HORIZON_START, HORIZON_END)

    assert engine.fitness_config.norm_ref_makespan_h is not None
    assert engine.fitness_config.norm_ref_makespan_h > 0
    assert engine.fitness_config.norm_ref_tardiness_h is not None
    assert engine.fitness_config.norm_ref_idle_h is not None
