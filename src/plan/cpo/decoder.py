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
from src.plan.cpo.decoder_kpis import build_result_dict
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
    boost_inputs: Optional[Mapping[str, int]] = None,  # Q.116.D — work_order_id → effective_boost
    start_floors: Optional[Mapping[str, datetime]] = None,  # Q.174.F6 — pisos por op
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
    # Q.116.D — boost_inputs (work_order_id → effective_boost) re-ordena
    # o priority_order ANTES do loop principal, sem violar axiomas.
    boost_map: Optional[Dict[str, int]] = None
    if boost_inputs:
        boost_map = {str(k): int(v) for k, v in boost_inputs.items() if v}
    priority_order = _sanitise_permutation(
        chromosome, operations, effective_boost=boost_map,
    )

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
        start_floors=start_floors,  # Q.174.F6 — pisos (materiais/componentes)
    )

    # Phase 9-10 — KPI accumulation + result dict. Q.166.F: extraído para
    # decoder_kpis.build_result_dict (reusado pelo caminho CP-SAT; comportamento
    # idêntico — mesmas chaves e arredondamentos).
    return build_result_dict(
        loop.scheduled, operations, machines, horizon_start, horizon_end,
        product_price_eur=product_price_eur,
        setups=loop.setups,
        warnings=loop.warnings,
        infeasible_op_ids=loop.infeasible,
        blocked_ops=loop.blocked,  # Q.174.F5
        routing_variants_applied=loop.routing_variants_applied,
        backwards_shifts=loop.backwards_shifts,
        engine_used="cpo_v4",
    )
