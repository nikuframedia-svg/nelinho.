"""Sprint A ME1 — decoder exposes Blueprint v2.0 MAP-Elites axes.

Before this fix MAPElites3D had `use_v2_axes=True` plumbed but the
decoder never populated `lam_utilization`, `idle_pct` or
`tardiness_transport_d`, so the archive silently fell back to the
legacy global metrics (`avg_utilization`, `total_tardiness_hours`,
`num_late_orders`). Net effect: two very different NELO trade-offs
(e.g. high lam_util + 0 idle vs low lam_util + 20 idle) landed in the
same cell, collapsing diversity on the axis that actually matters.

Covers:
* decoder populates `lam_utilization` — % of scheduled minutes spent
  in LAMINAGEM* phases (the centro bottleneck on the Nelo shop floor)
* decoder populates `idle_pct` = `idle_ratio * 100`
* decoder populates `tardiness_transport_d` = `total_tardiness_hours / 24`
* MAPElites3D with `use_v2_axes=True` reads these fields directly —
  two schedules with identical legacy KPIs but different lam/idle
  occupy distinct cells
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.mapelites import MAPElites3D
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


def _machine(mid: str) -> SchedulingMachine:
    return SchedulingMachine(machine_id=mid, name=mid)


def _op(
    op_id: str,
    *,
    phase_id: str = "LAMINAGEM",
    duration_min: float = 60,
    machine_id: str = "M1",
    order_id: str = "OF1",
    sequence: int = 1,
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id="P1",
        sequence=sequence,
        operation_code=op_id,
        duration_minutes=duration_min,
        machine_id=machine_id,
        phase_id=phase_id,
    )


def _run(ops, horizon_days: int = 1, *, skills=None):
    state = FactoryState(tenant_id=uuid4())
    if skills:
        state.skill_matrix = skills
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=horizon_days)
    chrom = Chromosome(permutation=list(range(len(ops))))
    return decode(chrom, ops, [_machine("M1")], state, horizon_start, horizon_end)


# ---------------------------------------------------------------------------
# decoder populates the three axes
# ---------------------------------------------------------------------------


def test_empty_schedule_has_zero_v2_axes():
    result = _run([])
    assert result["lam_utilization"] == 0.0
    assert result["idle_pct"] == 0.0
    assert result["tardiness_transport_d"] == 0.0


def test_pure_laminagem_schedule_has_100pct_lam_utilization():
    """Every op is a LAMINAGEM phase → 100% of scheduled minutes are
    laminagem minutes."""
    ops = [_op("O1", phase_id="LAMINAGEM"), _op("O2", phase_id="LAMINAGEM", sequence=2)]
    result = _run(ops)
    assert result["lam_utilization"] == 100.0


def test_mixed_schedule_has_proportional_lam_utilization():
    """Half the minutes in LAMINAGEM, half in PINTURA → lam_utilization=50."""
    ops = [
        _op("O1", phase_id="LAMINAGEM", duration_min=60),
        _op("O2", phase_id="PINTURA_ACABAMENTO", duration_min=60, sequence=2),
    ]
    result = _run(ops)
    assert abs(result["lam_utilization"] - 50.0) < 0.1, result["lam_utilization"]


def test_no_laminagem_gives_zero_lam_utilization():
    ops = [_op("O1", phase_id="DESMOLDE"), _op("O2", phase_id="CORTE", sequence=2)]
    result = _run(ops)
    assert result["lam_utilization"] == 0.0


def test_laminagem_matches_accented_and_infusao_variants():
    """The phase matcher accepts LAMINAGEM, LAMINAGEM_INFUSAO, and
    mixed-case variants so different tenants' naming conventions don't
    silently fall off the axis.
    """
    ops = [
        _op("O1", phase_id="Laminagem", duration_min=60),
        _op("O2", phase_id="LAMINAGEM_INFUSAO", duration_min=60, sequence=2),
    ]
    result = _run(ops)
    assert result["lam_utilization"] == 100.0


def test_idle_pct_is_idle_ratio_times_hundred():
    """`idle_pct` and `idle_ratio` must stay in lockstep — the MAP-Elites
    v2 Z axis reads `idle_pct` (0-50%), the fitness v2 reads
    `total_idle_hours`, and both derive from the same underlying accounting.
    """
    ops = [_op("O1", phase_id="LAMINAGEM", duration_min=60)]
    result = _run(ops, horizon_days=1, skills={"LAMINAGEM": {"w1"}})
    assert abs(result["idle_pct"] - result["idle_ratio"] * 100.0) < 0.01


def test_tardiness_transport_d_is_tardy_hours_over_24():
    """An op that finishes well past its due_date accumulates tardy hours;
    the v2 axis surfaces the same number in days.
    """
    op = _op("O1", phase_id="LAMINAGEM", duration_min=60)
    op.due_date = datetime(2026, 4, 22, 9, 0)  # 1h after horizon_start
    # Force it to finish ~23h after due → ~23h tardy = ~0.96d
    op.duration_minutes = 24 * 60  # 24h duration

    state = FactoryState(tenant_id=uuid4())
    horizon_start = datetime(2026, 4, 22, 8, 0)
    horizon_end = horizon_start + timedelta(days=2)
    chrom = Chromosome(permutation=[0])
    result = decode(chrom, [op], [_machine("M1")], state, horizon_start, horizon_end)

    expected_d = result["total_tardiness_hours"] / 24.0
    assert abs(result["tardiness_transport_d"] - expected_d) < 0.01


# ---------------------------------------------------------------------------
# MAPElites3D with use_v2_axes=True reads the new fields
# ---------------------------------------------------------------------------


def test_mapelites_v2_separates_cells_by_lam_utilization():
    """Two schedules with identical legacy KPIs but very different
    lam_utilization must land in different cells when v2 axes are on.
    """
    archive = MAPElites3D(use_v2_axes=True)

    # Two pseudo-schedules — same legacy metrics, different lam_util.
    sched_high_lam = {
        "avg_utilization": 50.0,
        "total_tardiness_hours": 0.0,
        "num_late_orders": 0,
        "lam_utilization": 95.0,
        "tardiness_transport_d": 0.0,
        "idle_pct": 10.0,
    }
    sched_low_lam = dict(sched_high_lam)
    sched_low_lam["lam_utilization"] = 10.0

    chrom_a = Chromosome(permutation=[0, 1])
    chrom_b = Chromosome(permutation=[1, 0])
    archive.insert(chrom_a, fitness=100.0, schedule=sched_high_lam, generation=1)
    archive.insert(chrom_b, fitness=100.0, schedule=sched_low_lam, generation=1)

    assert archive.cells_occupied() == 2, (
        "legacy mode would have collapsed these into one cell; "
        "v2 axes must keep them separate"
    )


def test_mapelites_v2_falls_back_gracefully_when_v2_fields_missing():
    """Half-migrated decoders that only populate legacy KPIs still
    produce a valid cell — we don't want the archive to crash."""
    archive = MAPElites3D(use_v2_axes=True)
    sched_legacy_only = {
        "avg_utilization": 40.0,
        "total_tardiness_hours": 24.0,
        "num_late_orders": 1,
        # lam_utilization / tardiness_transport_d / idle_pct absent
    }
    chrom = Chromosome(permutation=[0])
    ok = archive.insert(chrom, fitness=50.0, schedule=sched_legacy_only, generation=0)
    assert ok
    assert archive.cells_occupied() == 1
