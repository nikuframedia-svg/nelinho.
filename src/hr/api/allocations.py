"""
ProdPlan ONE - Allocations API
===============================
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.hr.services.allocation_service import AllocationService

router = APIRouter(prefix="/allocations", tags=["Allocations"])


# ─── Schemas ──────────────────────────────────────────────────────────────────


class AllocationRequest(BaseModel):
    """Allocation request."""
    requirements: List[Dict[str, Any]]
    employees: List[Dict[str, Any]]
    strategy: str = "skill_first"


class AllocationCreatedItem(BaseModel):
    allocation_id: str
    employee_id: str
    employee_name: str
    order_id: str
    operation_id: str
    allocated_hours: float
    hourly_rate: float
    estimated_cost: float
    skill_match: bool


class AllocationCreateResponse(BaseModel):
    allocations: List[AllocationCreatedItem]


class DailyAllocationRequest(BaseModel):
    """Q.31.D.2 — atribuição drag-drop de um operador a um barco."""
    employee_id: UUID
    order_id: str
    allocation_date: Optional[date] = None
    allocated_hours: float = 8.0


class DailyAllocationResponse(BaseModel):
    allocation_id: str
    employee_id: str
    order_id: str
    operation_id: str
    allocation_date: str
    allocated_hours: float
    status: str


class EmployeeAvailabilityResponse(BaseModel):
    employee_id: str
    from_date: str
    to_date: str
    total_capacity_hours: float
    allocated_hours: float
    available_hours: float
    utilization_percent: float
    allocations_count: int


class OrderAllocationItem(BaseModel):
    id: str
    employee_id: str
    operation_id: str
    allocated_hours: float
    status: str


class OrderAllocationsResponse(BaseModel):
    order_id: str
    allocations: List[OrderAllocationItem]


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/create", response_model=AllocationCreateResponse)
async def create_allocations(
    request: AllocationRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Create employee allocations."""
    service = AllocationService(session, tenant_id)

    allocations = await service.allocate_employees(
        requirements=request.requirements,
        employees=request.employees,
        strategy=request.strategy,
    )

    return AllocationCreateResponse(allocations=allocations)


@router.post("/daily", response_model=DailyAllocationResponse)
async def create_daily_allocation(
    request: DailyAllocationRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Q.31.D.2 — atribui um operador a um barco para um dia (drag-drop).

    O serviço resolve a operação concreta a partir da `ProductionSchedule`.
    Ordem sem fase agendada para o dia → 409.
    """
    service = AllocationService(session, tenant_id)
    try:
        allocation = await service.create_single_allocation(
            employee_id=request.employee_id,
            order_id=request.order_id,
            allocation_date=request.allocation_date or date.today(),
            allocated_hours=Decimal(str(request.allocated_hours)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await session.commit()

    return DailyAllocationResponse(
        allocation_id=str(allocation.id),
        employee_id=str(allocation.employee_id),
        order_id=allocation.order_id,
        operation_id=str(allocation.operation_id),
        allocation_date=allocation.allocation_date.isoformat(),
        allocated_hours=float(allocation.allocated_hours),
        status=allocation.status.value,
    )


@router.get(
    "/employees/{employee_id}/availability",
    response_model=EmployeeAvailabilityResponse,
)
async def get_employee_availability(
    employee_id: UUID,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Get employee availability."""
    service = AllocationService(session, tenant_id)

    result = await service.get_employee_availability(
        employee_id=employee_id,
        from_date=from_date,
        to_date=to_date,
    )

    return EmployeeAvailabilityResponse(**result)


@router.get("/orders/{order_id}", response_model=OrderAllocationsResponse)
async def get_order_allocations(
    order_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Get allocations for an order.

    Sprint Q.12 — `estimated_cost` foi removido desta resposta porque
    deriva de `hourly_rate` (informação salarial sensível). Para custo
    consolidado usa o endpoint de payroll, que tem RBAC apropriado.
    """
    service = AllocationService(session, tenant_id)
    allocations = await service.get_allocations(order_id=order_id)

    return OrderAllocationsResponse(
        order_id=order_id,
        allocations=[
            OrderAllocationItem(
                id=str(a.id),
                employee_id=str(a.employee_id),
                operation_id=str(a.operation_id),
                allocated_hours=float(a.allocated_hours),
                status=a.status.value,
            )
            for a in allocations
        ],
    )










