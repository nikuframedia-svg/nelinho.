"""
ProdPlan ONE - Employees API
=============================

REST endpoints for employee management.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.core.models.employee import EmploymentStatus
from src.core.services.master_data_service import MasterDataService
from .schemas import EmployeeCreate, EmployeeUpdate, EmployeeResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Create a new employee."""
    service = MasterDataService(session, tenant_id)
    
    employee = await service.create_employee(
        employee_code=data.employee_code,
        employee_name=data.employee_name,
        hire_date=data.hire_date,
        department=data.department,
        base_monthly_salary=data.base_monthly_salary,
        burden_rate=data.burden_rate,
    )
    
    return employee


@router.get("", response_model=List[EmployeeResponse])
async def list_employees(
    status: EmploymentStatus = None,
    department: str = None,
    limit: int = 100,
    offset: int = 0,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List employees with optional filtering."""
    from src.shared.pagination import validate_pagination
    validate_pagination(limit, offset)
    try:
        service = MasterDataService(session, tenant_id)
        employees = await service.list_employees(
            status=status,
            department=department,
            limit=limit,
            offset=offset,
        )
        return employees
    except (ConnectionRefusedError, Exception) as e:
        # DB unavailable - return fallback data
        import logging
        logger = logging.getLogger(__name__)
        error_str = str(e).lower()
        if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
            logger.warning(f"DB unavailable in list_employees, returning fallback: {e}")
            return []
        # Re-raise other exceptions (they'll be handled by global handler)
        raise


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get employee by ID."""
    service = MasterDataService(session, tenant_id)
    employee = await service.get_employee(employee_id)
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )
    
    return employee


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: UUID,
    data: EmployeeUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Update employee."""
    service = MasterDataService(session, tenant_id)
    
    updates = {}
    if data.employee_name is not None:
        updates["employee_name"] = data.employee_name
    if data.department is not None:
        updates["department"] = data.department
    if data.job_title is not None:
        updates["job_title"] = data.job_title
    if data.base_monthly_salary is not None:
        updates["base_monthly_salary"] = data.base_monthly_salary
    if data.status is not None:
        updates["status"] = data.status
    if data.notes is not None:
        updates["notes"] = data.notes

    employee = await service.update_employee(employee_id, **updates)
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )
    
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete employee."""
    service = MasterDataService(session, tenant_id)
    deleted = await service.delete_employee(employee_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee {employee_id} not found",
        )
    
    return None


