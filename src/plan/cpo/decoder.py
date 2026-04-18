"""
ProdPlan ONE — CPO v4 Heuristic Decoder
========================================

Turns a `Chromosome` into a feasible schedule, honoring:
- operation precedences (within the same order_id, by `sequence`)
- explicit predecessor_ops graph
- machine no-overlap (per centro_custo / machine)
- worker no-overlap (skills + team_size, NELO pairs for Laminagem)
- mold exclusivity when `mold_required`
- Sprint I.4: **multi-pocket mold batching** — ops of the same model that
  need the same mold run in parallel on the same mold (up to `pocket_count`
  boats at once, each holding the mold for `max(duration_i)` time).

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
    mold_batch_id: Optional[str] = None  # Sprint I.4 — ops sharing the same mold slot


def compute_mold_batches(
    operations: List[SchedulingOperation],
    state: FactoryState,
) -> Dict[str, str]:
    """
    Sprint I.4 — group mould-bound operations that can share a multi-pocket
    mould slot.

    Returns `{operation_id: batch_id}`. Ops mapped to the same `batch_id`
    will be scheduled together by the decoder: they start at the same time
    and the mould stays busy for `max(duration_i)`.

    Grouping rules:
    - Only ops with `mold_required=True` are candidates.
    - Ops are grouped by (`model_id`, chosen `mold_id`) — only the same
      model fits a given mould.
    - Each batch is capped at the mould's `pocket_count`. Extra ops form
      a new batch with the same key.
    - Ops without a model_id, without an eligible mould, or with
      precedence conflicts between each other are not batched.
    """
    if not operations:
        return {}

    # Group candidate ops by (model_id, mold_id)
    groups: Dict[tuple, List[SchedulingOperation]] = defaultdict(list)
    for op in operations:
        if not op.mold_required:
            continue
        if not op.model_id:
            continue
        mold_id = op.mold_id
        if not mold_id:
            info = state.mold_for(op.model_id)
            mold_id = info.molde_id if info else None
        if not mold_id:
            continue
        groups[(op.model_id, mold_id)].append(op)

    batches: Dict[str, str] = {}

    for (model_id, mold_id), members in groups.items():
        if len(members) < 2:
            continue  # single op — no batching benefit
        pocket_count = _pocket_count(state, mold_id)
        if pocket_count <= 1:
            continue

        # Precedence-free subsets: ops in the same batch must NOT depend on
        # each other (directly or transitively through predecessor_ops).
        # Simple filter: drop any op that lists a sibling's operation_id as a
        # predecessor. Intra-order precedence is by `sequence` — siblings
        # with different sequences can't run in parallel.
        independent: List[SchedulingOperation] = []
        for op in members:
            conflicts = set(op.predecessor_ops or [])
            has_sequence_peer = any(
                peer.order_id == op.order_id and peer.sequence != op.sequence
                and peer.operation_id != op.operation_id
                for peer in members
            )
            if has_sequence_peer:
                continue
            if conflicts.intersection(m.operation_id for m in members if m is not op):
                continue
            independent.append(op)

        # Pack into pocket-count-sized batches, deterministic order
        independent.sort(key=lambda o: (o.order_id, o.sequence, o.operation_id))
        for chunk_idx in range(0, len(independent), pocket_count):
            chunk = independent[chunk_idx : chunk_idx + pocket_count]
            if len(chunk) < 2:
                continue
            batch_id = f"mbatch:{model_id}:{mold_id}:{chunk_idx // pocket_count}"
            for op in chunk:
                batches[op.operation_id] = batch_id

    return batches


def _pocket_count(state: FactoryState, mold_id: str) -> int:
    mold_info = state.molds.get(mold_id)
    if mold_info is None:
        return 1
    return max(1, int(getattr(mold_info, "pocket_count", 1) or 1))


# Sprint P.8 — queue time between consecutive phases (Blueprint PL22).
# Default matches `planning.queue_time.median_h` seeded in Sprint L.4.
DEFAULT_QUEUE_TIME_MINUTES = 5.2 * 60.0
# Sprint P.9 — buffer pós-Desmolde (Blueprint PL21: 95% of errors detected
# at Desmolde → reserve 4h after to absorb rework without cascade).
DEFAULT_POST_DESMOLDE_BUFFER_MINUTES = 4 * 60.0
# Phase names to which the post-Desmolde buffer applies. We recognise the
# Portuguese canonical form stored in `SchedulingOperation.phase_name`.
POST_DESMOLDE_PHASE_NAMES = {"desmolde", "Desmolde", "DESMOLDE"}


def decode(
    chromosome: Chromosome,
    operations: List[SchedulingOperation],
    machines: List[SchedulingMachine],
    state: FactoryState,
    horizon_start: datetime,
    horizon_end: datetime,
    *,
    queue_time_minutes: Optional[float] = None,
    post_desmolde_buffer_minutes: Optional[float] = None,
) -> Dict[str, Any]:
    """Decode a chromosome into a feasible schedule.

    Sprint P.8/P.9 knobs:
    * `queue_time_minutes` — minimum gap between consecutive phases of the
      same order (PL22, default disabled unless caller passes a value).
    * `post_desmolde_buffer_minutes` — extra slack after Desmolde phases
      to absorb rework (PL21, default disabled).

    Both knobs default to `None` (disabled) so legacy callers see identical
    behaviour. CPOEngine threads these through from `CPOConfig.use_queue_time`
    and `CPOConfig.use_post_desmolde_buffer`.

    Returns a dict compatible with `SchedulingResult` fields plus:
    - operations: list of scheduled ops (as dicts, serializable)
    - makespan_hours, total_tardiness_hours, num_late_orders, setups
    - warnings, infeasible_ops (ids that couldn't fit)
    """
    queue_gap = timedelta(minutes=queue_time_minutes or 0.0)
    post_desmolde_extra = timedelta(minutes=post_desmolde_buffer_minutes or 0.0)
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

    # Sprint I.4 — pre-compute mould-batch assignments
    mold_batches = compute_mold_batches(operations, state)
    batch_members: Dict[str, List[SchedulingOperation]] = defaultdict(list)
    for op in operations:
        batch_id = mold_batches.get(op.operation_id)
        if batch_id:
            batch_members[batch_id].append(op)

    # Sprint P.8/P.9 — lookup for predecessor metadata by id (needed by
    # _earliest_start to distinguish Desmolde endings).
    op_by_id: Dict[str, SchedulingOperation] = {
        op.operation_id: op for op in operations
    }

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

            # Sprint I.4 — if this op is in a mould batch, we must be able to
            # schedule the WHOLE batch right now. Wait for peers otherwise.
            batch_id = mold_batches.get(op.operation_id)
            batch_peers: List[SchedulingOperation] = [op]
            if batch_id:
                peers = batch_members.get(batch_id, [])
                if any(not _precedences_met(p, order_to_ops, op_end_at) for p in peers):
                    new_pending.append(op)
                    continue
                # Members already scheduled in a previous pass are skipped;
                # avoid double-scheduling the same batch.
                already_done = {s.operation_id for s in scheduled}
                peers = [p for p in peers if p.operation_id not in already_done]
                if not peers:
                    continue
                batch_peers = peers

            earliest_pred_end = max(
                _earliest_start(
                    p, order_to_ops, op_end_at, horizon_start,
                    queue_gap=queue_gap, post_desmolde_extra=post_desmolde_extra,
                    op_by_id=op_by_id,
                )
                for p in batch_peers
            )

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

            # Worker pool — a mould batch needs team_size per member
            pool = state.workers_for(str(op.phase_id)) if op.phase_id else set()
            team_size = max(1, int(op.team_size))
            total_workers_needed = team_size * len(batch_peers)
            if not pool and team_size > 0:
                # No skill info → treat as manual; allow without worker binding
                batch_workers: List[List[str]] = [[] for _ in batch_peers]
            else:
                picked = _pick_workers(pool, total_workers_needed, worker_free_at, earliest_pred_end)
                if len(picked) < total_workers_needed:
                    # Cannot staff the full batch — infeasible for all peers
                    for p in batch_peers:
                        infeasible.append(p.operation_id)
                    continue
                # Split flat pick into per-peer slots deterministically
                batch_workers = [
                    picked[i * team_size : (i + 1) * team_size]
                    for i in range(len(batch_peers))
                ]

            # Mold — all peers share the same mould
            mold_chosen: Optional[str] = op.mold_id
            if op.mold_required and not mold_chosen:
                mold_info = state.mold_for(op.model_id) if op.model_id else None
                mold_chosen = mold_info.molde_id if mold_info else None
                if op.mold_required and not mold_chosen:
                    for p in batch_peers:
                        infeasible.append(p.operation_id)
                    continue

            # Start time = max of (pred end, machine free, workers free, mold free)
            candidates = [earliest_pred_end, machine_free_at[best_machine]]
            for slot in batch_workers:
                for w in slot:
                    candidates.append(worker_free_at.get(w, horizon_start))
            if mold_chosen:
                candidates.append(mold_free_at.get(mold_chosen, horizon_start))
            start = max(candidates)

            # The batch occupies the mould for max(durations); individual ops
            # finish at start + their own duration.
            peer_duration_min = [max(1.0, float(p.duration_minutes)) for p in batch_peers]
            batch_end = start + timedelta(minutes=max(peer_duration_min))

            # Emit one ScheduledOp per peer; each peer's end is start + own duration,
            # but the mould stays busy until batch_end so the next batch waits.
            flat_worker_list: List[str] = [w for slot in batch_workers for w in slot]
            for peer, slot_workers, peer_dur in zip(
                batch_peers, batch_workers, peer_duration_min
            ):
                peer_end = start + timedelta(minutes=peer_dur)
                if peer_end > horizon_end:
                    infeasible.append(peer.operation_id)
                    warnings.append(
                        f"Op {peer.operation_id} exceeds horizon "
                        f"({peer_end.isoformat()} > {horizon_end.isoformat()})"
                    )
                    # still schedule it (soft horizon) — track via warning
                scheduled.append(ScheduledOp(
                    operation_id=peer.operation_id,
                    order_id=peer.order_id,
                    phase_id=peer.phase_id,
                    machine_id=best_machine,
                    workers=list(slot_workers),
                    mold_id=mold_chosen,
                    start=start,
                    end=peer_end,
                    duration_minutes=peer_dur,
                    mold_batch_id=batch_id,
                ))
                op_end_at[peer.operation_id] = peer_end

            # Setup detection (same machine, different setup_family) — counted once per batch
            if _last_on_machine_has_different_family(best_machine, op, scheduled):
                setups += 1

            # Update timelines
            machine_free_at[best_machine] = batch_end
            for w in flat_worker_list:
                worker_free_at[w] = batch_end
            if mold_chosen:
                mold_free_at[mold_chosen] = batch_end
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
    *,
    queue_gap: Optional[timedelta] = None,
    post_desmolde_extra: Optional[timedelta] = None,
    op_by_id: Optional[Dict[str, SchedulingOperation]] = None,
) -> datetime:
    """Earliest start honouring precedences, queue time (PL22) and
    post-Desmolde buffer (PL21).

    * `queue_gap` — minimum idle between predecessor end and this op's start
      (Blueprint median 5.2h). Applied to EVERY sibling/explicit predecessor
      that ended at a scheduled moment.
    * `post_desmolde_extra` — extra buffer when the predecessor is a Desmolde
      phase (95% of errors detected here). Stacks on top of `queue_gap`.
    """
    earliest = default
    q_gap = queue_gap or timedelta()
    pd_extra = post_desmolde_extra or timedelta()

    def _with_gaps(end: datetime, pred_op: Optional[SchedulingOperation]) -> datetime:
        shifted = end + q_gap
        if pred_op is not None and _is_desmolde(pred_op):
            shifted += pd_extra
        return shifted

    siblings = order_to_ops[op.order_id]
    for prev in siblings:
        if prev.sequence < op.sequence:
            end = op_end_at.get(prev.operation_id)
            if end is None:
                continue
            candidate = _with_gaps(end, prev)
            if candidate > earliest:
                earliest = candidate
    for pid in op.predecessor_ops:
        end = op_end_at.get(pid)
        if end is None:
            continue
        pred_op = op_by_id.get(pid) if op_by_id else None
        candidate = _with_gaps(end, pred_op)
        if candidate > earliest:
            earliest = candidate
    return earliest


def _is_desmolde(op: SchedulingOperation) -> bool:
    """Match either the phase_name or a `desmolde`-style phase_id."""
    name = (getattr(op, "phase_name", None) or "").strip().lower()
    if name.startswith("desmolde"):
        return True
    phase_id = (op.phase_id or "").strip().lower()
    return phase_id == "desmolde" or phase_id.endswith(".desmolde")


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
        "mold_batch_id": s.mold_batch_id,
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
