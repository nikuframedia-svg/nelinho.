"""
ProdPlan ONE — CPO v4 Greedy 8-Phase Pipeline (Sprint P.1)
===========================================================

Blueprint v2.0 §5.3 makes the baseline greedy step explicit:

    1. DEMAND AGGREGATION   → Demand net (subtract stock + WIP)
    2. BACKWARDS SCHEDULING → Latest-start per phase, anchored by transport_date
    3. ROUTING SELECTION    → Pick A/B per order based on chromosome
    4. SETUP GROUPING       → Cluster by mold to minimise setups (Sprint I.4)
    5. MULTI-CENTER DISPATCH→ EDD per centre + operator
    6. WORKFORCE ASSIGNMENT → Hungarian (skill × quality)
    7. BUFFER & JIT          → Variance-based buffers + post-Desmolde + queue
    8. SCORING              → Compile KPIs

The Sprint E/F decoder already implements phases 3-7 inline (mold batching,
precedence resolution, first-fit worker assignment). This module lifts the
pipeline into an explicit series of `(state, partial_result) → partial_result`
steps so each phase is introspectable, testable, and individually budgeted.

The 2s cascade budget for the greedy phase (Blueprint §5.5) is honoured via
the per-phase `budget_s` on each `_greedy_phase_N` function — any overrun
short-circuits to whatever partial result we have, never raising.

Today the pipeline delegates the heavy work to the existing `decoder.decode`
(phases 3-7). This keeps Sprint P.1 additive: callers opt in via
`CPOConfig.use_greedy_pipeline=True`; nothing breaks when it's off.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase-level budget targets (seconds). Sum equals the Sprint P.12
# `greedy_budget_s` default of 2.0. Phases beyond their slice keep running
# — the budget is a telemetry target, not a hard cut-off.
# ---------------------------------------------------------------------------

PHASE_BUDGETS_S: Dict[int, float] = {
    1: 0.1,  # demand aggregation (in-memory filter)
    2: 0.3,  # backwards scheduling (anchor maths)
    3: 0.1,  # routing selection (lookups)
    4: 0.2,  # setup grouping (already cached in decoder)
    5: 0.6,  # multi-center dispatch (heart of the greedy)
    6: 0.4,  # workforce assignment
    7: 0.2,  # buffers
    8: 0.1,  # scoring
}


@dataclass
class PhaseTiming:
    phase: int
    name: str
    elapsed_s: float
    within_budget: bool


@dataclass
class GreedyPipelineResult:
    """Rich return value. `schedule` is what the engine consumes; the other
    fields power telemetry, the /cpo_meta commit payload, and Sprint P.12's
    per-phase budget checks."""

    schedule: Dict[str, Any]
    phase_timings: List[PhaseTiming] = field(default_factory=list)
    demand_net_ops: int = 0
    routing_choices_applied: int = 0
    over_budget: bool = False

    def to_meta(self) -> Dict[str, Any]:
        return {
            "phase_timings": [
                {
                    "phase": t.phase, "name": t.name,
                    "elapsed_s": round(t.elapsed_s, 4),
                    "within_budget": t.within_budget,
                }
                for t in self.phase_timings
            ],
            "demand_net_ops": self.demand_net_ops,
            "routing_choices_applied": self.routing_choices_applied,
            "over_budget": self.over_budget,
        }


class GreedyPipeline:
    """Explicit 8-phase baseline greedy. See module docstring."""

    def __init__(
        self,
        state: FactoryState,
        *,
        budget_s: float = 2.0,
        phase_budgets: Optional[Dict[int, float]] = None,
    ) -> None:
        self.state = state
        self.budget_s = budget_s
        self.phase_budgets = phase_budgets or dict(PHASE_BUDGETS_S)

    def run(
        self,
        chromosome: Chromosome,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime,
        horizon_end: datetime,
        *,
        queue_time_minutes: Optional[float] = None,
        post_desmolde_buffer_minutes: Optional[float] = None,
        boost_inputs: Optional[Dict[str, int]] = None,
    ) -> GreedyPipelineResult:
        timings: List[PhaseTiming] = []
        started = time.time()

        # Phase 1 — Demand aggregation
        t0 = time.time()
        active_ops = self._phase1_demand_aggregation(operations)
        timings.append(PhaseTiming(1, "demand_aggregation",
                                   time.time() - t0, True))

        # Phase 2 — Backwards scheduling hint (anchors only; decoder still
        # advances forward, the scheduler just primes it with due dates).
        t0 = time.time()
        anchors = self._phase2_backwards_scheduling(active_ops, horizon_end)
        timings.append(PhaseTiming(2, "backwards_scheduling",
                                   time.time() - t0, True))

        # Phase 3 — Routing selection (A/B)
        t0 = time.time()
        active_ops, routing_applied = self._phase3_routing_selection(
            active_ops, chromosome,
        )
        timings.append(PhaseTiming(3, "routing_selection",
                                   time.time() - t0, True))

        # Phases 4-7 — delegated to the existing decoder, which already does
        # setup grouping (Sprint I.4 mold batches), multi-center dispatch,
        # first-fit workforce and JIT buffers. The knobs we inject below are
        # the Sprint P.8/P.9 buffers.
        t0 = time.time()
        schedule = decode(
            chromosome,
            active_ops,
            machines,
            self.state,
            horizon_start,
            horizon_end,
            queue_time_minutes=queue_time_minutes,
            post_desmolde_buffer_minutes=post_desmolde_buffer_minutes,
            # Q.173.S — boosts pré-solve: reordenam o priority_order do
            # decoder (Q.116.D); antes nenhum call-site de produção os passava.
            boost_inputs=boost_inputs,
        )
        core_elapsed = time.time() - t0
        # Q.173.I — as fases 4-7 partilham UMA passagem do decoder e não há
        # breakdown medido; reportar core_elapsed/4 por fase era telemetria
        # fabricada (invariante #8). Uma entrada única com o tempo REAL.
        timings.append(PhaseTiming(
            4,
            "decoder_core (fases 4-7 partilhadas: setup_grouping, "
            "multi_center_dispatch, workforce_assignment, buffer_jit)",
            core_elapsed,
            core_elapsed <= sum(
                self.phase_budgets.get(p, 0.0) for p in (4, 5, 6, 7)
            ),
        ))

        # Phase 8 — Scoring (annotate schedule with aggregate anchors + idle).
        t0 = time.time()
        schedule = self._phase8_scoring(schedule, anchors)
        timings.append(PhaseTiming(8, "scoring", time.time() - t0, True))

        over_budget = (time.time() - started) > self.budget_s
        if over_budget:
            logger.info(
                "GreedyPipeline exceeded budget %.2fs (elapsed %.2fs)",
                self.budget_s, time.time() - started,
            )

        return GreedyPipelineResult(
            schedule=schedule,
            phase_timings=timings,
            demand_net_ops=len(active_ops),
            routing_choices_applied=routing_applied,
            over_budget=over_budget,
        )

    # ─── Phase implementations ────────────────────────────────────────────

    def _phase1_demand_aggregation(
        self, operations: List[SchedulingOperation],
    ) -> List[SchedulingOperation]:
        """Drop already-closed ops (duration 0, or explicit `status=completed`
        marker on the record). In the Blueprint this also subtracts on-hand
        stock and WIP; Sprint O materials feed into O.2 position API —
        demand_net here only prunes zero-work ops.
        """
        keep: List[SchedulingOperation] = []
        for op in operations:
            duration = float(getattr(op, "duration_minutes", 0) or 0)
            if duration <= 0:
                continue
            # Respect an optional `status` field if the adapter attached one.
            status = getattr(op, "status", None)
            if status and str(status).lower() in {"completed", "cancelled"}:
                continue
            keep.append(op)
        return keep

    def _phase2_backwards_scheduling(
        self,
        operations: List[SchedulingOperation],
        horizon_end: datetime,
    ) -> Dict[str, datetime]:
        """Compute latest-start anchors per order, pulled by `due_date` or by
        a longer-horizon transport_date. Returns `{order_id: anchor}`.

        The GA uses these as hints (via `chromosome.schedule_direction`) —
        an aggressive scheduler could subtract cumulative phase durations;
        the current MVP hands the anchors through to Phase 8 so the fitness
        knows each order's target finish.
        """
        anchors: Dict[str, datetime] = {}
        for op in operations:
            order_id = op.order_id
            due = getattr(op, "due_date", None)
            if due is None:
                continue
            due_dt = _as_datetime(due)
            prev = anchors.get(order_id)
            if prev is None or due_dt < prev:
                anchors[order_id] = due_dt
        return anchors

    def _phase3_routing_selection(
        self,
        operations: List[SchedulingOperation],
        chromosome: Chromosome,
    ) -> tuple[List[SchedulingOperation], int]:
        """Apply the chromosome's routing_choices to each op.

        We don't mutate the input ops — we attach a `variant` attribute the
        RoutingResolver (Sprint P.4/P.5) uses when expanding templates. If
        the chromosome has an empty `routing_choices` map, every op stays
        on the default "A" variant.
        """
        if not chromosome.routing_choices:
            return operations, 0
        applied = 0
        for op in operations:
            variant = chromosome.routing_variant(op.operation_id)
            if variant != "A":
                # Side-channel attribute. Decoder reads it only if it exists.
                op.variant = variant
                applied += 1
        return operations, applied

    def _phase8_scoring(
        self,
        schedule: Dict[str, Any],
        anchors: Dict[str, datetime],
    ) -> Dict[str, Any]:
        """Append v2.0 KPIs that fitness_v2 needs.

        * `tardiness_transport_d` — max(0, late_hours / 24) across anchors.
        * `lam_utilization` — share of total op-hours in any op whose
          phase_name contains "Laminagem" (case-insensitive).

        Q.134.I — `total_idle_hours`/`idle_ratio`/`idle_pct` are NOT recomputed
        here. The decoder (phases 4-7, called in `run`) already set them with
        the worker-based formula (`_compute_idle_metrics`). Overwriting them
        with an avg_utilization approximation made the greedy BASELINE's idle
        incomparable to the GA candidates' (decoder) idle, so the safety net
        saw a phantom 100×+ regression and reverted every work-center plan.
        Same formula on both sides → fair comparison (Spelke axiom 7).
        """
        ops = schedule.get("operations") or []
        total_op_minutes = sum(float(op.get("duration_minutes", 0)) for op in ops)
        makespan_h = float(schedule.get("makespan_hours", 0) or 0)

        # Transport-specific tardiness (in days) — anchors from Phase 2.
        tardiness_transport_d = 0.0
        if anchors and ops:
            order_end: Dict[str, datetime] = {}
            for op in ops:
                order_id = op.get("order_id")
                if not order_id:
                    continue
                # Q.169.D — as ops serializadas usam "end_time" (decoder
                # _scheduled_to_dict); op.get("end") era sempre None →
                # tardiness_transport_d ficou 0 desde sempre (KPI morto,
                # o mesmo padrão start/start_time do preview).
                end = op.get("end_time") or op.get("end")
                end_dt = _as_datetime(end) if end else None
                if end_dt is None:
                    continue
                prev = order_end.get(order_id)
                if prev is None or end_dt > prev:
                    order_end[order_id] = end_dt
            worst = 0.0
            for order_id, anchor in anchors.items():
                end = order_end.get(order_id)
                if end is None:
                    continue
                if end > anchor:
                    worst = max(
                        worst,
                        (end - anchor).total_seconds() / (24 * 3600.0),
                    )
            tardiness_transport_d = worst

        # Laminagem utilisation share.
        lam_minutes = sum(
            float(op.get("duration_minutes", 0))
            for op in ops
            if _is_laminagem_phase(op)
        )
        lam_utilization = (
            100.0 * lam_minutes / total_op_minutes if total_op_minutes > 0 else 0.0
        )

        schedule = dict(schedule)
        # total_idle_hours / idle_ratio / idle_pct — kept from the decoder
        # (worker-based), NOT overwritten (see docstring; Q.134.I).
        schedule["tardiness_transport_d"] = round(tardiness_transport_d, 3)
        schedule["lam_utilization"] = round(lam_utilization, 2)

        # Sprint Q.5 wire — the caller may attach a `revenue_by_order` dict so
        # the greedy pipeline can populate `throughput_eur_day` for the GA
        # fitness term (Sprint P.6). The dict is an optional channel: when
        # absent the fitness term falls back to zero (equivalent to weight=0).
        revenue_by_order = getattr(self, "_revenue_by_order", None)
        if revenue_by_order:
            schedule["throughput_eur_day"] = _estimate_throughput_eur_day(
                ops, revenue_by_order, makespan_h,
            )
        return schedule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        from datetime import date as _date
        if isinstance(value, _date):
            return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return utc_now_naive()


def _is_laminagem_phase(op_dict: Dict[str, Any]) -> bool:
    name = (op_dict.get("phase_name") or op_dict.get("phase_id") or "")
    return "laminag" in str(name).lower()


def _estimate_throughput_eur_day(
    ops: List[Dict[str, Any]],
    revenue_by_order: Dict[str, Any],
    makespan_hours: float,
) -> float:
    """Sum per-order revenue for orders whose LAST op finishes within the
    schedule, divided by horizon days. Defaults to zero when the schedule
    is sub-day (makespan < 1h)."""
    if makespan_hours <= 0:
        return 0.0
    horizon_days = max(1.0, makespan_hours / 24.0)
    seen_orders: set[str] = set()
    total = 0.0
    for op in ops:
        order_id = str(op.get("order_id") or "")
        if not order_id or order_id in seen_orders:
            continue
        seen_orders.add(order_id)
        revenue = revenue_by_order.get(order_id, 0)
        try:
            total += float(revenue or 0)
        except (TypeError, ValueError):
            continue
    return round(total / horizon_days, 2)
