"""
ProdPlan ONE - Allocations API
===============================
"""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
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










