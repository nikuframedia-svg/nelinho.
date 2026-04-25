"""
ProdPlan ONE - Productivity API
================================
"""

from datetime import date
from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.hr.services.productivity_service import ProductivityService

router = APIRouter(prefix="/productivity", tags=["Productivity"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class ProductivityRecordRequest(BaseModel):
    """Productivity record request."""
    employee_id: UUID
    operation_id: UUID
    order_id: str
    record_date: date
    standard_hours: Decimal
    actual_hours: Decimal
    standard_quantity: Decimal
    actual_quantity: Decimal
    good_quantity: Decimal


@router.get("/")
async def list_productivity(
    startDate: date = None,
    endDate: date = None,
    employeeId: UUID = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List productivity records with optional filters."""
    from sqlalchemy import select, and_
    from src.hr.models.productivity import EmployeeProductivity
    
    # Build query with filters
    conditions = [EmployeeProductivity.tenant_id == tenant_id]
    
    if startDate:
        conditions.append(EmployeeProductivity.record_date >= startDate)
    if endDate:
        conditions.append(EmployeeProductivity.record_date <= endDate)
    if employeeId:
        conditions.append(EmployeeProductivity.employee_id == employeeId)
    
    query = select(EmployeeProductivity).where(and_(*conditions))
    result = await session.execute(query)
    records = list(result.scalars().all())
    
    return {
        "data": [
            {
                "id": str(r.id),
                "employee_id": str(r.employee_id),
                "operation_id": str(r.operation_id),
                "order_id": r.order_id,
                "record_date": r.record_date.isoformat(),
                "standard_hours": float(r.standard_hours),
                "actual_hours": float(r.actual_hours),
                "efficiency_percent": float(r.efficiency_percent),
                "quality_percent": float(r.quality_percent),
                "bonus_eligible": r.bonus_eligible,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.post("/record")
async def record_productivity(
    request: ProductivityRecordRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Record productivity."""
    service = ProductivityService(session, tenant_id)
    
    record = await service.record_productivity(
        employee_id=request.employee_id,
        operation_id=request.operation_id,
        order_id=request.order_id,
        record_date=request.record_date,
        standard_hours=request.standard_hours,
        actual_hours=request.actual_hours,
        standard_quantity=request.standard_quantity,
        actual_quantity=request.actual_quantity,
        good_quantity=request.good_quantity,
    )
    
    return {
        "id": str(record.id),
        "employee_id": str(record.employee_id),
        "efficiency_percent": float(record.efficiency_percent),
        "quality_percent": float(record.quality_percent),
        "bonus_eligible": record.bonus_eligible,
    }


@router.get("/employee/{employee_id}")
async def get_employee_productivity(
    employee_id: UUID,
    from_date: date = None,
    to_date: date = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get productivity for an employee."""
    service = ProductivityService(session, tenant_id)
    
    result = await service.get_employee_productivity(
        employee_id=employee_id,
        from_date=from_date,
        to_date=to_date,
    )
    
    return result


@router.get("/orders/{order_id}")
async def get_order_productivity(
    order_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get productivity for an order."""
    service = ProductivityService(session, tenant_id)
    
    result = await service.get_order_productivity(order_id=order_id)
    
    return result


@router.get("/report")
async def get_productivity_report(
    startDate: date,
    endDate: date,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregated productivity report for a date range."""
    # Endpoint uses the ORM directly; the service instance was unused dead code.
    from sqlalchemy import select, and_
    from src.hr.models.productivity import EmployeeProductivity
    
    query = select(EmployeeProductivity).where(
        and_(
            EmployeeProductivity.tenant_id == tenant_id,
            EmployeeProductivity.record_date >= startDate,
            EmployeeProductivity.record_date <= endDate,
        )
    )
    
    result = await session.execute(query)
    records = list(result.scalars().all())
    
    if not records:
        return {
            "start_date": startDate.isoformat(),
            "end_date": endDate.isoformat(),
            "total_records": 0,
            "total_employees": 0,
            "avg_efficiency_percent": 0,
            "avg_quality_percent": 0,
            "total_standard_hours": 0,
            "total_actual_hours": 0,
            "bonus_eligible_count": 0,
        }
    
    # Aggregate metrics
    total_std_hours = sum(r.standard_hours for r in records)
    total_act_hours = sum(r.actual_hours for r in records)
    total_act_qty = sum(r.actual_quantity for r in records)
    total_good_qty = sum(r.good_quantity for r in records)
    
    avg_efficiency = (total_std_hours / total_act_hours * 100) if total_act_hours > 0 else Decimal("0")
    avg_quality = (total_good_qty / total_act_qty * 100) if total_act_qty > 0 else Decimal("0")
    
    unique_employees = len(set(r.employee_id for r in records))
    bonus_eligible_count = sum(1 for r in records if r.bonus_eligible)
    
    return {
        "start_date": startDate.isoformat(),
        "end_date": endDate.isoformat(),
        "total_records": len(records),
        "total_employees": unique_employees,
        "avg_efficiency_percent": float(avg_efficiency),
        "avg_quality_percent": float(avg_quality),
        "total_standard_hours": float(total_std_hours),
        "total_actual_hours": float(total_act_hours),
        "bonus_eligible_count": bonus_eligible_count,
    }



