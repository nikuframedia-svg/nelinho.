"""
ProdPlan ONE - Payroll API
===========================
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import AdminContext, require_admin, require_tenant_header
from src.shared.database import get_session
from src.hr.services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["Payroll"])


# ─── Schemas ──────────────────────────────────────────────────────────────────


class PayrollCalculateRequest(BaseModel):
    """Payroll calculation request."""
    year_month: date
    burden_rate: Decimal = Decimal("0.32")
    overtime_multiplier: Decimal = Decimal("1.5")

    @field_validator("year_month")
    @classmethod
    def _validate_year_month(cls, v: date) -> date:
        # Sprint Q.12 — rejeitar futuro e anos absurdos.
        if v.year < 2020 or v > date.today():
            raise ValueError(
                "year_month deve estar entre 2020 e hoje"
            )
        return v


class EmployeePayrollSummary(BaseModel):
    employee_id: str
    total_hours: float
    regular_hours: float
    overtime_hours: float
    total_cost: float


class PayrollCalculateResponse(BaseModel):
    year_month: str
    employee_count: int
    total_hours: float
    regular_hours: float
    overtime_hours: float
    regular_cost: float
    overtime_cost: float
    burden_cost: float
    total_cost: float
    employee_summaries: List[EmployeePayrollSummary]


class LabourCostSummaryResponse(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    order_id: Optional[str] = None
    employee_id: Optional[str] = None
    allocated_hours: float
    actual_hours: float
    estimated_cost: float
    actual_cost: float
    allocation_count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/calculate", response_model=PayrollCalculateResponse)
async def calculate_payroll(
    request: PayrollCalculateRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    _admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Calculate monthly payroll. Admin-only — payroll figures are
    sensitive financial data."""
    service = PayrollService(session, tenant_id)

    result = await service.calculate_monthly_payroll(
        year_month=request.year_month,
        burden_rate=request.burden_rate,
        overtime_multiplier=request.overtime_multiplier,
    )

    return PayrollCalculateResponse(**result)


@router.get("/monthly-cost", response_model=LabourCostSummaryResponse)
async def get_monthly_cost(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Get labor cost summary."""
    service = PayrollService(session, tenant_id)

    result = await service.get_labor_cost(
        from_date=from_date,
        to_date=to_date,
    )

    return LabourCostSummaryResponse(**result)










