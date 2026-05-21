"""
ProdPlan ONE — CPO v4 Heuristic Decoder: KPI accumulation (Q.67.6.B3 split).

Post-scheduling KPI helpers extracted from `decoder.py` so the façade stays
under 200L. These run once per `decode()` invocation, after every op has
been placed, to derive the dict returned to the caller:

- `_compute_tardiness` — order-level due-date misses
- `_compute_idle_metrics` — Sprint A F2 worker idle accounting
- `_compute_mapelites_axes` — Sprint A ME1 Blueprint v2.0 (x/y/z) axes
- `_compute_throughput` — Sprint A F1 revenue €/day
- `_compute_makespan_hours` — latest end vs horizon_start
- `_compute_otd_delivery` — FASE 1B.6 OTD fraction
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Tuple, Union

from src.plan.cpo.decoder_helpers import ScheduledOp
from src.plan.engines.scheduling_adapter import SchedulingOperation

# Sprint A ME1 — phase codes considered LAMINAGEM* for the X axis
_LAMINAGEM_KEYS = {
    "LAMINAGEM",
    "LAMINAGEM_INFUSAO",
    "LAMINACAO",
    "LAMINAGEM_STANDARD",
}


def _compute_makespan_hours(
    scheduled: List[ScheduledOp],
    horizon_start: datetime,
) -> float:
    if not scheduled:
        return 0.0
    latest = max(s.end for s in scheduled)
    return (latest - horizon_start).total_seconds() / 3600.0


def _compute_tardiness(
    scheduled: List[ScheduledOp],
    operations: List[SchedulingOperation],
) -> Tuple[float, int, Dict[str, Optional[datetime]]]:
    """Return `(tardy_hours, late_orders, due_by_order)`.

    Tardy hours sum the per-order overshoot beyond the earliest `due_date`
    seen on any op in that order. `late_orders` counts orders whose last
    scheduled op finishes after due. `due_by_order` is returned so the
    caller can compute OTD against the same denominator.
    """
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

    return tardy_hours, late_orders, due_by_order


def _compute_idle_metrics(
    scheduled: List[ScheduledOp],
    horizon_start: datetime,
    horizon_end: datetime,
) -> Tuple[float, float]:
    """Sprint A F2 — return `(total_idle_hours, idle_ratio)`.

    Only workers that actually appear on a ScheduledOp count in the pool —
    we don't charge idle for the entire skill matrix (a scheduler can't be
    "guilty" of not using a worker it wasn't allowed to pick anyway).
    """
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
    idle_ratio = (
        min(1.0, total_idle_hours / total_capacity_hours)
        if total_capacity_hours > 0
        else 0.0
    )
    return total_idle_hours, idle_ratio


def _compute_mapelites_axes(
    scheduled: List[ScheduledOp],
    tardy_hours: float,
    idle_ratio: float,
) -> Tuple[float, float, float]:
    """Sprint A ME1 — Blueprint v2.0 MAP-Elites axes (x/y/z).

    The archive's `use_v2_axes=True` mode consumes these three fields
    directly; without them it falls back to the legacy global utilisation /
    tardiness_hours / num_late_orders, which is phase-agnostic and groups
    distinct NELO trade-offs into the same cell.

      X — lam_utilization        : share of minutes spent in LAMINAGEM*
                                   phases over total scheduled minutes (%)
      Y — tardiness_transport_d  : tardy_hours converted to days
      Z — idle_pct               : idle_ratio × 100
    """
    lam_busy_minutes = 0.0
    total_scheduled_minutes = 0.0
    for s in scheduled:
        total_scheduled_minutes += s.duration_minutes
        phase_code = (s.phase_id or "").upper().replace(" ", "_")
        if any(k in phase_code for k in _LAMINAGEM_KEYS):
            lam_busy_minutes += s.duration_minutes

    lam_utilization = (
        (lam_busy_minutes / total_scheduled_minutes) * 100.0
        if total_scheduled_minutes > 0
        else 0.0
    )
    tardiness_transport_d = tardy_hours / 24.0
    idle_pct = idle_ratio * 100.0
    return lam_utilization, tardiness_transport_d, idle_pct


def _compute_throughput(
    scheduled: List[ScheduledOp],
    operations: List[SchedulingOperation],
    horizon_start: datetime,
    horizon_end: datetime,
    product_price_eur: Optional[Mapping[str, Union[float, Decimal]]],
) -> Tuple[float, float]:
    """Sprint A F1 — return `(throughput_total_eur, throughput_eur_day)`.

    Identifies each order's final op (highest sequence within its order),
    looks up the sale price for its product, sums revenue across orders
    whose final op was actually scheduled, and divides by horizon days.
    """
    if not product_price_eur:
        return 0.0, 0.0

    price_lookup: Dict[str, float] = {
        str(pid): float(val) for pid, val in product_price_eur.items()
    }
    final_op_by_order: Dict[str, SchedulingOperation] = {}
    for op in operations:
        current = final_op_by_order.get(op.order_id)
        if current is None or op.sequence > current.sequence:
            final_op_by_order[op.order_id] = op

    scheduled_ids = {s.operation_id for s in scheduled}
    throughput_total_eur = 0.0
    for _order_id, final_op in final_op_by_order.items():
        if final_op.operation_id not in scheduled_ids:
            # The final phase never got placed — don't count revenue.
            continue
        price = price_lookup.get(str(final_op.product_id), 0.0)
        if price > 0:
            throughput_total_eur += price

    horizon_seconds = (horizon_end - horizon_start).total_seconds()
    horizon_days = max(1.0, horizon_seconds / 86400.0)
    throughput_eur_day = throughput_total_eur / horizon_days
    return throughput_total_eur, throughput_eur_day


def _compute_otd_delivery(
    due_by_order: Dict[str, Optional[datetime]],
    late_orders: int,
) -> float:
    """FASE 1B.6 (CRIT-24) — populate otd_delivery so safety_net can
    actually use it as a guardrail.

    Definition: fraction of orders with a due_date that finished on or
    before due. Vacuously 1.0 when no order in the run carries a due_date
    (nothing to be late on).
    """
    n_with_due = len(due_by_order)
    if n_with_due == 0:
        return 1.0
    return 1.0 - (late_orders / n_with_due)
