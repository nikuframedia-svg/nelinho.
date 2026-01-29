"""
ProdPlan ONE - Allocations API
===============================
"""

from datetime import date
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.hr.services.allocation_service import AllocationService

router = APIRouter(prefix="/allocations", tags=["Allocations"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class AllocationRequest(BaseModel):
    """Allocation request."""
    requirements: List[Dict[str, Any]]
    employees: List[Dict[str, Any]]
    strategy: str = "skill_first"


@router.post("/create")
async def create_allocations(
    request: AllocationRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create employee allocations."""
    service = AllocationService(session, tenant_id)
    
    allocations = await service.allocate_employees(
        requirements=request.requirements,
        employees=request.employees,
        strategy=request.strategy,
    )
    
    return {"allocations": allocations}


@router.get("/employees/{employee_id}/availability")
async def get_employee_availability(
    employee_id: UUID,
    from_date: date = None,
    to_date: date = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get employee availability."""
    service = AllocationService(session, tenant_id)
    
    result = await service.get_employee_availability(
        employee_id=employee_id,
        from_date=from_date,
        to_date=to_date,
    )
    
    return result


@router.get("/orders/{order_id}")
async def get_order_allocations(
    order_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get allocations for an order."""
    service = AllocationService(session, tenant_id)
    allocations = await service.get_allocations(order_id=order_id)
    
    return {
        "order_id": order_id,
        "allocations": [
            {
                "id": str(a.id),
                "employee_id": str(a.employee_id),
                "operation_id": str(a.operation_id),
                "allocated_hours": float(a.allocated_hours),
                "estimated_cost": float(a.estimated_cost),
                "status": a.status.value,
            }
            for a in allocations
        ],
    }










