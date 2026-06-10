"""
ProdPlan ONE — Backward scheduler (Q.53.B)
============================================


The CPO optimises makespan and penalises tardiness *retrospectively* —
it never asks "to ship on the customer's date, when must this boat
*start*?". `WorkOrder` carries `delivery_date` (`OF_DATAENTREGA`) and
`transport_date` (`OF_DATATRANSPORTE`) and they were simply ignored.

This module answers the planner's two real questions:

* **start-by** — given a delivery/transport date, the latest date the
  first phase can start and still ship on time. Lead time = Σ phase
  durations (p50) + Σ cura/secagem gaps, walked *backwards* through the
  factory calendar so weekends and holidays push the start earlier.
* **suggest-shipment** — given a start date (or "today"), the earliest
  realistic ship date, walked *forwards* through the same calendar.

Lead time is computed against the order's routing template
(`RoutingTemplatePhase`, p50 durations). Cure gaps come from
`plan.phase_transition_gap` (the 16 NELO transitions). Both are physical
— they are NOT compressible by adding workers.

The phase chain is treated as a serial critical path: NELO boats move
phase-by-phase, one mould slot at a time, so the sum is the right lead
time (parallel sub-assemblies are out of scope for v1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence, Tuple
from uuid import UUID

from src.plan.cpo.state import normalize_phase_code
from src.shared.time import local_now_naive, local_today
from src.plan.services.factory_calendar import (
    DEFAULT_SHIFT_START,
    FactoryCalendar,
)

logger = logging.getLogger(__name__)


@dataclass
class PhaseStep:
    """One phase on the routing critical path."""

    phase_id: str
    phase_name: str
    duration_hours: float
    seq: int = 0


@dataclass
class LeadTimeBreakdown:
    """Audit-friendly decomposition of the computed lead time."""

    total_hours: float = 0.0
    work_hours: float = 0.0
    curing_gap_hours: float = 0.0
    n_phases: int = 0
    steps: List[dict] = field(default_factory=list)


def compute_lead_time(
    phases: Sequence[PhaseStep],
    gap_lookup,
) -> LeadTimeBreakdown:
    """Sum work hours + cura/secagem gaps along the routing chain.

    `gap_lookup(from_phase, to_phase) -> float` returns the mandatory
    minimum wait (hours) between two consecutive phases — typically
    `FactoryState.min_gap_hours` or a closure over `NELO_CURING_GAPS_SEED`.

    The breakdown is returned so the API can show *why* a lead time is
    what it is (audit trail invariant).
    """
    breakdown = LeadTimeBreakdown()
    ordered = sorted(phases, key=lambda p: p.seq)
    for idx, step in enumerate(ordered):
        work_h = max(0.0, float(step.duration_hours))
        gap_h = 0.0
        if idx > 0:
            prev = ordered[idx - 1]
            gap_h = max(0.0, float(gap_lookup(prev.phase_name or prev.phase_id,
                                              step.phase_name or step.phase_id)))
        breakdown.work_hours += work_h
        breakdown.curing_gap_hours += gap_h
        breakdown.steps.append({
            "seq": step.seq,
            "phase_id": step.phase_id,
            "phase_name": step.phase_name,
            "work_hours": round(work_h, 2),
            "curing_gap_hours": round(gap_h, 2),
        })
    breakdown.n_phases = len(ordered)
    breakdown.total_hours = breakdown.work_hours + breakdown.curing_gap_hours
    return breakdown


def start_by(
    target: datetime,
    phases: Sequence[PhaseStep],
    gap_lookup,
    calendar: FactoryCalendar,
) -> Tuple[datetime, LeadTimeBreakdown]:
    """Latest start datetime that still meets `target`.

    The curing gaps are calendar time (chemistry runs through the night
    and weekends) — they are subtracted as plain wall-clock hours. The
    work hours are productive time — they are subtracted through the
    factory calendar so non-working days push the start earlier.

    Returns `(start_datetime, breakdown)`.
    """
    breakdown = compute_lead_time(phases, gap_lookup)
    # 1) curing gaps are wall-clock — pull the target back by them.
    cursor = target - timedelta(hours=breakdown.curing_gap_hours)
    # 2) work hours consume the calendar.
    start = calendar.subtract_working_hours(cursor, breakdown.work_hours)
    return start, breakdown


def suggest_shipment(
    start: datetime,
    phases: Sequence[PhaseStep],
    gap_lookup,
    calendar: FactoryCalendar,
) -> Tuple[datetime, LeadTimeBreakdown]:
    """Earliest realistic ship datetime if work starts at `start`.

    Forward counterpart of `start_by`: work hours consume the calendar,
    curing gaps add wall-clock time.
    """
    breakdown = compute_lead_time(phases, gap_lookup)
    after_work = calendar.add_working_hours(start, breakdown.work_hours)
    ship = after_work + timedelta(hours=breakdown.curing_gap_hours)
    return ship, breakdown


# ---------------------------------------------------------------------------
# DB-backed wrapper
# ---------------------------------------------------------------------------

class BackwardSchedulerService:
    """Resolve routing + calendar from the DB and run the back/forward walk."""

    def __init__(self, session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _routing_phases_for_order(
        self, order: "ProductionOrder",  # noqa: F821 — string-quoted
    ) -> List[PhaseStep]:
        """Resolve the routing phases (critical path) for an order.

        Strategy: find a RoutingTemplate assigned to the order's product
        type / model; fall back to *any* active template; fall back to
        an empty list (caller handles the no-routing case explicitly).
        """
        from src.plan.models.routing_template import (
            ModelRoutingAssignment,
            RoutingTemplate,
            RoutingTemplatePhase,
        )
        from sqlalchemy import select

        model_key = str(order.product_type or order.product_id or "")
        template_id = None
        if model_key:
            stmt = select(ModelRoutingAssignment).where(
                ModelRoutingAssignment.tenant_id == self.tenant_id,
                ModelRoutingAssignment.model_id == model_key,
            )
            assignment = (await self.session.execute(stmt)).scalar_one_or_none()
            if assignment is not None:
                template_id = assignment.primary_template_id

        if template_id is None:
            # Fall back to any active template — better an estimate than
            # nothing. The breakdown carries `n_phases` so callers see it.
            stmt = (
                select(RoutingTemplate)
                .where(
                    RoutingTemplate.tenant_id == self.tenant_id,
                    RoutingTemplate.active.is_(True),
                )
                .order_by(RoutingTemplate.model_coverage.desc())
                .limit(1)
            )
            tpl = (await self.session.execute(stmt)).scalar_one_or_none()
            if tpl is not None:
                template_id = tpl.id

        if template_id is None:
            return []

        stmt = (
            select(RoutingTemplatePhase)
            .where(
                RoutingTemplatePhase.tenant_id == self.tenant_id,
                RoutingTemplatePhase.template_id == template_id,
            )
            .order_by(RoutingTemplatePhase.seq)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        steps: List[PhaseStep] = []
        for r in rows:
            if r.can_skip:
                continue
            dur = float(r.duration_p50_h or 0.0)
            steps.append(PhaseStep(
                phase_id=str(r.phase_id),
                phase_name=str(r.phase_name or r.phase_id),
                duration_hours=dur,
                seq=int(r.seq),
            ))
        return steps

    async def _gap_lookup(self):
        """Return a `(from, to) -> hours` closure over the phase gaps."""
        from src.plan.cpo.state import _load_phase_transition_gaps

        gaps = await _load_phase_transition_gaps(self.session, self.tenant_id)

        def _lookup(from_phase: str, to_phase: str) -> float:
            a = normalize_phase_code(from_phase)
            b = normalize_phase_code(to_phase)
            if not a or not b:
                return 0.0
            return float(gaps.get((a, b), 0.0))

        return _lookup

    async def start_by_for_order(
        self, order: "ProductionOrder",  # noqa: F821
    ) -> dict:
        """Compute the start-by date for one order.

        Uses `transport_date` when present (the planned ship date),
        otherwise the order has no anchor and we return a null result.
        """
        from src.plan.services.factory_calendar import FactoryCalendar

        target = order.transport_date
        target_field = "transport_date"
        if target is None:
            return {
                "order_id": str(order.id),
                "hull": str(order.legacy_id) if order.legacy_id is not None else None,
                "target_date": None,
                "target_field": None,
                "start_by": None,
                "lead_time": None,
                "feasible": None,
                "reason": "Ordem sem data de transporte definida.",
            }

        target_dt = _as_datetime(target)
        phases = await self._routing_phases_for_order(order)
        gap_lookup = await self._gap_lookup()
        calendar = await FactoryCalendar.load(self.session, self.tenant_id)

        if not phases:
            return {
                "order_id": str(order.id),
                "hull": str(order.legacy_id) if order.legacy_id is not None else None,
                "target_date": target_dt.date().isoformat(),
                "target_field": target_field,
                "start_by": None,
                "lead_time": None,
                "feasible": None,
                "reason": "Sem routing template para o modelo — lead time desconhecido.",
            }

        start_dt, breakdown = start_by(target_dt, phases, gap_lookup, calendar)
        now = local_now_naive()  # calendário fabril é local-naive
        feasible = start_dt >= now
        return {
            "order_id": str(order.id),
            "hull": str(order.legacy_id) if order.legacy_id is not None else None,
            "product_name": order.product_name,
            "product_type": order.product_type,
            "target_date": target_dt.date().isoformat(),
            "target_field": target_field,
            "start_by": start_dt.isoformat(),
            "lead_time": {
                "total_hours": round(breakdown.total_hours, 2),
                "work_hours": round(breakdown.work_hours, 2),
                "curing_gap_hours": round(breakdown.curing_gap_hours, 2),
                "n_phases": breakdown.n_phases,
                "steps": breakdown.steps,
            },
            "feasible": feasible,
            "reason": (
                "OK — há folga para começar a tempo."
                if feasible
                else "Atraso garantido — a data-limite de início já passou."
            ),
        }

    async def suggest_shipment_for_order(
        self,
        order: "ProductionOrder",  # noqa: F821
        start: Optional[datetime] = None,
    ) -> dict:
        """Earliest realistic ship date if work starts at `start` (or today)."""
        from src.plan.services.factory_calendar import FactoryCalendar

        phases = await self._routing_phases_for_order(order)
        gap_lookup = await self._gap_lookup()
        calendar = await FactoryCalendar.load(self.session, self.tenant_id)

        start_dt = start or datetime.combine(local_today(), DEFAULT_SHIFT_START)

        if not phases:
            return {
                "order_id": str(order.id),
                "hull": str(order.legacy_id) if order.legacy_id is not None else None,
                "start": start_dt.isoformat(),
                "suggested_shipment": None,
                "lead_time": None,
                "transport_date": (
                    _as_datetime(order.transport_date).date().isoformat()
                    if order.transport_date else None
                ),
                "reason": "Sem routing template para o modelo — lead time desconhecido.",
            }

        ship_dt, breakdown = suggest_shipment(start_dt, phases, gap_lookup, calendar)
        promised = order.transport_date
        on_time = None
        if promised is not None:
            on_time = ship_dt <= _as_datetime(promised)
        return {
            "order_id": str(order.id),
            "hull": str(order.legacy_id) if order.legacy_id is not None else None,
            "product_name": order.product_name,
            "product_type": order.product_type,
            "start": start_dt.isoformat(),
            "suggested_shipment": ship_dt.isoformat(),
            "lead_time": {
                "total_hours": round(breakdown.total_hours, 2),
                "work_hours": round(breakdown.work_hours, 2),
                "curing_gap_hours": round(breakdown.curing_gap_hours, 2),
                "n_phases": breakdown.n_phases,
                "steps": breakdown.steps,
            },
            "transport_date": (
                _as_datetime(promised).date().isoformat() if promised else None
            ),
            "meets_transport_date": on_time,
            "reason": (
                "OK — chega antes da data de transporte."
                if on_time
                else "Não chega à data de transporte prometida."
                if on_time is False
                else "Sem data de transporte para comparar."
            ),
        }


def _as_datetime(value) -> datetime:
    """Coerce a date/datetime to a naive datetime at the shift start."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, DEFAULT_SHIFT_START)
    raise TypeError(f"cannot coerce {value!r} to datetime")
