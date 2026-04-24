"""
ProdPlan ONE - Schedule API
============================
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.plan.services.scheduling_service import SchedulingService
from src.plan.engines.scheduling_adapter import SchedulerEngine, DispatchRule

router = APIRouter(prefix="/schedule", tags=["Scheduling"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class ScheduleGenerateRequest(BaseModel):
    """Request to generate schedule."""
    orders: List[Dict[str, Any]]
    machines: List[Dict[str, Any]]
    operations: List[Dict[str, Any]]
    engine: str = "heuristic"
    rule: str = "edd"
    planning_weeks: int = 4


class ScheduleResponse(BaseModel):
    """Schedule generation response."""
    planning_run_id: str
    status: str
    operations_scheduled: int
    kpis: Dict[str, Any]


@router.get("/")
async def list_schedules(
    status: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List all schedules."""
    # Return empty list for now (placeholder for future implementation)
    return {"data": [], "total": 0}


@router.post("/generate", response_model=ScheduleResponse)
async def generate_schedule(
    request: ScheduleGenerateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate production schedule."""
    service = SchedulingService(session, tenant_id)
    
    result = await service.generate_schedule(
        orders=request.orders,
        machines=request.machines,
        operations=request.operations,
        engine=SchedulerEngine(request.engine),
        rule=DispatchRule(request.rule),
        planning_weeks=request.planning_weeks,
    )
    
    return ScheduleResponse(
        planning_run_id=result["planning_run_id"],
        status=result["status"],
        operations_scheduled=result["operations_scheduled"],
        kpis=result["kpis"],
    )


@router.get("/{planning_run_id}")
async def get_schedule(
    planning_run_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get schedule by planning run ID."""
    service = SchedulingService(session, tenant_id)
    schedules = await service.get_schedule(planning_run_id=planning_run_id)
    
    return {
        "planning_run_id": planning_run_id,
        "operations": [
            {
                "id": str(s.id),
                "order_id": s.order_id,
                "operation_id": str(s.operation_id),
                "scheduled_start": s.scheduled_start_date.isoformat(),
                "scheduled_end": s.scheduled_end_date.isoformat(),
                "status": s.status.value,
            }
            for s in schedules
        ],
    }


@router.get("/order/{order_id}")
async def get_order_schedule(
    order_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get schedule for an order."""
    service = SchedulingService(session, tenant_id)
    schedules = await service.get_schedule(order_id=order_id)

    return {
        "order_id": order_id,
        "operations": [
            {
                "id": str(s.id),
                "operation_sequence": s.operation_sequence,
                "scheduled_start": s.scheduled_start_date.isoformat(),
                "scheduled_end": s.scheduled_end_date.isoformat(),
                "status": s.status.value,
            }
            for s in schedules
        ],
    }


# ─── Sprint H.2 — Operador tablet ────────────────────────────────────────

class WorkerOperationResponse(BaseModel):
    """One row the Operador tablet renders in "A minha fila"."""
    id: str
    order_id: str
    operation_sequence: int
    product_id: str
    quantity: float
    machine_id: Optional[str] = None
    scheduled_start: str
    scheduled_end: str
    scheduled_duration_hours: Optional[float] = None
    status: str
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None


@router.get(
    "/worker/{employee_id}/operations-today",
    response_model=List[WorkerOperationResponse],
)
async def get_worker_operations_today(
    employee_id: UUID,
    as_of: Optional[date] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Sprint H.2 — return every ProductionSchedule assigned to
    ``employee_id`` whose scheduled window overlaps the given day.

    Drives the tablet's "A minha fila de trabalho" view. Orders by
    scheduled start so the operator sees "next up" at the top.
    ``as_of`` defaults to today (server time); the frontend passes
    the local date explicitly so the operator reliably sees the
    same rows across midnight boundaries.
    """
    target_day = as_of or date.today()
    stmt = (
        select(ProductionSchedule)
        .where(
            and_(
                ProductionSchedule.tenant_id == tenant_id,
                ProductionSchedule.assigned_employee_id == employee_id,
                ProductionSchedule.scheduled_start_date <= target_day,
                ProductionSchedule.scheduled_end_date >= target_day,
            )
        )
        .order_by(
            ProductionSchedule.scheduled_start_date.asc(),
            ProductionSchedule.scheduled_start_time.asc().nullsfirst(),
            ProductionSchedule.operation_sequence.asc(),
        )
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [
        WorkerOperationResponse(
            id=str(row.id),
            order_id=row.order_id,
            operation_sequence=row.operation_sequence,
            product_id=str(row.product_id),
            quantity=float(row.quantity),
            machine_id=str(row.machine_id) if row.machine_id else None,
            scheduled_start=_combine_date_time(
                row.scheduled_start_date, row.scheduled_start_time,
            ),
            scheduled_end=_combine_date_time(
                row.scheduled_end_date, row.scheduled_end_time,
            ),
            scheduled_duration_hours=(
                float(row.scheduled_duration_hours)
                if row.scheduled_duration_hours is not None else None
            ),
            status=(
                row.status.value if isinstance(row.status, ScheduleStatus)
                else str(row.status)
            ),
            actual_start=row.actual_start.isoformat() if row.actual_start else None,
            actual_end=row.actual_end.isoformat() if row.actual_end else None,
        )
        for row in rows
    ]


def _combine_date_time(d: date, t) -> str:
    """Serialize a (date, time) pair into an ISO string the tablet UI
    can parse with ``new Date(…)``. Time missing → day starts at 00:00."""
    if t is None:
        return datetime.combine(d, datetime.min.time()).isoformat()
    return datetime.combine(d, t).isoformat()



