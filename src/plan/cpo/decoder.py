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
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.pair_assignment import prefers_pair, requires_pair
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
    setup_family: str = ""  # Sprint A D1 — carried so the setup counter works


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
        pocket_count = _pocket_count(state, mold_id)
        if pocket_count <= 1:
            continue
        if len(members) < 2:
            # Sprint C 4.2 D6 — a single-op batch wastes pocket capacity
            # unless the op is urgent. When the lone candidate has a
            # due_date within URGENCY_DAYS from now, we still emit it
            # as a batch so the mould slot commits (better one boat
            # on-time than six boats late waiting for company).
            op = members[0]
            due = getattr(op, "due_date", None)
            if due is None:
                continue
            # Use the op's own start hint if it's attached (greedy
            # pipeline sets it); otherwise fall back to "now" semantics
            # via datetime.utcnow() which matches the decoder's default.
            now = datetime.utcnow()
            urgency_window = timedelta(days=_MOLD_BATCH_URGENCY_DAYS)
            if due - now > urgency_window:
                continue
            # urgent singleton → fall through to the batching block
            independent: List[SchedulingOperation] = list(members)
            batch_id = f"mbatch:{model_id}:{mold_id}:urgent"
            batches[op.operation_id] = batch_id
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

# Sprint C 4.2 D6 — days until a singleton-on-multi-pocket-mould still
# commits the slot. Shorter = more aggressive (slots lock early, less
# room to accumulate peers); longer = more patient. 3 days maps to the
# NELO factory's typical 2-3 day "in-flight" transport window.
_MOLD_BATCH_URGENCY_DAYS = 3
# Sprint P.9 — buffer pós-Desmolde (Blueprint PL21: 95% of errors detected
# at Desmolde → reserve 4h after to absorb rework without cascade).
DEFAULT_POST_DESMOLDE_BUFFER_MINUTES = 4 * 60.0
# Phase names to which the post-Desmolde buffer applies. We recognise the
# Portuguese canonical form stored in `SchedulingOperation.phase_name`.
POST_DESMOLDE_PHASE_NAMES = {"desmolde", "Desmolde", "DESMOLDE"}

# Sprint R.9 — phases whose rework rate is known-high (QA11). The buffer
# percentages default to config (Sprint L.4 seeded `quality.rework_buffer_pct.*`)
# but are parameterised so decoder callers can stage them.
REWORK_BUFFER_PHASE_KEYWORDS = {
    "sanding_water": ("lixagem água", "lixagem water", "lixagem agua"),
    "sanding_polish": ("lixagem polimento", "lixagem polish"),
    "painting_finishing": ("pintura acabamento", "painting finishing"),
}
DEFAULT_REWORK_BUFFER_PCT = {
    "sanding_water": 0.20,
    "sanding_polish": 0.20,
    "painting_finishing": 0.18,
}


