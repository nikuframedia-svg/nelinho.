"""
ProdPlan ONE — CPO v4 Heuristic Decoder: pure helpers (Q.67.6.B3 split).

Pure helpers extracted from `decoder.py` so the façade stays under 200L.
No side-effects, no state mutation — these are deterministic functions
keyed off the inputs you pass in.

Grouped here:
- constants (queue/buffer defaults, rework phase keywords)
- `ScheduledOp` dataclass + `_scheduled_to_dict`
- `_pocket_count`, `_is_desmolde`
- `classify_rework_phase` (Sprint R.9 bucket detection)
- `_empty_result` (short-circuit dict for empty input)
- `compute_mold_batches` (Sprint I.4 multi-pocket grouping)
- `_compute_target_starts` (Sprint A D4 backwards anchors)
- `_estimate_utilization` (legacy machine-busy %)
- `_last_on_machine_has_different_family` (setup detection)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


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


def _pocket_count(state: FactoryState, mold_id: str) -> int:
    mold_info = state.molds.get(mold_id)
    if mold_info is None:
        return 1
    return max(1, int(getattr(mold_info, "pocket_count", 1) or 1))


def _is_desmolde(op: SchedulingOperation) -> bool:
    """Match either the phase_name or a `desmolde`-style phase_id."""
    name = (getattr(op, "phase_name", None) or "").strip().lower()
    if name.startswith("desmolde"):
        return True
    phase_id = (op.phase_id or "").strip().lower()
    return phase_id == "desmolde" or phase_id.endswith(".desmolde")


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
    for _order_id, order_ops in order_to_ops.items():
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
        "num_machines": 0,
        "lam_utilization": 0.0,
        "idle_pct": 0.0,
        "tardiness_transport_d": 0.0,
        "throughput_eur_total": 0.0,
        "throughput_eur_day": 0.0,
        "avg_utilization": 0.0,
        "warnings": list(warnings or []),
        "infeasible_op_ids": [],
    }
