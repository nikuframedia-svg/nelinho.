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


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_q169c_moldless_model_ops_not_falsely_serialized():
    """Q.169.C — ops com mold_required mas SEM model_id iam todas para a
    chave '' com capacidade 1: barcos não-relacionados ficavam serializados
    num molde fantasma. Agora agrupam por barco — 2 barcos sem modelo
    conhecido correm em paralelo."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 2}
    state.skill_matrix = {"A": {"w1", "w2"}}

    ops = [
        _op("O1A", "OF1", "A", 1, 120, team=1, mold=True, model=""),
        _op("O2A", "OF2", "A", 1, 120, team=1, mold=True, model=""),
    ]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available and res.status in ("OPTIMAL", "FEASIBLE")
    iv = [(res.starts_min[o], res.ends_min[o], 1) for o in ("O1A", "O2A")]
    assert _max_concurrency(iv, lambda d: d) == 2, (
        "barcos distintos sem modelo NÃO partilham molde fantasma"
    )
    assert max(res.ends_min.values()) == 120, "paralelo => makespan = 1 duração"


# ───────────────────────── Q.174.F1 — desempenho ─────────────────────────


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_q174_fase_sem_pool_nao_disputa_operadores():
    """Fases SEM pool (cura/estado químico) não consomem o cumulative global
    de operadores. Antes, cada op de Cura levava team>=1 — procura FANTASMA
    (380 ops no último plano live) que serializava curas contra gente que
    nunca lhes é alocada."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 10, "CURA": 10}
    # 1 só operador ativo; CURA sem pool (fase física).
    state.skill_matrix = {"A": {"w1"}}

    ops = [_op("OA", "OF0", "A", 1, 60, team=1)]
    # 5 curas paralelas de OFs distintas — sem demanda de gente, correm juntas.
    ops += [_op(f"C{i}", f"OFC{i}", "CURA", 1, 600, team=1) for i in range(5)]

    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available
    # As 5 curas correm em paralelo (não serializadas pelo operador único):
    iv = [(res.starts_min[f"C{i}"], res.ends_min[f"C{i}"], 1) for i in range(5)]
    assert _max_concurrency(iv, lambda d: d) == 5
    assert res.makespan_min <= 600  # sem serialização fantasma (5×600 antes)


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_q174_horizonte_dinamico_com_hint():
    """Warm-start → o domínio aperta para ~1.5× o hint (e regista-se em
    horizon_minutes_used); kill-switch dynamic_horizon=False mantém o fixo."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 2}
    state.skill_matrix = {"A": {"w1", "w2"}}
    ops = [_op(f"O{i}", f"OF{i}", "A", 1, 60, team=1) for i in range(4)]
    hint = {f"O{i}": i * 60 for i in range(4)}  # makespan hint = 240min

    dyn = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0, hint_starts_min=hint,
    )
    assert dyn.available
    assert 0 < dyn.horizon_minutes_used < cs._DEFAULT_HORIZON_MINUTES

    fixo = CPSATScheduler(
        CPSATConfig(budget_s=10, deterministic=True, dynamic_horizon=False)
    ).solve_timing(ops, state, _H0, hint_starts_min=hint)
    assert fixo.available
    assert fixo.horizon_minutes_used == cs._DEFAULT_HORIZON_MINUTES
    # mesmo resultado de makespan nos dois domínios (apertar não degrada)
    assert dyn.makespan_min == fixo.makespan_min


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_q174_gap_pct_devolvido():
    """gap_pct viaja no resultado (e daí para cpo_meta — auditável na BD)."""
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 1}
    state.skill_matrix = {"A": {"w1"}}
    ops = [_op(f"O{i}", f"OF{i}", "A", 1, 30, team=1) for i in range(3)]
    res = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert res.available
    assert res.gap_pct >= 0.0  # OPTIMAL → 0.0; FEASIBLE → gap real
