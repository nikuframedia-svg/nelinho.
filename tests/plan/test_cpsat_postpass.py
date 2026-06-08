"""Q.166.B — post-pass: atribuição concreta válida, sem double-booking.

Todo operador ∈ workers_for(fase); estação/molde/operador nunca sobrepostos no
tempo; ScheduledOp com campos válidos. Corre o CP-SAT real para obter os tempos.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.plan.cpo.state import FactoryState, MoldInfo
from src.plan.engines import cpsat_scheduler as cs
from src.plan.engines.cpsat_scheduler import CPSATConfig, CPSATScheduler
from src.plan.engines.cpsat_postpass import assign_concrete
from src.plan.engines.scheduling_adapter import SchedulingOperation

_H0 = datetime(2026, 6, 1, 0, 0, 0)


def _op(oid, order, fase, seq, dur, team=1, mold=False, model=""):
    return SchedulingOperation(
        operation_id=oid, order_id=order, product_id=model or "P", sequence=seq,
        operation_code=fase, duration_minutes=dur, machine_id=None, phase_id=fase,
        team_size=team, mold_required=mold, model_id=model,
    )


def _no_overlap(intervals):
    """True se nenhum par de intervalos (start,end) se sobrepõe."""
    iv = sorted(intervals, key=lambda x: x[0])
    for (s1, e1), (s2, e2) in zip(iv, iv[1:]):
        if s2 < e1:
            return False
    return True


def test_assign_concrete_empty_no_ortools_needed():
    # assign_concrete é Python puro (não precisa de ortools): sem ops → [].
    state = FactoryState(tenant_id=uuid4())
    assert assign_concrete([], state, _H0, {}) == []


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_postpass_valid_assignment_no_double_book():
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 2, "B": 2}
    state.skill_matrix = {"A": {"w1", "w2"}, "B": {"w3", "w4"}}
    state.phase_transition_gaps = {("A", "B"): 1.0}
    state.molds_by_model = {"MOD": [MoldInfo(molde_id="m1", modelo_id="MOD"),
                                    MoldInfo(molde_id="m2", modelo_id="MOD")]}

    ops = []
    for i in range(5):
        ops.append(_op(f"O{i}A", f"OF{i}", "A", 1, 120, team=1, mold=True, model="MOD"))
        ops.append(_op(f"O{i}B", f"OF{i}", "B", 2, 60, team=1))

    timing = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    assert timing.available

    scheduled = assign_concrete(ops, state, _H0, timing.starts_min)
    assert len(scheduled) == len(ops)

    # 1) todo operador ∈ workers_for(fase)
    for s in scheduled:
        pool = state.workers_for(s.phase_id)
        for w in s.workers:
            assert w in pool, f"worker {w} fora do pool da fase {s.phase_id}"

    # 2) nenhum operador double-booked
    by_worker = {}
    for s in scheduled:
        for w in s.workers:
            by_worker.setdefault(w, []).append((s.start, s.end))
    for w, iv in by_worker.items():
        assert _no_overlap(iv), f"operador {w} double-booked"

    # 3) nenhuma estação double-booked
    by_machine = {}
    for s in scheduled:
        by_machine.setdefault(s.machine_id, []).append((s.start, s.end))
    for m, iv in by_machine.items():
        assert _no_overlap(iv), f"estação {m} double-booked"

    # 4) nenhum molde double-booked
    by_mold = {}
    for s in scheduled:
        if s.mold_id:
            by_mold.setdefault(s.mold_id, []).append((s.start, s.end))
    for m, iv in by_mold.items():
        assert _no_overlap(iv), f"molde {m} double-booked"

    # 5) precedência+cura respeitada (B >= A.end + 1h)
    ends = {s.operation_id: s.end for s in scheduled}
    starts = {s.operation_id: s.start for s in scheduled}
    for i in range(5):
        assert (starts[f"O{i}B"] - ends[f"O{i}A"]).total_seconds() >= 3600 - 1


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_postpass_calendar_keeps_work_on_working_days():
    # Q.166.C — com calendário (Seg-Sex 8h), nenhuma op cai em fim-de-semana e a
    # cura é preservada (piso wall-clock). 24/7 sem calendário.
    from src.plan.services.factory_calendar import FactoryCalendar
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"A": 2, "B": 2}
    state.skill_matrix = {"A": {"w1", "w2"}, "B": {"w3", "w4"}}
    state.phase_transition_gaps = {("A", "B"): 1.0}
    state.calendar = FactoryCalendar()  # Mon-Fri 8h default

    ops = []
    for i in range(6):
        ops.append(_op(f"O{i}A", f"OF{i}", "A", 1, 240, team=1))   # 4h
        ops.append(_op(f"O{i}B", f"OF{i}", "B", 2, 240, team=1))
    timing = CPSATScheduler(CPSATConfig(budget_s=10, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    scheduled = assign_concrete(ops, state, _H0, timing.starts_min)
    # nenhuma op arranca num fim-de-semana
    for s in scheduled:
        assert s.start.weekday() < 5, f"op {s.operation_id} arranca ao fim-de-semana"
    # precedência+cura ainda respeitada (B >= A.end + 1h wall-clock)
    ends = {s.operation_id: s.end for s in scheduled}
    starts = {s.operation_id: s.start for s in scheduled}
    for i in range(6):
        assert (starts[f"O{i}B"] - ends[f"O{i}A"]).total_seconds() >= 3600 - 1


@pytest.mark.skipif(not cs.HAS_ORTOOLS, reason="ortools não instalado")
def test_postpass_empty_pool_schedules_manual():
    # Fase sem skill_matrix → ops agendadas como manual (workers vazio), sem crash.
    state = FactoryState(tenant_id=uuid4())
    state.phase_stations = {"X": 1}
    ops = [_op("O0", "OF0", "X", 1, 60)]
    timing = CPSATScheduler(CPSATConfig(budget_s=5, deterministic=True)).solve_timing(
        ops, state, _H0,
    )
    scheduled = assign_concrete(ops, state, _H0, timing.starts_min)
    assert len(scheduled) == 1 and scheduled[0].workers == []
