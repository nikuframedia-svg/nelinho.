"""
ProdPlan ONE - Schedule API
============================
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.plan.services.scheduling_service import (
    InvalidScheduleTransition,
    SchedulingService,
)
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
    planning_run_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List schedule rows with optional ``status`` / ``planning_run_id``
    filters and pagination (``limit`` ≤ 100, ``offset`` ≥ 0).

    Sprint Q.9 (2.1) — was a placeholder returning ``{"data": [], "total": 0}``;
    now hits ProductionSchedule directly.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    filters = [ProductionSchedule.tenant_id == tenant_id]
    if status:
        try:
            filters.append(ProductionSchedule.status == ScheduleStatus(status))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"invalid status {status!r}; must be one of "
                    f"{[s.value for s in ScheduleStatus]}"
                ),
            )
    if planning_run_id:
        filters.append(ProductionSchedule.planning_run_id == planning_run_id)

    # Total before pagination
    from sqlalchemy import func
    total_stmt = select(func.count(ProductionSchedule.id)).where(and_(*filters))
    total = (await session.execute(total_stmt)).scalar() or 0

    rows_stmt = (
        select(ProductionSchedule)
        .where(and_(*filters))
        .order_by(
            ProductionSchedule.scheduled_start_date.asc(),
            ProductionSchedule.scheduled_start_time.asc().nulls_last(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()

    data = [
        {
            "id": str(r.id),
            "order_id": r.order_id,
            "order_line": r.order_line,
            "operation_sequence": r.operation_sequence,
            "machine_id": str(r.machine_id) if r.machine_id else None,
            "scheduled_start_date": r.scheduled_start_date.isoformat(),
            "scheduled_end_date": r.scheduled_end_date.isoformat(),
            "scheduled_duration_hours": (
                float(r.scheduled_duration_hours)
                if r.scheduled_duration_hours is not None else None
            ),
            "status": r.status.value if r.status else None,
            "planning_run_id": r.planning_run_id,
            "engine_used": r.engine_used,
            "assigned_employee_id": (
                str(r.assigned_employee_id)
                if r.assigned_employee_id else None
            ),
        }
        for r in rows
    ]
    return {
        "data": data,
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


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


# ─── Q.30.A — Registar operação (iniciar / concluir) ─────────────────────

class OperationStartRequest(BaseModel):
    """Operador inicia uma fase. ``actual_start`` omisso → hora do servidor."""
    actual_start: Optional[datetime] = None


class OperationCompleteRequest(BaseModel):
    """Operador conclui uma fase. ``actual_end`` omisso → hora do servidor."""
    actual_end: Optional[datetime] = None
    actual_quantity: Optional[Decimal] = None


class OperationStateResponse(BaseModel):
    """Estado da fase após a transição — o tablet refresca a fila com isto."""
    id: str
    order_id: str
    operation_sequence: int
    status: str
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None
    actual_quantity: Optional[float] = None


def _operation_state(row: ProductionSchedule) -> OperationStateResponse:
    return OperationStateResponse(
        id=str(row.id),
        order_id=row.order_id,
        operation_sequence=row.operation_sequence,
        status=(
            row.status.value if isinstance(row.status, ScheduleStatus)
            else str(row.status)
        ),
        actual_start=row.actual_start.isoformat() if row.actual_start else None,
        actual_end=row.actual_end.isoformat() if row.actual_end else None,
        actual_quantity=(
            float(row.actual_quantity)
            if row.actual_quantity is not None else None
        ),
    )


@router.post("/{schedule_id}/start", response_model=OperationStateResponse)
async def start_operation(
    schedule_id: UUID,
    request: OperationStartRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.30.A — operador marca uma fase como iniciada (SCHEDULED→IN_PROGRESS).

    Grava o ``actual_start`` (por omissão a hora do servidor). É a porta
    obrigatória antes de ``/complete``: a máquina de estados (FASE 3.5)
    proíbe SCHEDULED→COMPLETED directo, para os actuals históricos ficarem
    consistentes. 409 se a transição não é válida; 404 se a fase não existe.
    """
    service = SchedulingService(session, tenant_id)
    try:
        row = await service.update_status(
            schedule_id,
            status=ScheduleStatus.IN_PROGRESS,
            actual_start=request.actual_start or datetime.now(),
        )
    except InvalidScheduleTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operação {schedule_id} não encontrada",
        )
    await session.commit()
    return _operation_state(row)


@router.post("/{schedule_id}/complete", response_model=OperationStateResponse)
async def complete_operation(
    schedule_id: UUID,
    request: OperationCompleteRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.30.A — operador marca uma fase como concluída (IN_PROGRESS→COMPLETED).

    Grava ``actual_end`` (por omissão a hora do servidor) e, se indicada, a
    ``actual_quantity`` real produzida. Publica ``SCHEDULE_UPDATED`` para o
    realtime. 409 se a fase não está IN_PROGRESS; 404 se não existe.
    """
    service = SchedulingService(session, tenant_id)
    try:
        row = await service.update_status(
            schedule_id,
            status=ScheduleStatus.COMPLETED,
            actual_end=request.actual_end or datetime.now(),
            actual_quantity=request.actual_quantity,
        )
    except InvalidScheduleTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operação {schedule_id} não encontrada",
        )
    await session.commit()
    return _operation_state(row)



