"""Q.68.4.A — CP-SAT engine coverage push (18% -> 70%+).

DAMP tests for `src/plan/engines/cpsat_engine.py`. Each test is self-contained:
it builds its own operations/machines via local helpers so failures read as a
spec for the behaviour being asserted. No global fixtures, no class hierarchy.

Notes
-----
* The CP-SAT engine works in *minutes* (integer arithmetic). Durations are
  rounded with `int(...)`, so always use integer minutes >= 1.
* All tests run with a tiny ``time_limit_seconds`` so the whole file stays
  under a few seconds on a developer laptop.
* `SchedulingOperation` is a `@dataclass` with `__post_init__` filling list
  defaults — never share a list literal across operations because the dataclass
  mutates it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, List, Optional

import pytest

# Module under test is gated on ortools at import time, but the engine raises
# only when instantiated. We still skip the whole module if ortools is missing.
ortools = pytest.importorskip("ortools.sat.python.cp_model")

from src.plan.engines.cpsat_engine import (  # noqa: E402  — import after gate
    CPSATConfig,
    CPSATScheduler,
    is_cpsat_available,
)
from src.plan.engines.scheduling_adapter import (  # noqa: E402
    SchedulingMachine,
    SchedulingOperation,
)


# ---------------------------------------------------------------------------
# Local helpers (DAMP — duplicate small structures rather than share globals)
# ---------------------------------------------------------------------------


def _h(start: datetime, hours: float) -> datetime:
    return start + timedelta(hours=hours)


def _make_op(
    op_id: str,
    *,
    order_id: str = "ORD-1",
    product_id: str = "PRD-1",
    sequence: int = 1,
    duration_minutes: float = 30.0,
    machine_id: Optional[str] = "M1",
    due_date: Optional[datetime] = None,
    priority: float = 1.0,
    predecessor_ops: Optional[List[str]] = None,
    operation_code: str = "OP",
) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id=product_id,
        sequence=sequence,
        operation_code=operation_code,
        duration_minutes=duration_minutes,
        machine_id=machine_id,
        due_date=due_date,
        priority=priority,
        predecessor_ops=list(predecessor_ops) if predecessor_ops else [],
    )


def _make_machine(machine_id: str = "M1", name: Optional[str] = None) -> SchedulingMachine:
    return SchedulingMachine(machine_id=machine_id, name=name or machine_id)


def _short_scheduler(time_limit: float = 2.0) -> CPSATScheduler:
    return CPSATScheduler(CPSATConfig(time_limit_seconds=time_limit, num_workers=2))


def _horizon(hours: float = 24.0) -> tuple[datetime, datetime]:
    start = datetime(2026, 5, 21, 8, 0, 0)
    return start, start + timedelta(hours=hours)


def _starts_by_id(result: dict) -> dict[str, str]:
    return {op["operation_id"]: op["start_time"] for op in result["operations"]}


def _ends_by_id(result: dict) -> dict[str, str]:
    return {op["operation_id"]: op["end_time"] for op in result["operations"]}


def _machine_for(result: dict, op_id: str) -> str:
    for op in result["operations"]:
        if op["operation_id"] == op_id:
            return op["machine_id"]
    raise AssertionError(f"operation {op_id} not in result")


def _intervals_on(result: dict, machine_id: str) -> List[tuple[str, str]]:
    return [
        (op["start_time"], op["end_time"])
        for op in result["operations"]
        if op["machine_id"] == machine_id
    ]


# ---------------------------------------------------------------------------
# Module-level availability helpers
# ---------------------------------------------------------------------------


def test_is_cpsat_available_returns_true_when_ortools_installed():
    """When ortools imports successfully the module flag must report True.

    The pytest.importorskip at the top of this file guarantees we are in that
    state, so the helper must agree.
    """
    assert is_cpsat_available() is True


# ---------------------------------------------------------------------------
# Constructor / configuration
# ---------------------------------------------------------------------------


def test_default_config_uses_documented_defaults():
    cfg = CPSATConfig()
    assert cfg.time_limit_seconds == 30.0
    assert cfg.num_workers == 4
    assert cfg.makespan_weight == 1.0
    assert cfg.tardiness_weight == 10.0
    assert cfg.setup_time_minutes == 15


def test_constructor_accepts_explicit_config():
    cfg = CPSATConfig(time_limit_seconds=5.0, num_workers=1, makespan_weight=2.0)
    scheduler = CPSATScheduler(cfg)
    assert scheduler.config is cfg
    assert scheduler.config.time_limit_seconds == 5.0


def test_constructor_uses_default_config_when_none_passed():
    scheduler = CPSATScheduler(None)
    assert isinstance(scheduler.config, CPSATConfig)
    assert scheduler.config.time_limit_seconds == 30.0


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------


def test_schedule_with_no_operations_returns_empty_result():
    scheduler = _short_scheduler()
    start, end = _horizon()
    result = scheduler.schedule(operations=[], machines=[_make_machine()], horizon_start=start, horizon_end=end)

    assert result["success"] is True
    assert result["operations"] == []
    assert result["status"] == "optimal"
    assert result["engine_used"] == "cpsat"
    assert result["makespan_hours"] == 0.0
    assert result["num_late_orders"] == 0
    assert "No operations to schedule" in result["warnings"]
    # No solver fields on empty path (the cheap return)
    assert "solver_stats" not in result


def test_schedule_single_operation_completes_within_horizon():
    scheduler = _short_scheduler()
    start, end = _horizon()
    op = _make_op("OP-1", duration_minutes=60)

    result = scheduler.schedule([op], [_make_machine("M1")], start, end)

    assert result["success"] is True
    assert len(result["operations"]) == 1
    only = result["operations"][0]
    assert only["operation_id"] == "OP-1"
    assert only["machine_id"] == "M1"
    # duration must be preserved verbatim (engine reports input duration)
    assert only["duration_minutes"] == 60
    # makespan in hours ~ 1h
    assert result["makespan_hours"] >= 1.0


# ---------------------------------------------------------------------------
# Happy path — multi-operation
# ---------------------------------------------------------------------------


def test_schedule_three_operations_returns_sorted_by_start_time():
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op("A", sequence=1, duration_minutes=30, machine_id="M1"),
        _make_op("B", sequence=2, duration_minutes=30, machine_id="M2", order_id="ORD-2"),
        _make_op("C", sequence=3, duration_minutes=30, machine_id="M3", order_id="ORD-3"),
    ]
    machines = [_make_machine("M1"), _make_machine("M2"), _make_machine("M3")]

    result = scheduler.schedule(ops, machines, start, end)

    assert result["success"] is True
    starts = [op["start_time"] for op in result["operations"]]
    assert starts == sorted(starts), "operations must be sorted by start_time"
    assert len(result["operations"]) == 3


def test_schedule_returns_solver_stats_on_success():
    scheduler = _short_scheduler()
    start, end = _horizon()
    op = _make_op("OP-only", duration_minutes=15)
    result = scheduler.schedule([op], [_make_machine()], start, end)

    assert "solver_stats" in result
    stats = result["solver_stats"]
    assert "objective_value" in stats
    assert "num_conflicts" in stats
    assert "num_branches" in stats
    assert "wall_time" in stats
    assert stats["wall_time"] >= 0.0


# ---------------------------------------------------------------------------
# Precedence — sequence-based AND explicit predecessors
# ---------------------------------------------------------------------------


def test_schedule_respects_sequence_precedence_inside_same_order():
    scheduler = _short_scheduler()
    start, end = _horizon()
    # Both ops on different machines so any ordering is feasible — but they
    # share order_id, so the engine MUST honour sequence.
    ops = [
        _make_op("A", order_id="ORD-X", sequence=2, duration_minutes=30, machine_id="M1"),
        _make_op("B", order_id="ORD-X", sequence=1, duration_minutes=30, machine_id="M2"),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1"), _make_machine("M2")], start, end)

    assert result["success"] is True
    starts = _starts_by_id(result)
    ends = _ends_by_id(result)
    # B (sequence=1) must finish at or before A (sequence=2) starts
    assert ends["B"] <= starts["A"]


def test_schedule_respects_explicit_predecessor_ops():
    scheduler = _short_scheduler()
    start, end = _horizon()
    # Different orders so sequence-precedence does NOT apply — only the
    # explicit predecessor_ops edge should constrain ordering.
    ops = [
        _make_op("ROOT", order_id="ORD-A", sequence=1, duration_minutes=30, machine_id="M1"),
        _make_op(
            "CHILD",
            order_id="ORD-B",
            sequence=1,
            duration_minutes=30,
            machine_id="M2",
            predecessor_ops=["ROOT"],
        ),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1"), _make_machine("M2")], start, end)

    assert result["success"] is True
    starts = _starts_by_id(result)
    ends = _ends_by_id(result)
    assert ends["ROOT"] <= starts["CHILD"]


def test_schedule_ignores_unknown_predecessor_ids_gracefully():
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op(
            "ONLY",
            duration_minutes=20,
            machine_id="M1",
            predecessor_ops=["DOES-NOT-EXIST"],
        ),
    ]
    # Should not crash; the predecessor reference is silently dropped.
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["success"] is True
    assert len(result["operations"]) == 1


# ---------------------------------------------------------------------------
# Machine constraints — no-overlap
# ---------------------------------------------------------------------------


def test_schedule_machine_no_overlap_two_ops_same_machine():
    """Property: two ops on the same machine never overlap in time."""
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op("A", order_id="ORD-1", sequence=1, duration_minutes=60, machine_id="M1"),
        _make_op("B", order_id="ORD-2", sequence=1, duration_minutes=60, machine_id="M1"),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)

    assert result["success"] is True
    intervals = sorted(_intervals_on(result, "M1"))
    assert len(intervals) == 2
    # second interval must start at or after first ends
    assert intervals[0][1] <= intervals[1][0]


def test_schedule_machine_no_overlap_property_with_five_ops():
    """Property: pairwise no-overlap across five ops on a single machine."""
    scheduler = _short_scheduler(time_limit=3.0)
    start, end = _horizon(48)
    ops = [
        _make_op(f"OP-{i}", order_id=f"ORD-{i}", sequence=1, duration_minutes=30, machine_id="M1")
        for i in range(5)
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["success"] is True

    intervals = sorted(_intervals_on(result, "M1"))
    for (s1, e1), (s2, e2) in zip(intervals, intervals[1:]):
        assert e1 <= s2, f"overlap detected: {(s1, e1)} vs {(s2, e2)}"


def test_schedule_routes_unknown_machine_to_virtual_manual():
    """machine_id pointing to a machine not in `machines` is rerouted to MANUAL."""
    scheduler = _short_scheduler()
    start, end = _horizon()
    op = _make_op("X", machine_id="GHOST-MACHINE", duration_minutes=15)

    result = scheduler.schedule([op], [_make_machine("REAL-M")], start, end)

    assert result["success"] is True
    # Output preserves the original op.machine_id ("GHOST-MACHINE") in the
    # result dict (since `_build_result` uses `op.machine_id or "MANUAL"`),
    # but the CONSTRAINT was added on the MANUAL machine pool. We assert the
    # reported machine_id matches the input (this captures current behaviour).
    assert _machine_for(result, "X") == "GHOST-MACHINE"


def test_schedule_routes_none_machine_to_manual():
    scheduler = _short_scheduler()
    start, end = _horizon()
    op = _make_op("MAN-1", machine_id=None, duration_minutes=20)

    result = scheduler.schedule([op], [_make_machine("M1")], start, end)

    assert result["success"] is True
    assert _machine_for(result, "MAN-1") == "MANUAL"


# ---------------------------------------------------------------------------
# Duration edge cases
# ---------------------------------------------------------------------------


def test_schedule_clamps_zero_duration_to_one_minute():
    """Internal contract: zero/negative duration is treated as 1-minute interval.

    The reported `duration_minutes` in the result still reflects the input
    value (the engine doesn't rewrite the op), but the schedule must be
    feasible — so no exception.
    """
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [_make_op("Z", duration_minutes=0.0, machine_id="M1")]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)

    assert result["success"] is True
    assert result["operations"][0]["duration_minutes"] == 0.0


def test_schedule_clamps_negative_duration_to_one_minute():
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [_make_op("NEG", duration_minutes=-5.0, machine_id="M1")]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# Tardiness & due-date handling
# ---------------------------------------------------------------------------


def test_schedule_records_late_order_when_due_date_violated():
    scheduler = _short_scheduler()
    start, end = _horizon(hours=24)
    # Two ops sharing a machine, each 6h long, so makespan is at least 12h.
    # Due date is 2h after start -> at least one is late.
    due = _h(start, 2)
    ops = [
        _make_op("A", order_id="ORD-LATE", sequence=1, duration_minutes=360, machine_id="M1", due_date=due),
        _make_op("B", order_id="ORD-LATE2", sequence=1, duration_minutes=360, machine_id="M1", due_date=due),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)

    assert result["success"] is True
    assert result["num_late_orders"] >= 1
    assert result["total_tardiness_hours"] > 0.0


def test_schedule_no_tardiness_when_due_dates_in_future():
    scheduler = _short_scheduler()
    start, end = _horizon(hours=48)
    far_future = _h(start, 40)
    ops = [
        _make_op("A", duration_minutes=30, machine_id="M1", due_date=far_future),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["num_late_orders"] == 0
    assert result["total_tardiness_hours"] == 0.0


def test_schedule_ignores_due_dates_before_horizon_start():
    """due_minutes <= 0 path: tardiness var is NOT created."""
    scheduler = _short_scheduler()
    start, end = _horizon()
    in_past = start - timedelta(hours=10)  # before horizon
    ops = [_make_op("PAST-DUE", duration_minutes=30, machine_id="M1", due_date=in_past)]

    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["success"] is True
    # Even though the op completes after `in_past`, the engine cannot count
    # it as tardy because the due-date is before the horizon. But the result
    # builder DOES compare end_dt > due_date in absolute terms, so it WILL
    # mark it late. We assert the schedule itself stays feasible.
    assert len(result["operations"]) == 1


# ---------------------------------------------------------------------------
# Objective behaviour
# ---------------------------------------------------------------------------


def test_schedule_minimizes_makespan_with_two_parallel_machines():
    """Given two independent ops and two machines, the solver should run them
    in parallel — making makespan equal to the longest op, not their sum."""
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op("A", order_id="O1", sequence=1, duration_minutes=60, machine_id="M1"),
        _make_op("B", order_id="O2", sequence=1, duration_minutes=60, machine_id="M2"),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1"), _make_machine("M2")], start, end)
    assert result["success"] is True
    # parallel execution => makespan ≈ 1h, definitely < 2h
    assert result["makespan_hours"] < 1.5


def test_schedule_objective_with_priority_weights_higher_priority_finishes_first():
    """High-priority op with imminent due date should be scheduled before
    low-priority op when both share a machine."""
    scheduler = _short_scheduler(time_limit=3.0)
    start, end = _horizon()
    tight_due = _h(start, 1.5)
    ops = [
        _make_op(
            "LOW",
            order_id="ORD-LOW",
            sequence=1,
            duration_minutes=60,
            machine_id="M1",
            due_date=_h(start, 20),
            priority=1.0,
        ),
        _make_op(
            "HIGH",
            order_id="ORD-HIGH",
            sequence=1,
            duration_minutes=60,
            machine_id="M1",
            due_date=tight_due,
            priority=10.0,
        ),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)

    assert result["success"] is True
    starts = _starts_by_id(result)
    # tardiness penalty dominates makespan => HIGH (priority=10, tight due) wins.
    assert starts["HIGH"] < starts["LOW"]


# ---------------------------------------------------------------------------
# Utilization & KPI computation
# ---------------------------------------------------------------------------


def test_schedule_reports_utilization_between_zero_and_one_hundred():
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op("A", duration_minutes=30, machine_id="M1"),
        _make_op("B", order_id="ORD-2", duration_minutes=30, machine_id="M1"),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert 0 <= result["avg_utilization"] <= 100


def test_schedule_reports_zero_late_orders_for_no_due_dates():
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [_make_op("A", duration_minutes=30, machine_id="M1", due_date=None)]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)

    assert result["num_late_orders"] == 0
    assert result["total_tardiness_hours"] == 0.0


# ---------------------------------------------------------------------------
# Tight horizon — infeasibility path
# ---------------------------------------------------------------------------


def test_schedule_infeasible_when_horizon_too_short():
    """A horizon of 5 minutes cannot fit two serial 60-min ops on one machine.

    The engine should return success=False with a non-empty warning and the
    infeasible / unknown status.
    """
    scheduler = _short_scheduler(time_limit=1.0)
    start = datetime(2026, 5, 21, 8, 0, 0)
    end = start + timedelta(minutes=5)
    ops = [
        _make_op("A", order_id="O", sequence=1, duration_minutes=60, machine_id="M1"),
        _make_op("B", order_id="O", sequence=2, duration_minutes=60, machine_id="M1"),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)

    assert result["success"] is False
    assert result["engine_used"] == "cpsat"
    assert result["operations"] == []
    assert result["status"] in {"infeasible", "unknown", "model_invalid"}
    assert any("status" in w.lower() for w in result["warnings"])
    assert result["makespan_hours"] == 0.0


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


def test_scheduled_operation_dict_has_all_required_keys():
    scheduler = _short_scheduler()
    start, end = _horizon()
    op = _make_op("OP-X", duration_minutes=30, machine_id="M1")
    result = scheduler.schedule([op], [_make_machine("M1")], start, end)

    assert result["success"] is True
    item = result["operations"][0]
    for key in (
        "operation_id",
        "order_id",
        "product_id",
        "operation_code",
        "machine_id",
        "start_time",
        "end_time",
        "duration_minutes",
        "setup_minutes",
    ):
        assert key in item, f"missing key {key!r} in scheduled op"
    # ISO-format strings (parseable)
    datetime.fromisoformat(item["start_time"])
    datetime.fromisoformat(item["end_time"])


def test_schedule_result_top_level_schema_on_success():
    scheduler = _short_scheduler()
    start, end = _horizon()
    op = _make_op("S", duration_minutes=15, machine_id="M1")
    result = scheduler.schedule([op], [_make_machine("M1")], start, end)

    for key in (
        "success",
        "engine_used",
        "rule_used",
        "solve_time_sec",
        "status",
        "operations",
        "makespan_hours",
        "total_tardiness_hours",
        "num_late_orders",
        "avg_utilization",
        "warnings",
        "solver_stats",
    ):
        assert key in result
    assert result["rule_used"] is None
    assert result["engine_used"] == "cpsat"
    assert isinstance(result["warnings"], list)


# ---------------------------------------------------------------------------
# Multi-machine routing
# ---------------------------------------------------------------------------


def test_schedule_distributes_ops_across_listed_machines():
    """Two ops, two real machines: each op goes to the machine it requested."""
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op("A", order_id="O1", sequence=1, duration_minutes=30, machine_id="M-A"),
        _make_op("B", order_id="O2", sequence=1, duration_minutes=30, machine_id="M-B"),
    ]
    machines = [_make_machine("M-A"), _make_machine("M-B")]
    result = scheduler.schedule(ops, machines, start, end)

    assert result["success"] is True
    assert _machine_for(result, "A") == "M-A"
    assert _machine_for(result, "B") == "M-B"


def test_schedule_mixed_manual_and_machine_ops_succeeds():
    scheduler = _short_scheduler()
    start, end = _horizon()
    ops = [
        _make_op("MACHINE-OP", duration_minutes=30, machine_id="M1"),
        _make_op("HAND-OP", order_id="ORD-2", duration_minutes=20, machine_id=None),
    ]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["success"] is True
    assert _machine_for(result, "MACHINE-OP") == "M1"
    assert _machine_for(result, "HAND-OP") == "MANUAL"


# ---------------------------------------------------------------------------
# Time-bounds property
# ---------------------------------------------------------------------------


def test_schedule_property_all_ops_within_horizon():
    """Property: every scheduled op starts >= horizon_start and ends <= horizon_end."""
    scheduler = _short_scheduler()
    start, end = _horizon(hours=8)
    ops = [
        _make_op("A", order_id="O1", sequence=1, duration_minutes=30, machine_id="M1"),
        _make_op("B", order_id="O2", sequence=1, duration_minutes=45, machine_id="M2"),
        _make_op("C", order_id="O3", sequence=1, duration_minutes=15, machine_id="M1"),
    ]
    machines = [_make_machine("M1"), _make_machine("M2")]
    result = scheduler.schedule(ops, machines, start, end)
    assert result["success"] is True

    for item in result["operations"]:
        op_start = datetime.fromisoformat(item["start_time"])
        op_end = datetime.fromisoformat(item["end_time"])
        assert op_start >= start, f"op {item['operation_id']} starts before horizon"
        assert op_end <= end, f"op {item['operation_id']} ends after horizon"
        assert op_end >= op_start


# ---------------------------------------------------------------------------
# Configuration flowing through
# ---------------------------------------------------------------------------


def test_schedule_respects_short_time_limit_does_not_hang():
    """Sanity guard: a tiny time-limit must not deadlock the test suite."""
    scheduler = CPSATScheduler(CPSATConfig(time_limit_seconds=0.5, num_workers=1))
    start, end = _horizon()
    op = _make_op("ONE", duration_minutes=15, machine_id="M1")
    result = scheduler.schedule([op], [_make_machine("M1")], start, end)
    assert result["success"] is True
    # solve_time_sec is wall-clock incl. python overhead so allow a generous bound
    assert result["solve_time_sec"] < 5.0


def test_schedule_solve_time_recorded_on_infeasible_path():
    """Even when the solver returns no solution, the result must include
    a non-negative solve_time_sec — otherwise dashboards crash."""
    scheduler = _short_scheduler(time_limit=0.5)
    start = datetime(2026, 5, 21, 8, 0, 0)
    end = start + timedelta(minutes=2)  # too short
    ops = [_make_op("A", duration_minutes=60, machine_id="M1")]
    result = scheduler.schedule(ops, [_make_machine("M1")], start, end)
    assert result["success"] is False
    assert result["solve_time_sec"] >= 0.0