def classify_rework_phase(phase_name: Optional[str], phase_id: Optional[str]) -> Optional[str]:
    """Return the Sprint R.9 bucket key when the phase is rework-heavy."""
    haystack = f"{(phase_name or '').lower()} {(phase_id or '').lower()}"
    for bucket, keywords in REWORK_BUFFER_PHASE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return bucket
    return None


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
    product_price_eur: Optional[Mapping[str, Union[float, Decimal]]] = None,
) -> Dict[str, Any]:
    """Decode a chromosome into a feasible schedule.

    Sprint P.8/P.9 knobs:
    * `queue_time_minutes` — minimum gap between consecutive phases of the
      same order (PL22, default disabled unless caller passes a value).
    * `post_desmolde_buffer_minutes` — extra slack after Desmolde phases
      to absorb rework (PL21, default disabled).

    Sprint A F1 knob:
    * `product_price_eur` — mapping product_id → sale price (€). When
      provided, the schedule's `throughput_eur_day` is computed as the
      total revenue of final-phase ops divided by horizon days. Without
      it (legacy callers), `throughput_eur_day` stays at 0 and the fitness
      weight for throughput has no effect — the CEO's €30-35K/day target
      needs this mapping populated to be actually optimised.

    Both knobs default to `None` (disabled) so legacy callers see identical
    behaviour. CPOEngine threads these through from `CPOConfig.use_queue_time`
    and `CPOConfig.use_post_desmolde_buffer`.

    Returns a dict compatible with `SchedulingResult` fields plus:
    - operations: list of scheduled ops (as dicts, serializable)
    - makespan_hours, total_tardiness_hours, num_late_orders, setups
    - throughput_eur_day, throughput_eur_total (Sprint A F1)
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
    n = len(op_by_index)

    # FASE 1A.3 (CRIT-10) — validate the chromosome's permutation up front
    # and surface any anomaly via WARN. The previous list comprehension
    # silently dropped out-of-bounds indices (ops disappear) and accepted
    # duplicates (same op processed twice). Both can mask GA operator bugs.
    perm = list(chromosome.permutation)
    out_of_range = [i for i in perm if not (0 <= i < n)]
    duplicates = len(perm) - len(set(perm))
    missing = n - len({i for i in perm if 0 <= i < n})
    if out_of_range or duplicates or missing or len(perm) != n:
        logger.warning(
            "decoder: malformed chromosome permutation "
            "(n=%d, perm_len=%d, out_of_range=%d, duplicates=%d, missing=%d) — "
            "deduplicating and appending missing ops in natural order",
            n, len(perm), len(out_of_range), duplicates, missing,
        )

    # Build priority_order: take each in-range index at most once, in chromosome
    # order. Anything left over is appended in natural index order so every op
    # is scheduled exactly once.
    priority_order: List[SchedulingOperation] = []
    seen_idx: set = set()
    for i in perm:
        if 0 <= i < n and i not in seen_idx:
            priority_order.append(op_by_index[i])
            seen_idx.add(i)
    for i in range(n):
        if i not in seen_idx:
            priority_order.append(op_by_index[i])
            seen_idx.add(i)

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
    routing_variants_applied = 0  # Sprint A C1 — ops where variant B picked alt machine
    backwards_shifts = 0  # Sprint A D4 — ops placed later than earliest because of target_start

    # Sprint A D4 — pre-compute latest-start anchors for backwards scheduling.
    # Only used when the chromosome requests backward direction; computed
    # unconditionally because it's cheap (walks orders once) and the anchors
    # are also useful for diagnostics.
    is_backward = getattr(chromosome, "schedule_direction", "forward") == "backward"
    target_starts = (
        _compute_target_starts(order_to_ops, state) if is_backward else {}
    )
    max_op_start = horizon_end - timedelta(minutes=1)  # leave room for duration

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
                    op_by_id=op_by_id, state=state,
                )
                for p in batch_peers
            )

            # Machine choice: preferred + alternatives, pick earliest available.
            # Sprint A C1 — when the chromosome routes this op to variant "B"
            # and the op has alternative_machines, invert the priority so the
            # alt machine is tried first. This is what actually lets the GA
            # optimise routing A/B: same op, different machine path, different
            # downstream makespan/quality trade-off.
            op_variant = chromosome.routing_variant(op.operation_id)
            primary_first = [op.machine_id] if op.machine_id else []
            alt_pool = [
                alt for alt in op.alternative_machines
                if alt not in primary_first
            ]
            if op_variant == "B" and alt_pool:
                ordered_candidates = alt_pool + primary_first
            else:
                ordered_candidates = primary_first + alt_pool

            candidate_machines = [
                m for m in ordered_candidates if m in machine_free_at
            ]
            if not candidate_machines:
                # Fall back to any machine (manual-style)
                candidate_machines = list(machine_ids)

            # Tie-break preserves our order — when two machines have the same
            # `earliest available`, variant B's alt stays first.
            best_machine = min(
                candidate_machines,
                key=lambda m: (
                    max(machine_free_at[m], earliest_pred_end),
                    candidate_machines.index(m),
                ),
            )
            if op_variant == "B" and best_machine in alt_pool:
                routing_variants_applied += 1

            # Worker pool — a mould batch needs team_size per member
            pool = state.workers_for(str(op.phase_id)) if op.phase_id else set()
            team_size = max(1, int(op.team_size))
            total_workers_needed = team_size * len(batch_peers)
            if not pool and team_size > 0:
                # No skill info → treat as manual; allow without worker binding.
                # NEW-2: log a warning because this is a SILENT risk — we may
                # be scheduling a phase where nobody in the skill matrix can
                # actually perform it. If the tenant has a skill_matrix and
                # this phase_id simply isn't mapped, that's a config bug.
                skill_matrix = getattr(state, "skill_matrix", None)
                if skill_matrix and op.phase_id:
                    warnings.append(
                        f"No workers in skill_matrix for phase {op.phase_id!r} "
                        f"(op {op.operation_id}); scheduled as manual."
                    )
                    logger.warning(
                        "Phase %r has no eligible workers in skill_matrix — "
                        "op %s scheduled as manual; verify skill seed.",
                        op.phase_id, op.operation_id,
                    )
                batch_workers: List[List[str]] = [[] for _ in batch_peers]
            else:
                picked = _pick_workers(
                    pool, total_workers_needed, worker_free_at, earliest_pred_end,
                    state=state,
                    quality_weight=float(getattr(chromosome, "quality_weight", 0.0) or 0.0),
                )
                if len(picked) < total_workers_needed:
                    # Sprint Q.8 (CEO confirmation 2026-04-26): for PREFERRED-pair
                    # phases (Laminagem post-rule-relax) we accept a solo
                    # assignment when the pair pool is exhausted, instead of
                    # failing the whole batch. The longer per-op duration that
                    # comes from running with one fewer worker is the natural
                    # fitness penalty — no extra weight needed.
                    soft_pair = (
                        team_size > 1
                        and prefers_pair(op, state)
                        and not requires_pair(op, state)
                    )
                    can_downgrade = (
                        soft_pair
                        and len(picked) >= len(batch_peers)
                    )
                    if can_downgrade:
                        warnings.append(
                            f"Pair-preferred phase {op.phase_id!r} "
                            f"(op {op.operation_id}) staffed solo — "
                            f"pool too thin for {total_workers_needed} workers."
                        )
                        team_size = 1
                        total_workers_needed = team_size * len(batch_peers)
                        picked = picked[:total_workers_needed]
                    else:
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
            earliest_feasible = max(candidates)

            # Sprint A D4 — backwards scheduling: for every peer in this batch
            # we may have a precomputed target_start (order.due_date minus
            # downstream durations + curing gaps). When it's later than
            # earliest_feasible, we shift the whole batch to the latest common
            # target so the operation sits as late as possible without
            # violating precedence or resources. When any target is earlier
            # than feasible, precedence wins and nothing moves.
            start = earliest_feasible
            if is_backward:
                peer_targets = [
                    target_starts[p.operation_id]
                    for p in batch_peers
                    if p.operation_id in target_starts
                ]
                if peer_targets:
                    # The batch must start at or after the LATEST target among
                    # its members (so each op still meets its own anchor) but
                    # never later than the horizon minus its own duration.
                    batch_target = min(max(peer_targets), max_op_start)
                    if batch_target > earliest_feasible:
                        start = batch_target
                        backwards_shifts += len(batch_peers)

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
                    setup_family=getattr(peer, "setup_family", "") or "",
                ))
                op_end_at[peer.operation_id] = peer_end

            # Setup detection (same machine, different setup_family) — counted once per batch.
            # Compare the current op against the most recent prior op on the
            # same machine (excluding the ones we just added in this batch).
            if _last_on_machine_has_different_family(
                best_machine, op, scheduled, batch_size=len(batch_peers),
            ):
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

    # Sprint A F2 — worker idle accounting. Each worker seen in the
    # schedule consumed some duration across the horizon; whatever's left
    # is "idle". `idle_ratio` is in [0, 1]; `total_idle_hours` aggregates
    # across every active worker (so it scales with the team size).
    #
    # Only workers that actually appear on a ScheduledOp count in the pool
    # — we don't charge idle for the entire skill matrix (a scheduler can't
    # be "guilty" of not using a worker it wasn't allowed to pick anyway).
    horizon_hours = max(0.01, (horizon_end - horizon_start).total_seconds() / 3600.0)
    worker_busy_minutes: Dict[str, float] = defaultdict(float)
    for s in scheduled:
        share = s.duration_minutes  # each listed worker contributes the op's duration
        for w in s.workers:
            worker_busy_minutes[w] += share

    active_workers = set(worker_busy_minutes)
    n_active_workers = max(1, len(active_workers))
    total_busy_hours = sum(worker_busy_minutes.values()) / 60.0
    total_capacity_hours = n_active_workers * horizon_hours
    total_idle_hours = max(0.0, total_capacity_hours - total_busy_hours)
    idle_ratio = min(1.0, total_idle_hours / total_capacity_hours) if total_capacity_hours > 0 else 0.0

    # Sprint A ME1 — Blueprint v2.0 MAP-Elites axes (x/y/z). The archive's
    # `use_v2_axes=True` mode consumes these three fields directly; without
    # them it falls back to the legacy global utilisation / tardiness_hours
    # / num_late_orders, which is phase-agnostic and groups distinct NELO
    # trade-offs into the same cell.
    #
    #   X — lam_utilization : share of minutes spent in LAMINAGEM* phases
    #                         over total scheduled minutes (in %)
    #   Y — tardiness_transport_d : convert legacy tardy_hours to days
    #   Z — idle_pct        : idle_ratio × 100
    _laminagem_keys = {"LAMINAGEM", "LAMINAGEM_INFUSAO", "LAMINACAO", "LAMINAGEM_STANDARD"}
    lam_busy_minutes = 0.0
    total_scheduled_minutes = 0.0
    for s in scheduled:
        total_scheduled_minutes += s.duration_minutes
        phase_code = (s.phase_id or "").upper().replace(" ", "_")
        if any(k in phase_code for k in _laminagem_keys):
            lam_busy_minutes += s.duration_minutes

    lam_utilization = (
        (lam_busy_minutes / total_scheduled_minutes) * 100.0
        if total_scheduled_minutes > 0 else 0.0
    )
    tardiness_transport_d = tardy_hours / 24.0
    idle_pct = idle_ratio * 100.0

    # Sprint A F1 — throughput €/day. Identify each order's final op
    # (highest sequence within its order), look up the sale price for its
    # product, and divide the total revenue by the number of horizon days.
    throughput_total_eur = 0.0
    throughput_eur_day = 0.0
    if product_price_eur:
        price_lookup: Dict[str, float] = {
            str(pid): float(val) for pid, val in product_price_eur.items()
        }
        # Last op per order by sequence — matches "final phase" semantics
        # without needing a schema-level `is_final_phase` flag.
        final_op_by_order: Dict[str, SchedulingOperation] = {}
        for op in operations:
            current = final_op_by_order.get(op.order_id)
            if current is None or op.sequence > current.sequence:
                final_op_by_order[op.order_id] = op

        scheduled_ids = {s.operation_id for s in scheduled}
        for order_id, final_op in final_op_by_order.items():
            if final_op.operation_id not in scheduled_ids:
                # The final phase never got placed — don't count revenue.
                continue
            price = price_lookup.get(str(final_op.product_id), 0.0)
            if price > 0:
                throughput_total_eur += price

        horizon_seconds = (horizon_end - horizon_start).total_seconds()
        horizon_days = max(1.0, horizon_seconds / 86400.0)
        throughput_eur_day = throughput_total_eur / horizon_days

    # Sprint C 4.2 D7 — soft horizon coherence. Up to now `success=True`
    # was stamped unconditionally even when ops landed beyond the horizon
    # and got recorded as infeasible. That lied to the caller: a partial
    # schedule looked identical to a clean one. Now `success` reflects
    # whether every op fit within the horizon (soft horizon — still
    # scheduled, but flagged) so downstream callers can gate on it.
    success_flag = not infeasible

    # FASE 1B.6 (CRIT-24) — populate otd_delivery so safety_net can
    # actually use it as a guardrail. Without this, the OTD branch in
    # safety_net.is_worse_than_baseline was dead code (33% of the safety
    # net's intended scope). Definition: fraction of orders with a
    # due_date that finished on or before due. Vacuously 1.0 when no
    # order in the run carries a due_date (nothing to be late on).
    n_with_due = len(due_by_order)
    otd_delivery = 1.0 if n_with_due == 0 else 1.0 - (late_orders / n_with_due)

    return {
        "success": success_flag,
        "engine_used": "cpo_v4",
        "operations": [_scheduled_to_dict(s) for s in scheduled],
        "makespan_hours": round(makespan_hours, 2),
        "total_tardiness_hours": round(tardy_hours, 2),
        "num_late_orders": late_orders,
        "otd_delivery": round(otd_delivery, 4),
        "setups": setups,
        "routing_variants_applied": routing_variants_applied,
        "backwards_shifts": backwards_shifts,
        "total_idle_hours": round(total_idle_hours, 2),
        "idle_ratio": round(idle_ratio, 4),
        # Sprint A ME1 — Blueprint v2.0 MAP-Elites axes
        "lam_utilization": round(lam_utilization, 2),
        "idle_pct": round(idle_pct, 2),
        "tardiness_transport_d": round(tardiness_transport_d, 2),
        "throughput_eur_total": round(throughput_total_eur, 2),
        "throughput_eur_day": round(throughput_eur_day, 2),
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
    state: Optional[FactoryState] = None,
) -> datetime:
    """Earliest start honouring precedences, queue time (PL22),
    post-Desmolde buffer (PL21) and curing/drying constraints (§3.8).

    Gap stack applied to every predecessor:
    1. `base_gap = max(queue_gap, state.min_gap_hours(pred→curr))` —
       the curing gap is a physical minimum; queue_gap is the idle
       default. We take whichever is larger, they don't stack.
    2. `+ post_desmolde_extra` if predecessor is Desmolde (PL21 stacks
       on top as a QC-absorption buffer).
    """
    earliest = default
    q_gap = queue_gap or timedelta()
    pd_extra = post_desmolde_extra or timedelta()

    def _phase_of(o: Optional[SchedulingOperation]) -> Optional[str]:
        if o is None:
            return None
        return getattr(o, "phase_name", None) or (o.phase_id or None)

    curr_phase = _phase_of(op)

    def _with_gaps(end: datetime, pred_op: Optional[SchedulingOperation]) -> datetime:
        curing_h = 0.0
        if state is not None and pred_op is not None:
            curing_h = state.min_gap_hours(_phase_of(pred_op), curr_phase)
        curing_gap = timedelta(hours=curing_h) if curing_h > 0 else timedelta()
        # Curing gap (physical) dominates queue gap (soft queue) — take max
        base_gap = q_gap if q_gap >= curing_gap else curing_gap
        shifted = end + base_gap
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


def _compute_target_starts(
    order_to_ops: Dict[str, List[SchedulingOperation]],
    state: FactoryState,
) -> Dict[str, datetime]:
    """Sprint A D4 — compute latest-start anchors for backwards scheduling.

    For every op we walk the order's phase chain in reverse from the last
    op (highest sequence) back to this one, accumulating:

      * the op's own duration
      * each downstream op's duration
      * each downstream curing/drying gap (LAMINAGEM→CURA 15h etc.)

    Then `target_start = order_due_date - accumulated_offset`. Ops whose
    order has no `due_date` are skipped (no target → decoder falls back
    to forward-only semantics for that op).

    Returns `{operation_id: target_start_datetime}`. Only includes ops for
    which we could compute a real target.
    """
    targets: Dict[str, datetime] = {}
    for order_id, order_ops in order_to_ops.items():
        # Latest due_date across the order's ops (first-set wins on ties).
        order_due: Optional[datetime] = None
        for op in order_ops:
            due = getattr(op, "due_date", None)
            if due is None:
                continue
            if order_due is None or due > order_due:
                order_due = due
        if order_due is None:
            continue

        ops_sorted = sorted(order_ops, key=lambda o: o.sequence)
        # Cumulative tail-duration (in hours) starting at each op: includes
        # the op's own duration + everything that comes after + every
        # curing gap between consecutive phases downstream.
        tail_hours: Dict[str, float] = {}
        running = 0.0
        for i in range(len(ops_sorted) - 1, -1, -1):
            op = ops_sorted[i]
            own_h = max(0.0, float(op.duration_minutes)) / 60.0
            gap_h = 0.0
            if i < len(ops_sorted) - 1:
                nxt = ops_sorted[i + 1]
                gap_h = state.min_gap_hours(
                    getattr(op, "phase_name", None) or op.phase_id,
                    getattr(nxt, "phase_name", None) or nxt.phase_id,
                )
            running += own_h + gap_h
            tail_hours[op.operation_id] = running

        for op_id, tail_h in tail_hours.items():
            targets[op_id] = order_due - timedelta(hours=tail_h)
    return targets


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
    *,
    state: Optional[FactoryState] = None,
    quality_weight: float = 0.0,
) -> List[str]:
    """Pick N workers from the pool by blending availability and experience.

    Sprint A D3+D5 — the scoring:

        skill_score       = min(1, state.skill_count(w) / skill_scale)
        availability      = 1 / (1 + hours_until_free)     # 1 ⇒ free now
        combined          = skill_score * quality_weight
                          + availability * (1 - quality_weight)

    * `quality_weight = 0` (legacy) → pure availability ranking, matches
      the pre-fix first-fit behaviour so old tests are unaffected.
    * `quality_weight = 1` → pick the most experienced workers in the
      pool regardless of when they're free (good for high-stakes ops).
    * Anything in between (the chromosome default is 0.3) blends both.

    Ties are broken deterministically by worker id so schedules are
    reproducible across runs.
    """
    if not pool:
        return []

    qw = max(0.0, min(1.0, float(quality_weight)))

    # Pre-compute per-worker skill score once; scale normalises against
    # the busiest worker in the pool so the score stays in [0, 1].
    skill_scores: Dict[str, float] = {}
    if state is not None and qw > 0.0:
        raw_counts = {w: float(state.skill_count(w)) for w in pool}
        max_count = max(raw_counts.values(), default=1.0)
        if max_count <= 0:
            max_count = 1.0
        skill_scores = {w: c / max_count for w, c in raw_counts.items()}

    def _score(worker: str) -> Tuple[float, str]:
        free_at = worker_free_at.get(worker, earliest)
        hours_until_free = max(0.0, (free_at - earliest).total_seconds() / 3600.0)
        availability = 1.0 / (1.0 + hours_until_free)
        skill = skill_scores.get(worker, 0.0)
        combined = skill * qw + availability * (1.0 - qw)
        # Return negative because `sorted(..., reverse=False)` + negation
        # gives us "highest combined first" with worker-id as a stable
        # tie-break.
        return (-combined, worker)

    candidates = sorted(pool, key=_score)
    return candidates[:team_size]


def _last_on_machine_has_different_family(
    machine_id: str,
    op: SchedulingOperation,
    scheduled: List[ScheduledOp],
    *,
    batch_size: int = 1,
) -> bool:
    """Return True when the current op introduces a mold/setup change on
    `machine_id` vs the most recent *different* op previously scheduled on
    that machine (Sprint A D1).

    * A setup is charged **once per batch** — we skip `batch_size` trailing
      ScheduledOps because they were just appended for the current batch.
    * Empty `setup_family` on either side counts as "unknown" and does NOT
      trigger a setup (conservative — avoids inflating setups when the ERP
      hasn't tagged the family yet).
    * First op on a machine never counts as a setup (there's no prior to
      compare against).
    """
    current_family = (getattr(op, "setup_family", "") or "").strip()
    if not current_family:
        return False

    tail_skip = max(0, batch_size)
    # `scheduled` already contains the current batch — walk back past it.
    frontier = scheduled[:-tail_skip] if tail_skip else list(scheduled)

    for prior in reversed(frontier):
        if prior.machine_id != machine_id:
            continue
        prior_family = (prior.setup_family or "").strip()
        if not prior_family:
            # Unknown family on the predecessor — no reliable comparison
            return False
        return prior_family != current_family
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
        "setup_family": s.setup_family,
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
        "routing_variants_applied": 0,
        "backwards_shifts": 0,
        "total_idle_hours": 0.0,
        "idle_ratio": 0.0,
        "lam_utilization": 0.0,
        "idle_pct": 0.0,
        "tardiness_transport_d": 0.0,
        "throughput_eur_total": 0.0,
        "throughput_eur_day": 0.0,
        "avg_utilization": 0.0,
        "warnings": list(warnings or []),
        "infeasible_op_ids": [],
    }
