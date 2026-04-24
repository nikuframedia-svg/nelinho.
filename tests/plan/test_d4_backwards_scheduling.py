"""Sprint A D4 — backwards scheduling in the decoder.

Before this fix, `chromosome.schedule_direction = "backward"` was silently
ignored: the decoder always placed ops at the earliest feasible time,
regardless of the chromosome's intent. PL14 (schedule from transport_date)
was impossible to optimise — the GA could never learn "start OF_123 later
so it finishes just before the truck leaves".

Covers:
* `_compute_target_starts` walks each order in reverse, accumulating
  durations + curing gaps between consecutive phases, so op `target_start
  = due_date - tail_duration - tail_gaps`.
* forward mode (default) ignores targets entirely → identical to pre-fix
  behaviour (backwards-compat).
* backward mode shifts ops later when slack exists, but NEVER earlier
  than the precedence/resource floor.
* ops that would land past `horizon_end` clamp to `horizon_end - 1min`.
* `backwards_shifts` counter tracks how many ops actually moved.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import _compute_target_starts, decode
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


REF = datetime(2026, 4, 22, 8, 0)


def _machine(mid: str = "M1") -> SchedulingMachine:
    return SchedulingMachine(machine_id=mid, name=mid)


def _op(
    op_id: str,
    *,
    order_id: str = "OF1",
    sequence: int = 1,
    phase_id: str = "PHASE_A",
    duration_min: float = 60,
    due_date: datetime | None = None,
    machine_id: str = "M1",
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
        due_date=due_date,
    )


def _run(ops, *, direction: str = "forward", horizon_days: int = 3, skills=None):
    state = FactoryState(tenant_id=uuid4())
    if skills:
        state.skill_matrix = skills
    chrom = Chromosome(
        permutation=list(range(len(ops))),
        schedule_direction=direction,  # type: ignore[arg-type]
    )
    return decode(
        chrom, ops, [_machine()], state,
        horizon_start=REF,
        horizon_end=REF + timedelta(days=horizon_days),
    )


# ---------------------------------------------------------------------------
# _compute_target_starts — helper
# ---------------------------------------------------------------------------


def test_compute_target_starts_last_op_anchors_to_due_minus_own_duration():
    state = FactoryState(tenant_id=uuid4())
    due = REF + timedelta(hours=20)
    op = _op("O1", duration_min=60, due_date=due)
    targets = _compute_target_starts({"OF1": [op]}, state)

    # Single op: target_start = due - 1h (own duration only, no tail).
    assert targets["O1"] == due - timedelta(hours=1)


def test_compute_target_starts_accumulates_downstream_duration():
    state = FactoryState(tenant_id=uuid4())
    due = REF + timedelta(hours=40)
    ops = [
        _op("O1", sequence=1, duration_min=60, due_date=due),
        _op("O2", sequence=2, duration_min=120, due_date=due),
    ]
    targets = _compute_target_starts({"OF1": ops}, state)

    # O2 (last): due - 2h
    assert targets["O2"] == due - timedelta(hours=2)
    # O1: due - 2h (O2 duration) - 1h (own) = due - 3h
    # (no curing gap between PHASE_A and PHASE_A)
    assert targets["O1"] == due - timedelta(hours=3)


def test_compute_target_starts_includes_curing_gap():
    state = FactoryState(tenant_id=uuid4())
    state.phase_transition_gaps = {("LAMINAGEM", "CURA"): 15.0}
    due = REF + timedelta(hours=50)
    ops = [
        _op("O1", sequence=1, duration_min=60, phase_id="LAMINAGEM", due_date=due),
        _op("O2", sequence=2, duration_min=60, phase_id="CURA", due_date=due),
    ]
    targets = _compute_target_starts({"OF1": ops}, state)

    # O2: due - 1h
    assert targets["O2"] == due - timedelta(hours=1)
    # O1: due - 1h (O2 dur) - 15h (curing gap) - 1h (own) = due - 17h
    assert targets["O1"] == due - timedelta(hours=17)


def test_compute_target_starts_skips_orders_without_due_date():
    state = FactoryState(tenant_id=uuid4())
    ops = [_op("O1", duration_min=60)]  # no due_date
    targets = _compute_target_starts({"OF1": ops}, state)
    assert "O1" not in targets


# ---------------------------------------------------------------------------
# Decoder behaviour — forward vs backward
# ---------------------------------------------------------------------------


def test_forward_mode_starts_at_horizon_start():
    due = REF + timedelta(hours=48)
    ops = [_op("O1", duration_min=60, due_date=due)]
    result = _run(ops, direction="forward")

    # Forward: earliest feasible = horizon_start (no precedence).
    assert result["operations"][0]["start_time"] == REF.isoformat()
    assert result["backwards_shifts"] == 0


def test_backward_mode_shifts_single_op_to_target_start():
    """Single op, 1h duration, due in 48h → target_start = due - 1h.
    Horizon allows it → op runs at due - 1h, not at REF.
    """
    due = REF + timedelta(hours=48)
    ops = [_op("O1", duration_min=60, due_date=due)]
    result = _run(ops, direction="backward")

    scheduled_start = datetime.fromisoformat(result["operations"][0]["start_time"])
    expected_start = due - timedelta(hours=1)
    assert scheduled_start == expected_start
    assert result["backwards_shifts"] == 1


def test_backward_mode_respects_precedence_over_target():
    """O1 has due_date late; O2 is the successor. O2's target_start would
    be earlier than O1's end — but precedence forces O2 to wait for O1.
    We verify O2 starts at O1's end, NOT at its target_start.
    """
    due = REF + timedelta(hours=48)
    # O1 runs 4h, O2 runs 2h, due in 48h.
    # O2 target = due - 2h = REF + 46h
    # O1 target = due - 2h (O2) - 4h (own) = REF + 42h
    # If we process forward with precedence, O1 starts at REF+42h (target) → ends REF+46h.
    # O2 precedence forces start >= REF+46h, which is also its target.
    ops = [
        _op("O1", sequence=1, duration_min=240, due_date=due),
        _op("O2", sequence=2, duration_min=120, due_date=due),
    ]
    result = _run(ops, direction="backward")

    by_id = {o["operation_id"]: o for o in result["operations"]}
    o1_start = datetime.fromisoformat(by_id["O1"]["start_time"])
    o2_start = datetime.fromisoformat(by_id["O2"]["start_time"])
    o1_end = datetime.fromisoformat(by_id["O1"]["end_time"])

    # O2 must never start before O1 ends — precedence invariant.
    assert o2_start >= o1_end, f"precedence violated: {o2_start} < {o1_end}"
    # And O1 shifts to its backward target (REF + 42h)
    assert o1_start == REF + timedelta(hours=42)


def test_backward_mode_clamps_to_horizon_end():
    """due_date after horizon_end → target would be beyond horizon;
    decoder clamps so the op still fits (start <= horizon_end - 1min).
    """
    due = REF + timedelta(days=10)   # way past horizon
    ops = [_op("O1", duration_min=60, due_date=due)]
    result = _run(ops, direction="backward", horizon_days=2)

    scheduled_start = datetime.fromisoformat(result["operations"][0]["start_time"])
    horizon_end = REF + timedelta(days=2)
    # Must be <= horizon_end - 1min (the cap we added).
    assert scheduled_start <= horizon_end - timedelta(minutes=1)


def test_backward_without_due_date_falls_back_to_forward():
    """If an order has no due_date, we can't compute a target — the op
    schedules forward like before.
    """
    ops = [_op("O1", duration_min=60)]  # no due_date
    result = _run(ops, direction="backward")

    assert result["operations"][0]["start_time"] == REF.isoformat()
    assert result["backwards_shifts"] == 0


def test_backward_mode_counts_every_shifted_op():
    """Multiple orders, distinct machines → every op is free to shift to
    its own target. Using distinct machines isolates the shift from the
    resource-contention fallback (which itself is tested in the
    'respects_precedence' case).
    """
    due_a = REF + timedelta(hours=48)
    due_b = REF + timedelta(hours=36)
    ops = [
        _op("A1", order_id="OFA", duration_min=60, due_date=due_a, machine_id="M1"),
        _op("B1", order_id="OFB", duration_min=60, due_date=due_b, machine_id="M2"),
    ]
    # Manually attach two machines via direct decode call (the helper uses
    # a single machine — swap it out here).
    state = FactoryState(tenant_id=uuid4())
    chrom = Chromosome(permutation=[0, 1], schedule_direction="backward")
    result = decode(
        chrom, ops,
        [_machine("M1"), _machine("M2")],
        state,
        horizon_start=REF,
        horizon_end=REF + timedelta(days=3),
    )
    assert result["backwards_shifts"] == 2


# ---------------------------------------------------------------------------
# Forward mode backwards-compat — target computation is opt-in
# ---------------------------------------------------------------------------


def test_forward_schedule_ignores_target_starts_entirely():
    """Even with due_date set, forward mode must produce the pre-D4 result."""
    due = REF + timedelta(hours=48)
    ops = [
        _op("O1", sequence=1, duration_min=60, due_date=due),
        _op("O2", sequence=2, duration_min=60, due_date=due),
    ]
    result = _run(ops, direction="forward")

    # O1 starts at REF, O2 starts right after O1 (no queue_gap on this test).
    by_id = {o["operation_id"]: o for o in result["operations"]}
    assert by_id["O1"]["start_time"] == REF.isoformat()
    o1_end = datetime.fromisoformat(by_id["O1"]["end_time"])
    o2_start = datetime.fromisoformat(by_id["O2"]["start_time"])
    assert o2_start == o1_end
    assert result["backwards_shifts"] == 0
