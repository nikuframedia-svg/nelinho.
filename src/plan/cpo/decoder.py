"""ProdPlan ONE — CPO v4 Heuristic Decoder (façade, Q.67.6.B3).

Turns a `Chromosome` into a feasible schedule, honouring precedences,
machine/worker/mould no-overlap, Sprint I.4 multi-pocket mould batching,
and the curing-gap chemistry. Deterministic for fixed inputs.

Split into three siblings; `decode()` orchestrates them:
  * `decoder_helpers.py`   — constants, ScheduledOp, mould batches, dicts
  * `decoder_resources.py` — precedence/earliest-start, resource selection,
                             main scheduling loop
  * `decoder_kpis.py`      — makespan, tardiness, OTD, idle, MAP-Elites
                             axes, throughput €/day

Public API is identical to the pre-split monolith: `decode`,
`compute_mold_batches`, `classify_rework_phase`, every constant, and
every test-touched helper are re-exported here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Union

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder_helpers import (
    DEFAULT_POST_DESMOLDE_BUFFER_MINUTES,
    DEFAULT_QUEUE_TIME_MINUTES,
    DEFAULT_REWORK_BUFFER_PCT,
    POST_DESMOLDE_PHASE_NAMES,
    REWORK_BUFFER_PHASE_KEYWORDS,
    ScheduledOp,
    _compute_target_starts,
    _empty_result,
    _estimate_utilization,
    _is_desmolde,
    _last_on_machine_has_different_family,
    _pocket_count,
    _scheduled_to_dict,
    classify_rework_phase,
    compute_mold_batches,
)
from src.plan.cpo.decoder_kpis import (
    _compute_idle_metrics,
    _compute_makespan_hours,
    _compute_mapelites_axes,
    _compute_otd_delivery,
    _compute_tardiness,
    _compute_throughput,
)
from src.plan.cpo.decoder_resources import (
    _earliest_start,
    _pick_workers,
    _precedences_met,
    _run_scheduling_loop,
    _sanitise_permutation,
)
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

# Public API + re-exports for tests (Q.67.6.B3 split).
__all__ = [
    "decode", "compute_mold_batches", "classify_rework_phase", "ScheduledOp",
    "DEFAULT_QUEUE_TIME_MINUTES", "DEFAULT_POST_DESMOLDE_BUFFER_MINUTES",
    "DEFAULT_REWORK_BUFFER_PCT", "POST_DESMOLDE_PHASE_NAMES",
    "REWORK_BUFFER_PHASE_KEYWORDS",
    "_empty_result", "_estimate_utilization", "_is_desmolde",
    "_last_on_machine_has_different_family", "_pocket_count",
    "_scheduled_to_dict", "_compute_target_starts", "_earliest_start",
    "_pick_workers", "_precedences_met",
]


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

    Knobs (all `None`-default, legacy-safe):
    * `queue_time_minutes` (Sprint P.8 / PL22) — soft inter-phase gap.
    * `post_desmolde_buffer_minutes` (Sprint P.9 / PL21) — slack after
      Desmolde phases to absorb rework.
    * `product_price_eur` (Sprint A F1) — product_id → sale price; needed
      to populate `throughput_eur_day` toward the €30-35K/day target.

    Returns a `SchedulingResult`-shaped dict (operations, makespan_hours,
    total_tardiness_hours, num_late_orders, setups, throughput_eur_day,
    warnings, infeasible_op_ids, …).
    """
    # Phase 1 — empty short-circuits.
    queue_gap = timedelta(minutes=queue_time_minutes or 0.0)
    post_desmolde_extra = timedelta(minutes=post_desmolde_buffer_minutes or 0.0)
    if not operations:
        return _empty_result(horizon_start)
    machine_ids = [m.machine_id for m in machines]
    if not machine_ids:
        return _empty_result(horizon_start, warnings=["No machines available"])

    # Phase 2 — sanitise permutation (warn on out-of-range/dup/missing).
    priority_order = _sanitise_permutation(chromosome, operations)

    # Phase 3 — intra-order precedence: group + sort by sequence.
    order_to_ops: Dict[str, List[SchedulingOperation]] = defaultdict(list)
    for op in operations:
        order_to_ops[op.order_id].append(op)
    for ops in order_to_ops.values():
        ops.sort(key=lambda o: o.sequence)

    # Phase 4 — pre-compute mould-batch assignments (Sprint I.4).
    mold_batches = compute_mold_batches(operations, state)
    batch_members: Dict[str, List[SchedulingOperation]] = defaultdict(list)
    for op in operations:
        batch_id = mold_batches.get(op.operation_id)
        if batch_id:
            batch_members[batch_id].append(op)
    op_by_id: Dict[str, SchedulingOperation] = {
        op.operation_id: op for op in operations
    }

    # Sprint A D4 — pre-compute latest-start anchors for backwards scheduling.
    is_backward = getattr(chromosome, "schedule_direction", "forward") == "backward"
    target_starts = (
        _compute_target_starts(order_to_ops, state) if is_backward else {}
    )

    # Phases 5-8 — main scheduling loop (resource selection + timelines).
    loop = _run_scheduling_loop(
        chromosome=chromosome,
        priority_order=priority_order,
        order_to_ops=order_to_ops,
        op_by_id=op_by_id,
        mold_batches=mold_batches,
        batch_members=batch_members,
        machine_ids=machine_ids,
        state=state,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        queue_gap=queue_gap,
        post_desmolde_extra=post_desmolde_extra,
        is_backward=is_backward,
        target_starts=target_starts,
    )

    # Phase 9 — KPI accumulation.
    makespan_hours = _compute_makespan_hours(loop.scheduled, horizon_start)
    tardy_hours, late_orders, due_by_order = _compute_tardiness(
        loop.scheduled, operations,
    )
    total_idle_hours, idle_ratio = _compute_idle_metrics(
        loop.scheduled, horizon_start, horizon_end,
    )
    lam_utilization, tardiness_transport_d, idle_pct = _compute_mapelites_axes(
        loop.scheduled, tardy_hours, idle_ratio,
    )
    throughput_total_eur, throughput_eur_day = _compute_throughput(
        loop.scheduled, operations, horizon_start, horizon_end, product_price_eur,
    )
    otd_delivery = _compute_otd_delivery(due_by_order, late_orders)

    # Phase 10 — soft-horizon coherence: success only if every op fit.
    return {
        "success": not loop.infeasible,
        "engine_used": "cpo_v4",
        "operations": [_scheduled_to_dict(s) for s in loop.scheduled],
        "makespan_hours": round(makespan_hours, 2),
        "total_tardiness_hours": round(tardy_hours, 2),
        "num_late_orders": late_orders,
        "otd_delivery": round(otd_delivery, 4),
        "setups": loop.setups,
        "routing_variants_applied": loop.routing_variants_applied,
        "backwards_shifts": loop.backwards_shifts,
        "total_idle_hours": round(total_idle_hours, 2),
        "idle_ratio": round(idle_ratio, 4),
        # Sprint A ME1 — Blueprint v2.0 MAP-Elites axes
        "lam_utilization": round(lam_utilization, 2),
        "idle_pct": round(idle_pct, 2),
        "tardiness_transport_d": round(tardiness_transport_d, 2),
        "throughput_eur_total": round(throughput_total_eur, 2),
        "throughput_eur_day": round(throughput_eur_day, 2),
        "avg_utilization": _estimate_utilization(
            loop.scheduled, machines, horizon_start, horizon_end,
        ),
        "warnings": loop.warnings,
        "infeasible_op_ids": loop.infeasible,
    }
