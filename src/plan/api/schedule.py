"""
ProdPlan ONE - Schedule API
============================
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.core.models.employee import Employee
from src.plan.cpo.commits import CommitsService
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.plan.services.cpo_commit_orders import operations_for_worker_day
from src.plan.services.operation_execution_service import OperationExecutionService
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


async def _resolve_worker_code(
    session: AsyncSession, tenant_id: UUID, employee_id: str,
) -> Optional[str]:
    """Resolve o identificador recebido para o ``employee_code`` que vive em
    ``op["workers"]`` (Q.148/Q.157.D).

    O frontend manda ``?worker=`` ou o ``user_id`` de ``auth/me``. Aceita:
    - ``Employee.id`` (UUID) → devolve o ``employee_code`` desse colaborador;
    - um ``employee_code`` directo (string não-UUID) → devolve-o tal e qual;
    - UUID que não é um Employee (ex.: um ``user_id``) → ``None`` (fila vazia
      honesta, nunca inventa operações).
    """
    raw = str(employee_id or "").strip()
    if not raw:
        return None
    try:
        uid = UUID(raw)
    except (ValueError, AttributeError):
        uid = None
    if uid is not None:
        emp = (
            await session.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id, Employee.id == uid,
                )
            )
        ).scalar_one_or_none()
        return emp.employee_code if emp is not None else None
    return raw


def _op_to_worker_response(
    op: Dict[str, Any], exec_row: Optional[Any],
) -> WorkerOperationResponse:
    """Mapeia uma operação do commit LIVE → contrato do tablet, sobrepondo o
    estado de execução real (overlay) quando existe."""
    duration_min = op.get("duration_minutes")
    machine = op.get("machine_id")
    order_id = str(op.get("order_id") or "")
    return WorkerOperationResponse(
        id=str(op.get("operation_id") or ""),
        order_id=order_id,
        # A op do commit não traz sequence/product_id/quantity (o decoder não os
        # serializa); defaults honestos — o tablet usa-os só como texto.
        operation_sequence=0,
        product_id=order_id,
        quantity=1.0,
        machine_id=str(machine) if machine else None,
        scheduled_start=str(op.get("start_time") or ""),
        scheduled_end=str(op.get("end_time") or ""),
        scheduled_duration_hours=(
            round(float(duration_min) / 60.0, 2) if duration_min is not None else None
        ),
        status=(exec_row.status if exec_row is not None else "SCHEDULED"),
        actual_start=(
            exec_row.actual_start.isoformat()
            if exec_row is not None and exec_row.actual_start else None
        ),
        actual_end=(
            exec_row.actual_end.isoformat()
            if exec_row is not None and exec_row.actual_end else None
        ),
    )


@router.get(
    "/worker/{employee_id}/operations-today",
    response_model=List[WorkerOperationResponse],
)
async def get_worker_operations_today(
    employee_id: str,
    as_of: Optional[date] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.157.D — fila do operador a partir do plano LIVE do CPO.

    Antes lia de ``plan.production_schedules`` (só populada pelo ``/generate``
    manual, desacoplada do CPO LIVE) → fila vazia ou stale. Agora lê do commit
    LIVE mais recente (fallback DRAFT), filtra as operações onde o operador
    (``employee_code``) aparece em ``op["workers"]`` e que estão activas no dia,
    e sobrepõe o progresso real do overlay ``operation_execution`` (Q.157.E).
    Sem commit, sem operador resolvido, ou sem ops → ``[]`` (vazio honesto).
    """
    target_day = as_of or date.today()
    worker_code = await _resolve_worker_code(session, tenant_id, employee_id)
    if not worker_code:
        return []

    commits = CommitsService(session, tenant_id)
    commit = await commits.latest_live() or await commits.get_latest()
    if commit is None:
        return []

    ops = operations_for_worker_day(commit.operations or [], worker_code, target_day)
    if not ops:
        return []

    exec_svc = OperationExecutionService(session, tenant_id)
    status_map = await exec_svc.status_map(
        [str(op.get("operation_id") or "") for op in ops]
    )
    return [
        _op_to_worker_response(op, status_map.get(str(op.get("operation_id") or "")))
        for op in ops
    ]


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


# ─── Q.157.E — picagem das operações do plano LIVE (por operation_id) ─────

def _exec_state(row: Any) -> OperationStateResponse:
    """OperationExecution (overlay) → contrato OperationStateResponse do tablet."""
    return OperationStateResponse(
        id=str(row.operation_id),
        order_id=str(row.order_id or ""),
        operation_sequence=0,
        status=str(row.status),
        actual_start=row.actual_start.isoformat() if row.actual_start else None,
        actual_end=row.actual_end.isoformat() if row.actual_end else None,
        actual_quantity=(
            float(row.actual_quantity) if row.actual_quantity is not None else None
        ),
    )


async def _find_live_operation(
    session: AsyncSession, tenant_id: UUID, operation_id: str,
) -> Optional[Dict[str, Any]]:
    """Localiza uma operação (por ``operation_id``) no commit LIVE/DRAFT mais
    recente — para enriquecer o overlay com order_id/worker/commit_sha reais."""
    commits = CommitsService(session, tenant_id)
    commit = await commits.latest_live() or await commits.get_latest()
    if commit is None:
        return None
    for op in commit.operations or []:
        if str(op.get("operation_id") or "") == str(operation_id):
            workers = op.get("workers") or []
            first = str(workers[0]) if isinstance(workers, (list, tuple)) and workers else ""
            return {
                "order_id": str(op.get("order_id") or ""),
                "worker_code": first,
                "commit_sha": str(commit.commit_sha256 or ""),
            }
    return None


@router.post("/operation/{operation_id}/start", response_model=OperationStateResponse)
async def start_live_operation(
    operation_id: str,
    request: OperationStartRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.157.E — operador inicia uma operação do plano LIVE (SCHEDULED→IN_PROGRESS).

    Escreve o progresso no overlay ``operation_execution`` (o commit é imutável),
    com audit na mesma tx. 404 se a operação não existe no commit LIVE/DRAFT;
    409 se a transição não é válida.
    """
    meta = await _find_live_operation(session, tenant_id, operation_id)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operação {operation_id} não está no plano LIVE",
        )
    svc = OperationExecutionService(session, tenant_id)
    try:
        row = await svc.start(
            operation_id=operation_id,
            order_id=meta["order_id"],
            worker_code=meta["worker_code"],
            commit_sha=meta["commit_sha"],
            actual_start=request.actual_start or datetime.now(timezone.utc),
        )
    except InvalidScheduleTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return _exec_state(row)


@router.post(
    "/operation/{operation_id}/complete", response_model=OperationStateResponse,
)
async def complete_live_operation(
    operation_id: str,
    request: OperationCompleteRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.157.E — operador conclui uma operação do plano LIVE (IN_PROGRESS→COMPLETED).

    Grava ``actual_end``/``actual_quantity`` no overlay + audit na mesma tx.
    409 se a operação não está IN_PROGRESS (precisa de ``/start`` antes).
    """
    svc = OperationExecutionService(session, tenant_id)
    try:
        row = await svc.complete(
            operation_id=operation_id,
            actual_end=request.actual_end or datetime.now(timezone.utc),
            actual_quantity=request.actual_quantity,
        )
    except InvalidScheduleTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return _exec_state(row)


