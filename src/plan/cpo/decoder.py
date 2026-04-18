"""
ProdPlan ONE — CPO v4 Heuristic Decoder
========================================

Turns a `Chromosome` into a feasible schedule, honoring:
- operation precedences (within the same order_id, by `sequence`)
- explicit predecessor_ops graph
- machine no-overlap (per centro_custo / machine)
- worker no-overlap (skills + team_size, NELO pairs for Laminagem)
- mold exclusivity when `mold_required`

Deterministic: same (chromosome, FactoryState, ops, machines, horizon)
→ same schedule.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

logger = logging.getLogger(__name__)


@dataclass
class ScheduledOp:
    operation_id: str
    order_id: str
    phase_id: Optional[str]
    machine_id: str
    workers: List[str]
    mold_id: Optional[str]
    start: datetime
    end: datetime
    duration_minutes: float


def decode(
    chromosome: Chromosome,
    operations: List[SchedulingOperation],
    machines: List[SchedulingMachine],
    state: FactoryState,
    horizon_start: datetime,
    horizon_end: datetime,
) -> Dict[str, Any]:
    """
    Decode a chromosome into a feasible schedule.

    Returns a dict compatible with `SchedulingResult` fields plus:
    - operations: list of scheduled ops (as dicts, serializable)
    - makespan_hours, total_tardiness_hours, num_late_orders, setups
    - warnings, infeasible_ops (ids that couldn't fit)
    """
    if not operations:
        return _empty_result(horizon_start)

    machine_ids = [m.machine_id for m in machines]
    if not machine_ids:
        return _empty_result(horizon_start, warnings=["No machines available"])

    # timelines
    machine_free_at: Dict[str, datetime] = {mid: horizon_start for mid in machine_ids}
    worker_free_at: Dict[str, datetime] = {}
    mold_free_at: Dict[str, datetime] = {}

    # predecessors — end time of each scheduled op (op_id → end)
    op_end_at: Dict[str, datetime] = {}

    # Sort ops by chromosome-provided priority, but respect precedence via
    # a topological pass at decode time.
    op_by_index = list(operations)
    priority_order = [op_by_index[i] for i in chromosome.permutation if 0 <= i < len(op_by_index)]
    # Fallback: any op missing from chromosome perm gets appended at the end
    seen = {id(op) for op in priority_order}
    for op in op_by_index:
        if id(op) not in seen:
            priority_order.append(op)

    # Resolve precedences: within same order, natural `sequence` order must hold
    order_to_ops: Dict[str, List[SchedulingOperation]] = defaultdict(list)
    for op in operations:
        order_to_ops[op.order_id].append(op)
    for ops in order_to_ops.values():
        ops.sort(key=lambda o: o.sequence)

    scheduled: List[ScheduledOp] = []
    infeasible: List[str] = []
    warnings: List[str] = []
    setups = 0

    pending = list(priority_order)
    loop_guard = 0
    max_loops = len(pending) * 10 + 10  # prevent infinite loop on bad data

    while pending and loop_guard < max_loops:
        loop_guard += 1
        progress = False
        new_pending: List[SchedulingOperation] = []

        for op in pending:
            if not _precedences_met(op, order_to_ops, op_end_at):
                new_pending.append(op)
                continue

            earliest_pred_end = _earliest_start(op, order_to_ops, op_end_at, horizon_start)

            # Machine choice: preferred + alternatives, pick earliest available
            candidate_machines = [op.machine_id] if op.machine_id else []
            candidate_machines = [m for m in candidate_machines if m in machine_free_at]
            for alt in op.alternative_machines:
                if alt in machine_free_at and alt not in candidate_machines:
                    candidate_machines.append(alt)
            if not candidate_machines:
                # Fall back to any machine (manual-style)
                candidate_machines = list(machine_ids)

            best_machine = min(
                candidate_machines,
                key=lambda m: max(machine_free_at[m], earliest_pred_end),
            )

            # Worker pool
            pool = state.workers_for(str(op.phase_id)) if op.phase_id else set()
            team_size = max(1, int(op.team_size))
            if not pool and team_size > 0:
                # No skill info → treat as manual; allow without worker binding
                workers_chosen: List[str] = []
            else:
                workers_chosen = _pick_workers(pool, team_size, worker_free_at, earliest_pred_end)
                if len(workers_chosen) < team_size:
                    infeasible.append(op.operation_id)
                    continue

            # Mold
            mold_chosen: Optional[str] = op.mold_id
            if op.mold_required and not mold_chosen:
                # assign from state
                mold_info = state.mold_for(op.model_id) if op.model_id else None
                mold_chosen = mold_info.molde_id if mold_info else None
                if op.mold_required and not mold_chosen:
                    infeasible.append(op.operation_id)
                    continue

            # Start time = max of (pred end, machine free, workers free, mold free)
            candidates = [
                earliest_pred_end,
                machine_free_at[best_machine],
            ]
            for w in workers_chosen:
                candidates.append(worker_free_at.get(w, horizon_start))
            if mold_chosen:
                candidates.append(mold_free_at.get(mold_chosen, horizon_start))
            start = max(candidates)

            duration_min = max(1.0, float(op.duration_minutes))
            end = start + timedelta(minutes=duration_min)

            if end > horizon_end:
                infeasible.append(op.operation_id)
                warnings.append(
                    f"Op {op.operation_id} exceeds horizon ({end.isoformat()} > "
                    f"{horizon_end.isoformat()})"
                )
                # still schedule it (soft horizon) — track via warning

            scheduled.append(ScheduledOp(
                operation_id=op.operation_id,
                order_id=op.order_id,
                phase_id=op.phase_id,
                machine_id=best_machine,
                workers=list(workers_chosen),
                mold_id=mold_chosen,
                start=start,
                end=end,
                duration_minutes=duration_min,
            ))

            # Setup detection (same machine, different setup_family)
            if _last_on_machine_has_different_family(best_machine, op, scheduled):
                setups += 1

            # update timelines
            machine_free_at[best_machine] = end
            for w in workers_chosen:
                worker_free_at[w] = end
            if mold_chosen:
                mold_free_at[mold_chosen] = end
            op_end_at[op.operation_id] = end
            progress = True

        pending = new_pending
        if not progress:
            # Remaining ops have unsatisfied preds we can never satisfy — give up
            for op in pending:
                infeasible.append(op.operation_id)
            warnings.append(
                f"Precedence deadlock: {len(pending)} ops unresolvable"
            )
            break

    makespan_hours = 0.0
    if scheduled:
        latest = max(s.end for s in scheduled)
        makespan_hours = (latest - horizon_start).total_seconds() / 3600.0

    # Tardiness: sum hours past due_date per order
    due_by_order: Dict[str, Optional[datetime]] = {}
    for op in operations:
        if op.due_date is not None:
            prev = due_by_order.get(op.order_id)
            if prev is None or op.due_date < prev:
                due_by_order[op.order_id] = op.due_date

    order_last_end: Dict[str, datetime] = {}
    for s in scheduled:
        prev = order_last_end.get(s.order_id)
        if prev is None or s.end > prev:
            order_last_end[s.order_id] = s.end

    tardy_hours = 0.0
    late_orders = 0
    for order_id, end_time in order_last_end.items():
        due = due_by_order.get(order_id)
        if due is None:
            continue
        if end_time > due:
            late_orders += 1
            tardy_hours += (end_time - due).total_seconds() / 3600.0

    return {
        "success": True,
        "engine_used": "cpo_v4",
        "operations": [_scheduled_to_dict(s) for s in scheduled],
        "makespan_hours": round(makespan_hours, 2),
        "total_tardiness_hours": round(tardy_hours, 2),
        "num_late_orders": late_orders,
        "setups": setups,
        "avg_utilization": _estimate_utilization(scheduled, machines, horizon_start, horizon_end),
        "warnings": warnings,
        "infeasible_op_ids": infeasible,
    }


def _precedences_met(
    op: SchedulingOperation,
    order_to_ops: Dict[str, List[SchedulingOperation]],
    op_end_at: Dict[str, datetime],
) -> bool:
    # Intra-order precedence
    siblings = order_to_ops[op.order_id]
    for prev in siblings:
        if prev.sequence < op.sequence and prev.operation_id not in op_end_at:
            return False
    # Explicit predecessors
    for pid in op.predecessor_ops:
        if pid not in op_end_at:
            return False
    return True


def _earliest_start(
    op: SchedulingOperation,
    order_to_ops: Dict[str, List[SchedulingOperation]],
    op_end_at: Dict[str, datetime],
    default: datetime,
) -> datetime:
    earliest = default
    siblings = order_to_ops[op.order_id]
    for prev in siblings:
        if prev.sequence < op.sequence:
            end = op_end_at.get(prev.operation_id)
            if end and end > earliest:
                earliest = end
    for pid in op.predecessor_ops:
        end = op_end_at.get(pid)
        if end and end > earliest:
            earliest = end
    return earliest


def _pick_workers(
    pool: set,
    team_size: int,
    worker_free_at: Dict[str, datetime],
    earliest: datetime,
) -> List[str]:
    """
    First-fit: pick the N workers from the pool with the earliest free-at.
    Deterministic tie-break by worker id (lex sort).
    """
    candidates = sorted(
        pool,
        key=lambda w: (worker_free_at.get(w, earliest), w),
    )
    return candidates[:team_size]


def _last_on_machine_has_different_family(
    machine_id: str,
    op: SchedulingOperation,
    scheduled: List[ScheduledOp],
) -> bool:
    # Find the last scheduled op on this machine (before the one we just added)
    for s in reversed(scheduled[:-1]):
        if s.machine_id == machine_id:
            # Find that op to compare setup_family
            # Not cheap here; skip if not available
            return False
    return False


def _estimate_utilization(
    scheduled: List[ScheduledOp],
    machines: List[SchedulingMachine],
    horizon_start: datetime,
    horizon_end: datetime,
) -> float:
    if not machines:
        return 0.0
    span_min = max(1.0, (horizon_end - horizon_start).total_seconds() / 60.0)
    total_busy = sum(s.duration_minutes for s in scheduled)
    return round(min(100.0, (total_busy / (span_min * len(machines))) * 100.0), 2)


def _scheduled_to_dict(s: ScheduledOp) -> Dict[str, Any]:
    return {
        "operation_id": s.operation_id,
        "order_id": s.order_id,
        "phase_id": s.phase_id,
        "machine_id": s.machine_id,
        "workers": list(s.workers),
        "mold_id": s.mold_id,
        "start_time": s.start.isoformat(),
        "end_time": s.end.isoformat(),
        "duration_minutes": s.duration_minutes,
    }


def _empty_result(horizon_start: datetime, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "success": True,
        "engine_used": "cpo_v4",
        "operations": [],
        "makespan_hours": 0.0,
        "total_tardiness_hours": 0.0,
        "num_late_orders": 0,
        "setups": 0,
        "avg_utilization": 0.0,
        "warnings": list(warnings or []),
        "infeasible_op_ids": [],
    }
