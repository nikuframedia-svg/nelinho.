"""
ProdPlan ONE - Payroll API
===========================
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.hr.services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["Payroll"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class PayrollCalculateRequest(BaseModel):
    """Payroll calculation request."""
    year_month: date
    burden_rate: Decimal = Decimal("0.32")
    overtime_multiplier: Decimal = Decimal("1.5")


@router.post("/calculate")
async def calculate_payroll(
    request: PayrollCalculateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Calculate monthly payroll."""
    service = PayrollService(session, tenant_id)
    
    result = await service.calculate_monthly_payroll(
        year_month=request.year_month,
        burden_rate=request.burden_rate,
        overtime_multiplier=request.overtime_multiplier,
    )
    
    return result


@router.get("/monthly-cost")
async def get_monthly_cost(
    from_date: date = None,
    to_date: date = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get labor cost summary."""
    service = PayrollService(session, tenant_id)
    
    result = await service.get_labor_cost(
        from_date=from_date,
        to_date=to_date,
    )
    
    return result










