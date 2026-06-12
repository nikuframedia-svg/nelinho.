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
    horizon_start: datetime,
) -> Dict[str, object]:
    """Tardiness KPIs separando dívida herdada de atraso novo (Q.153.A2).

    ~88% das OFs chegam com a data de entrega já no passado (dívida
    herdada). Medir só o atraso cru faria com que TODAS contassem como
    atrasadas e o GA não distinguiria um plano melhor de um pior. Medimos
    a pontualidade do PLANO contra `effective_due = max(due, horizon_start)`
    para o GA optimizar o atraso NOVO/evitável (`tardiness_beyond_today_h`),
    sem mascarar a dívida (`num_already_overdue`). Nunca mutamos `due_date`.

    Chaves devolvidas:
      tardy_hours              — atraso total vs due real (legacy; safety_net)
      late_orders              — nº ordens que acabam depois do due real (legacy)
      num_already_overdue      — nº ordens com due < horizon_start (herdado)
      num_newly_late           — nº ordens que acabam depois de effective_due
      tardiness_beyond_today_h — atraso evitável vs effective_due (alvo do GA)
      due_by_order             — due real por ordem (p/ OTD no mesmo denominador)
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
    num_already_overdue = 0
    num_newly_late = 0
    tardiness_beyond_today_h = 0.0
    for order_id, end_time in order_last_end.items():
        due = due_by_order.get(order_id)
        if due is None:
            continue
        overdue_at_start = due < horizon_start
        if overdue_at_start:
            num_already_overdue += 1
        # Legacy — atraso vs due real (mantém safety_net/OTD inalterados).
        if end_time > due:
            late_orders += 1
            tardy_hours += (end_time - due).total_seconds() / 3600.0
        # Q.153.A2 — magnitude evitável vs effective_due = max(due, hoje).
        # Inclui o tempo-para-limpar de ordens já vencidas (o GA ganha
        # gradiente: acabar os atrasados quanto antes), mas SEM a dívida
        # histórica que saturava a fitness.
        effective_due = due if due > horizon_start else horizon_start
        if end_time > effective_due:
            tardiness_beyond_today_h += (
                (end_time - effective_due).total_seconds() / 3600.0
            )
            # "newly late" = o plano atrasou uma ordem que NÃO estava já
            # vencida à entrada (atraso genuinamente causado pelo plano).
            if not overdue_at_start:
                num_newly_late += 1

    return {
        "tardy_hours": tardy_hours,
        "late_orders": late_orders,
        "num_already_overdue": num_already_overdue,
        "num_newly_late": num_newly_late,
        "tardiness_beyond_today_h": tardiness_beyond_today_h,
        "due_by_order": due_by_order,
    }


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


def build_result_dict(
    scheduled: List[ScheduledOp],
    operations: List[SchedulingOperation],
    machines: List[object],
    horizon_start: datetime,
    horizon_end: datetime,
    *,
    product_price_eur: Optional[Mapping[str, Union[float, Decimal]]] = None,
    setups: int = 0,
    warnings: Optional[List[str]] = None,
    infeasible_op_ids: Optional[List[str]] = None,
    routing_variants_applied: int = 0,
    backwards_shifts: int = 0,
    engine_used: str = "cpo_v4",
    blocked_ops: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    """Q.166.F — monta o result-dict canónico a partir de uma lista de ScheduledOp.

    Extraído da Phase 9-10 do `decoder.decode` (comportamento idêntico) para ser
    REUSADO pelo caminho CP-SAT (`cpsat_scheduler`+`cpsat_postpass`), garantindo que
    ambos emitem EXACTAMENTE o mesmo contrato (operations[], makespan_hours, otd,
    idle, lam_utilization, throughput, etc.) que commits/safety_net/API esperam.
    """
    from src.plan.cpo.decoder_helpers import _estimate_utilization, _scheduled_to_dict

    warnings = warnings or []
    infeasible_op_ids = infeasible_op_ids or []
    blocked_ops = blocked_ops or []

    makespan_hours = _compute_makespan_hours(scheduled, horizon_start)
    tard = _compute_tardiness(scheduled, operations, horizon_start)
    tardy_hours = tard["tardy_hours"]
    late_orders = tard["late_orders"]
    due_by_order = tard["due_by_order"]
    total_idle_hours, idle_ratio = _compute_idle_metrics(
        scheduled, horizon_start, horizon_end,
    )
    lam_utilization, tardiness_transport_d, idle_pct = _compute_mapelites_axes(
        scheduled, tardy_hours, idle_ratio,
    )
    throughput_total_eur, throughput_eur_day = _compute_throughput(
        scheduled, operations, horizon_start, horizon_end, product_price_eur,
    )
    otd_delivery = _compute_otd_delivery(due_by_order, late_orders)

    return {
        "success": not infeasible_op_ids,
        "engine_used": engine_used,
        "operations": [_scheduled_to_dict(s) for s in scheduled],
        "makespan_hours": round(makespan_hours, 2),
        "total_tardiness_hours": round(tardy_hours, 2),
        "num_late_orders": late_orders,
        "num_already_overdue": tard["num_already_overdue"],
        "num_newly_late": tard["num_newly_late"],
        "tardiness_beyond_today_h": round(tard["tardiness_beyond_today_h"], 2),
        "otd_delivery": round(otd_delivery, 4),
        "setups": setups,
        "routing_variants_applied": routing_variants_applied,
        "backwards_shifts": backwards_shifts,
        "total_idle_hours": round(total_idle_hours, 2),
        "idle_ratio": round(idle_ratio, 4),
        "num_machines": len(machines),
        "lam_utilization": round(lam_utilization, 2),
        "idle_pct": round(idle_pct, 2),
        "tardiness_transport_d": round(tardiness_transport_d, 2),
        "throughput_eur_total": round(throughput_total_eur, 2),
        "throughput_eur_day": round(throughput_eur_day, 2),
        "avg_utilization": _estimate_utilization(
            scheduled, machines, horizon_start, horizon_end,
        ),
        "warnings": warnings,
        "infeasible_op_ids": infeasible_op_ids,
        # Q.174.F5 — secção estruturada "não planeável": status (op_status.*)
        # + recurso em falta por op (decisão do dono: plano parcial + secção
        # inviável, nunca silêncio). Paralela a infeasible_op_ids (intacto).
        "unplannable": blocked_ops,
    }
