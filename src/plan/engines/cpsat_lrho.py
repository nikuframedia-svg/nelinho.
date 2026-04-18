"""
ProdPlan ONE — CP-SAT Rolling Horizon (L-RHO) (Sprint P.10)
============================================================

Blueprint v2.0 §5.5 — 5th cascade phase. Uses OR-Tools CP-SAT to refine
the GA elite over rolling 2-day windows, warm-started by the GA's own
schedule, with a 15s total budget.

Why rolling, not monolithic:
* Full-horizon CP-SAT on 500 ops blows past the 15s slice.
* 2-day windows with 1-day step keep the per-solve problem small (~20-50
  ops) and let us re-optimise the "close-in" bit where delays hurt most.
* Ops with `start < now + 4h` are **frozen** — the solver is not allowed
  to move them (the shop floor has already committed).

Dual-resource: each operation creates one `IntervalVar` per resource it
consumes (machine, every worker) and a `NoOverlap` constraint per resource.
The same interval is shared across those constraints so a single start
time keeps machine, worker_a, worker_b and mold all consistent.

OR-Tools is optional. When `ortools` isn't importable, `schedule()` returns
`{used: False, reason: "ortools_unavailable"}` and the caller keeps the GA's
output. Tests that can't install ortools (most CI setups) skip the real
solve and exercise the stub.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:  # pragma: no cover — ortools is optional at runtime
    from ortools.sat.python import cp_model  # type: ignore

    HAS_ORTOOLS = True
except Exception:  # pragma: no cover
    cp_model = None  # type: ignore
    HAS_ORTOOLS = False


@dataclass
class LRHOConfig:
    """Sprint P.10 parameters."""

    horizon_days: int = 2          # window size
    step_days: int = 1             # roll stride
    frozen_zone_hours: float = 4.0  # ops starting within this window are frozen
    budget_s: float = 15.0
    solver_threads: int = 4


@dataclass
class LRHOResult:
    used: bool
    improved: bool = False
    windows: int = 0
    ops_rescheduled: int = 0
    solve_time_s: float = 0.0
    schedule: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)

    def to_meta(self) -> Dict[str, Any]:
        return {
            "used": self.used,
            "improved": self.improved,
            "windows": self.windows,
            "ops_rescheduled": self.ops_rescheduled,
            "solve_time_s": round(self.solve_time_s, 3),
            "warnings": list(self.warnings),
        }


class CPSATLRHO:
    """Rolling-horizon refinement over a GA baseline schedule."""

    def __init__(self, config: Optional[LRHOConfig] = None) -> None:
        self.config = config or LRHOConfig()

    def refine(
        self,
        baseline_schedule: Dict[str, Any],
        *,
        horizon_start: datetime,
        horizon_end: datetime,
        now: Optional[datetime] = None,
    ) -> LRHOResult:
        """Refine `baseline_schedule["operations"]` over rolling windows.

        Returns an `LRHOResult`. When OR-Tools isn't available the result's
        `used=False` and the caller keeps the baseline.
        """
        if not HAS_ORTOOLS:
            return LRHOResult(used=False, warnings=["ortools_unavailable"])

        started = time.time()
        ops = list(baseline_schedule.get("operations") or [])
        if not ops:
            return LRHOResult(used=False, warnings=["no_operations"])

        now = now or horizon_start
        frozen_cutoff = now + timedelta(hours=self.config.frozen_zone_hours)

        # Slice operations into rolling windows.
        windows = self._plan_windows(horizon_start, horizon_end)
        total_ops_moved = 0
        warnings: List[str] = []

        # Work on a dict keyed by operation_id so we can safely update ops in place.
        op_index: Dict[str, Dict[str, Any]] = {
            op.get("operation_id", f"op-{i}"): dict(op)
            for i, op in enumerate(ops)
        }

        for window_start, window_end in windows:
            if time.time() - started > self.config.budget_s:
                warnings.append(f"budget_exhausted_after_window_{window_start.isoformat()}")
                break

            window_ops = [
                op for op in op_index.values()
                if _in_window(op, window_start, window_end)
            ]
            if not window_ops:
                continue

            moved = self._solve_window(
                window_ops, window_start, window_end, frozen_cutoff,
            )
            total_ops_moved += moved

        elapsed = time.time() - started

        # Rebuild the schedule with refined ops — preserves the original order.
        refined_ops = [op_index.get(op.get("operation_id"), op) for op in ops]
        schedule = dict(baseline_schedule)
        schedule["operations"] = refined_ops

        # Refresh aggregates that depend on end times.
        schedule = _recompute_aggregates(schedule)

        return LRHOResult(
            used=True,
            improved=total_ops_moved > 0,
            windows=len(windows),
            ops_rescheduled=total_ops_moved,
            solve_time_s=elapsed,
            schedule=schedule,
            warnings=warnings,
        )

    # ─── Private ──────────────────────────────────────────────────────────

    def _plan_windows(
        self, horizon_start: datetime, horizon_end: datetime,
    ) -> List[Tuple[datetime, datetime]]:
        step = timedelta(days=self.config.step_days)
        span = timedelta(days=self.config.horizon_days)
        windows: List[Tuple[datetime, datetime]] = []
        cursor = horizon_start
        while cursor < horizon_end:
            window_end = min(cursor + span, horizon_end)
            windows.append((cursor, window_end))
            cursor += step
        return windows

    def _solve_window(
        self,
        ops: List[Dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
        frozen_cutoff: datetime,
    ) -> int:
        """Solve one window. Returns how many ops the solver actually moved."""
        if cp_model is None:  # pragma: no cover — guarded at module level
            return 0
        model = cp_model.CpModel()

        # Resolution: minute-granularity is sufficient for NELO scheduling.
        def _minute(dt: datetime) -> int:
            return int((dt - window_start).total_seconds() // 60)

        horizon_minutes = max(1, _minute(window_end))

        interval_vars: Dict[str, Any] = {}
        machine_intervals: Dict[str, list] = {}
        worker_intervals: Dict[str, list] = {}
        mold_intervals: Dict[str, list] = {}

        for op in ops:
            op_id = op.get("operation_id") or ""
            if not op_id:
                continue
            start_dt = _parse_dt(op.get("start"))
            end_dt = _parse_dt(op.get("end"))
            duration_min = int(
                op.get("duration_minutes")
                or ((end_dt - start_dt).total_seconds() / 60 if start_dt and end_dt else 60)
            )
            duration_min = max(1, duration_min)

            if start_dt is None or end_dt is None:
                continue

            # Clamp into the window for interval creation.
            earliest = max(0, _minute(start_dt))
            # Frozen ops: pin via equality.
            is_frozen = start_dt < frozen_cutoff
            domain_start = cp_model.Domain.FromValues([earliest]) if is_frozen \
                else cp_model.Domain.FromIntervals([[0, max(0, horizon_minutes - duration_min)]])
            start_var = model.NewIntVarFromDomain(domain_start, f"s:{op_id}")
            end_var = model.NewIntVar(
                duration_min, horizon_minutes, f"e:{op_id}",
            )
            model.Add(end_var == start_var + duration_min)
            interval = model.NewIntervalVar(start_var, duration_min, end_var, f"i:{op_id}")
            interval_vars[op_id] = (start_var, end_var, interval, duration_min)

            machine_id = op.get("machine_id")
            if machine_id:
                machine_intervals.setdefault(machine_id, []).append(interval)
            for worker_id in op.get("workers") or []:
                worker_intervals.setdefault(worker_id, []).append(interval)
            mold_id = op.get("mold_id")
            if mold_id:
                mold_intervals.setdefault(mold_id, []).append(interval)

        # No-overlap constraints per resource.
        for intervals in machine_intervals.values():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)
        for intervals in worker_intervals.values():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)
        for intervals in mold_intervals.values():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)

        # Minimise makespan (last end).
        if interval_vars:
            makespan = model.NewIntVar(0, horizon_minutes, "makespan")
            for _, end_var, _, _ in interval_vars.values():
                model.Add(makespan >= end_var)
            model.Minimize(makespan)

        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = self.config.solver_threads
        # Per-window budget — share the total equally across expected windows.
        per_window_budget = max(0.5, self.config.budget_s / max(1, len(interval_vars)))
        solver.parameters.max_time_in_seconds = per_window_budget
        status = solver.Solve(model)

        moved = 0
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for op in ops:
                op_id = op.get("operation_id") or ""
                if op_id not in interval_vars:
                    continue
                start_var, end_var, _, duration = interval_vars[op_id]
                new_start_min = solver.Value(start_var)
                new_end_min = solver.Value(end_var)
                new_start = window_start + timedelta(minutes=new_start_min)
                new_end = window_start + timedelta(minutes=new_end_min)
                if new_start != _parse_dt(op.get("start")):
                    moved += 1
                op["start"] = new_start
                op["end"] = new_end
        return moved


def _in_window(
    op: Dict[str, Any], window_start: datetime, window_end: datetime,
) -> bool:
    start = _parse_dt(op.get("start"))
    end = _parse_dt(op.get("end"))
    if start is None or end is None:
        return False
    return start < window_end and end > window_start


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _recompute_aggregates(schedule: Dict[str, Any]) -> Dict[str, Any]:
    ops = schedule.get("operations") or []
    if not ops:
        return schedule
    ends = [_parse_dt(op.get("end")) for op in ops]
    ends = [e for e in ends if e is not None]
    if ends:
        latest = max(ends)
        earliest = min(_parse_dt(op.get("start")) or latest for op in ops)
        schedule["makespan_hours"] = round(
            (latest - earliest).total_seconds() / 3600.0, 2,
        )
    return schedule
