"""
ProdPlan ONE - HR Productivity Models
======================================
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, ForeignKey, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class EmployeeProductivity(TenantBase):
    """
    Employee Productivity entity.
    
    Records actual vs standard performance.
    """
    
    __tablename__ = "employee_productivity"
    __table_args__ = {"schema": "hr"}
    
    # Employee
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=False,
        index=True,
    )
    
    # Operation/Order
    order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    operation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.operations.id"),
        nullable=False,
    )
    
    # Date
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Time
    standard_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    
    # Quantity
    standard_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    
    # Calculated metrics
    efficiency_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    quality_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    
    # Bonus eligibility
    bonus_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<Productivity {self.employee_id} @ {self.record_date}: {self.efficiency_percent}%>"


class MonthlyPayrollSummary(TenantBase):
    """
    Monthly Payroll Summary entity.
    
    Aggregates labor costs by month.
    """
    
    __tablename__ = "monthly_payroll_summary"
    __table_args__ = {"schema": "hr"}
    
    # Period
    year_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Employee (NULL for department/company totals)
    employee_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
    )
    department: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Hours
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    total_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    
    # Costs
    regular_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    overtime_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    burden_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    
    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Metrics
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_efficiency_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    
    def __repr__(self) -> str:
        return f"<Payroll {self.year_month}: {self.total_cost} EUR>"


