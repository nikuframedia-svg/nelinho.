"""ProdPlan ONE — Date-aware planning API (Q.53.B).

Endpoints that put the customer's delivery dates back into planning:

* ``GET  /v1/plan/calendar``                       — factory working calendar
* ``GET  /v1/plan/orders/{id}/start-by``           — latest start to ship on time
* ``GET  /v1/plan/orders/{id}/suggest-shipment``   — earliest realistic ship date
* ``GET  /v1/plan/adherence``                      — plan vs realised by phase
* ``POST /v1/plan/ctp``                            — capable-to-promise per truck

All read-only except CTP (which only *computes*, never writes). The
calendar is seeded by ``src/adapters/nelo/etl/calendar.py``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.factory_calendar import FactoryCalendarDay
from src.plan.models.order import ProductionOrder
from src.plan.services.backward_scheduler import BackwardSchedulerService
from src.plan.services.ctp_service import CapableToPromiseService
from src.plan.services.plan_adherence_service import PlanAdherenceService
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.shared.time import local_today

logger = logging.getLogger(__name__)
router = APIRouter(tags=["PLAN.Dates"])


# ─── Calendar ────────────────────────────────────────────────────────────


class CalendarDayOut(BaseModel):
    day: str
    is_working_day: bool
    shift_hours: float
    label: Optional[str] = None


class CalendarResponse(BaseModel):
    items: List[CalendarDayOut]
    working_days: int
    non_working_days: int


@router.get("/calendar", response_model=CalendarResponse)
async def get_calendar(
    from_date: Optional[date] = Query(None, description="Início da janela (default: hoje)."),
    to_date: Optional[date] = Query(None, description="Fim da janela (default: +90d)."),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> CalendarResponse:
    """Factory working calendar for a date window.

    Empty result means the calendar was never seeded — run the
    ``calendar`` ETL mirror. No silent fallback: the UI shows an explicit
    empty state.
    """
    start = from_date or local_today()
    end = to_date or (start + timedelta(days=90))
    if end < start:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="to_date não pode ser anterior a from_date.",
        )

    stmt = (
        select(FactoryCalendarDay)
        .where(
            FactoryCalendarDay.tenant_id == tenant_id,
            FactoryCalendarDay.day >= start,
            FactoryCalendarDay.day <= end,
        )
        .order_by(FactoryCalendarDay.day)
    )
    rows = (await session.execute(stmt)).scalars().all()
    items = [
        CalendarDayOut(
            day=r.day.isoformat(),
            is_working_day=bool(r.is_working_day),
            shift_hours=float(r.shift_hours or 0),
            label=r.label,
        )
        for r in rows
    ]
    working = sum(1 for i in items if i.is_working_day)
    return CalendarResponse(
        items=items,
        working_days=working,
        non_working_days=len(items) - working,
    )


# ─── Start-by / Suggest-shipment ─────────────────────────────────────────


async def _load_order(
    order_id: UUID, tenant_id: UUID, session: AsyncSession,
) -> ProductionOrder:
    stmt = select(ProductionOrder).where(
        ProductionOrder.tenant_id == tenant_id,
        ProductionOrder.id == order_id,
    )
    order = (await session.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Ordem {order_id} não encontrada.",
        )
    return order


@router.get("/orders/{order_id}/start-by")
async def order_start_by(
    order_id: UUID,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Latest start date for an order to still meet its transport date.

    Lead time = Σ routing-phase work hours (walked through the factory
    calendar) + Σ cura/secagem gaps (wall-clock). Returns a breakdown so
    the planner sees *why* the start-by date is what it is.
    """
    order = await _load_order(order_id, tenant_id, session)
    service = BackwardSchedulerService(session, tenant_id)
    return await service.start_by_for_order(order)


@router.get("/orders/{order_id}/suggest-shipment")
async def order_suggest_shipment(
    order_id: UUID,
    start: Optional[date] = Query(
        None, description="Data de início da produção (default: hoje).",
    ),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Earliest realistic ship date if the order starts on `start`."""
    order = await _load_order(order_id, tenant_id, session)
    service = BackwardSchedulerService(session, tenant_id)
    start_dt = (
        datetime.combine(start, datetime.min.time().replace(hour=8))
        if start else None
    )
    return await service.suggest_shipment_for_order(order, start=start_dt)


# ─── Adherence ───────────────────────────────────────────────────────────


@router.get("/adherence")
async def plan_adherence(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Plan vs realised by phase, including defect rate per phase.

    Plan = latest ``ScheduleCommit`` operations. Realised = matched
    ``ProductionSchedule`` rows with actuals. Defect rate = rework rows
    per phase. Empty/no-commit returns an explicit empty report.
    """
    service = PlanAdherenceService(session, tenant_id)
    return await service.compute()


# ─── Capable-to-Promise ──────────────────────────────────────────────────


class CtpRequest(BaseModel):
    truck_date: date = Field(..., description="Data de partida do camião.")
    truck_capacity: int = Field(
        6, ge=1, le=100, description="Slots no camião.",
    )
    start_from: Optional[date] = Field(
        None, description="Quando a produção pode começar (default: hoje).",
    )
    order_ids: Optional[List[str]] = Field(
        None, description="Restringir a estas ordens (default: todas em curso).",
    )


@router.post("/ctp")
async def capable_to_promise(
    body: CtpRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Capable-to-promise — quais barcos encaixam num camião/data.

    Avalia cada ordem em curso contra a data do camião: data viável
    (backward scheduler), capacidade do camião, materiais em stock e
    molde disponível. Devolve committable / at-risk / rejected.
    """
    service = CapableToPromiseService(session, tenant_id)
    return await service.evaluate(
        truck_date=body.truck_date,
        truck_capacity=body.truck_capacity,
        start_from=body.start_from,
        candidate_order_ids=body.order_ids,
    )
