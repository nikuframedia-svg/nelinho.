"""Q.166.A — CP-SAT timing model: feasibility + capacidades cumulative respeitadas.

Replay da solução: as contagens por instante (estações/operadores/moldes) nunca
excedem a capacidade; precedência + cura respeitadas. ortools ausente → available=False.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.engines import cpsat_scheduler as cs
from src.plan.engines.cpsat_scheduler import CPSATConfig, CPSATScheduler
from src.plan.engines.scheduling_adapter import SchedulingOperation

_H0 = datetime(2026, 6, 1, 0, 0, 0)


def _op(oid, order, fase, seq, dur, team=1, mold=False, model=""):
    return SchedulingOperation(
        operation_id=oid, order_id=order, product_id=model or "P", sequence=seq,
        operation_code=fase, duration_minutes=dur, machine_id=None, phase_id=fase,
        team_size=team, mold_required=mold, model_id=model,
    )


def _max_concurrency(intervals, demand_fn):
    """Sweep-line: máxima soma de demandas sobrepostas."""
    ev = []
    for (s, e, d) in intervals:
        if e <= s:
            continue
        ev.append((s, demand_fn(d)))
        ev.append((e, -demand_fn(d)))
    ev.sort(key=lambda x: (x[0], x[1]))  # libertações antes de ocupações no mesmo t
    cur = peak = 0
    for _, delta in ev:
        cur += delta
        peak = max(peak, cur)
    return peak


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_solve_respects_stations_workers_precedence_curing():
    state = FactoryState(tenant_id=uuid4())
    # 2 fases; fase A 2 estações + pool 2; fase B 3 estações + pool 3.
    state.phase_stations = {"A": 2, "B": 3}
    state.skill_matrix = {"A": {"w1", "w2"}, "B": {"w3", "w4", "w5"}}
    # cura A→B = 1h.
    state.phase_transition_gaps = {("A", "B"): 1.0}

    ops = []
    for i in range(6):  # 6 OFs: A(seq1) → B(seq2)
        ops.append(_op(f"O{i}A", f"OF{i}", "A", 1, 120, team=1))
        ops.append(_op(f"O{i}B", f"OF{i}", "B", 2, 60, team=1))

    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available and res.status in ("OPTIMAL", "FEASIBLE")

    # precedência + cura: B começa >= A.end + 60min
    for i in range(6):
        a_end = res.ends_min[f"O{i}A"]
        b_start = res.starts_min[f"O{i}B"]
        assert b_start >= a_end + 60

    # estações por fase nunca excedidas
    a_iv = [(res.starts_min[f"O{i}A"], res.ends_min[f"O{i}A"], 1) for i in range(6)]
    b_iv = [(res.starts_min[f"O{i}B"], res.ends_min[f"O{i}B"], 1) for i in range(6)]
    assert _max_concurrency(a_iv, lambda d: d) <= 2  # 2 estações em A
    assert _max_concurrency(b_iv, lambda d: d) <= 3  # 3 estações em B


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_global_operator_cap_respected():
    state = FactoryState(tenant_id=uuid4())
    # 1 fase, 5 estações, mas só 3 operadores ativos no total → cap global=3.
    state.phase_stations = {"A": 5}
    state.skill_matrix = {"A": {"w1", "w2", "w3"}}
    ops = [_op(f"O{i}", f"OF{i}", "A", 1, 60, team=1) for i in range(8)]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available
    iv = [(res.starts_min[f"O{i}"], res.ends_min[f"O{i}"], 1) for i in range(8)]
    # cap global = 3 operadores (união do skill_matrix), embora haja 5 estações.
    assert _max_concurrency(iv, lambda d: d) <= 3


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_mold_capacity_serializes_single_mold():
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"LAM": 4}
    state.skill_matrix = {"LAM": {"w1", "w2", "w3", "w4"}}
    # modelo MOD com 1 molde → fase com mold_required serializa (cap molde=1).
    state.molds_by_model = {"MOD": [MoldInfo(molde_id="m1", modelo_id="MOD")]}
    ops = [_op(f"O{i}", f"OF{i}", "LAM", 1, 60, team=1, mold=True, model="MOD")
           for i in range(4)]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available
    iv = [(res.starts_min[f"O{i}"], res.ends_min[f"O{i}"], 1) for i in range(4)]
    assert _max_concurrency(iv, lambda d: d) <= 1  # 1 molde → serial


def test_ortools_missing_returns_unavailable(monkeypatch):
    monkeypatch.setattr(cs, "HAS_ORTOOLS", False)
    state = FactoryState(tenant_id=uuid4())
    ops = [_op("O0", "OF0", "A", 1, 60)]
    res = CPSATScheduler().solve_timing(ops, state, _H0)
    assert res.available is False
    assert res.reason == "ortools_unavailable"


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_empty_ops_ok():
    state = FactoryState(tenant_id=uuid4())
    res = CPSATScheduler().solve_timing([], state, _H0)
    assert res.available and res.makespan_min == 0
