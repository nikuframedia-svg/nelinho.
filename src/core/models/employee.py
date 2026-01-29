"""
ProdPlan ONE - Employee Model
==============================

Master data for employees (operators, technicians).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class EmploymentStatus(str, Enum):
    """Employment status."""
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    TERMINATED = "TERMINATED"
    SUSPENDED = "SUSPENDED"


class EmploymentType(str, Enum):
    """Employment type."""
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    TEMPORARY = "TEMPORARY"
    CONTRACTOR = "CONTRACTOR"


class Employee(TenantBase):
    """
    Employee entity.
    
    Represents production workers, operators, technicians.
    Linked to HR allocations and productivity tracking.
    """
    
    __tablename__ = "employees"
    __table_args__ = {"schema": "core"}
    
    # Identification
    employee_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Employment
    status: Mapped[EmploymentStatus] = mapped_column(
        SQLEnum(EmploymentStatus, name="employment_status"),
        default=EmploymentStatus.ACTIVE,
        nullable=False,
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        SQLEnum(EmploymentType, name="employment_type"),
        default=EmploymentType.FULL_TIME,
        nullable=False,
    )
    
    # Dates
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Organization
    department: Mapped[Optional[str]] = mapped_column(String(100))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    supervisor_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    
    # Work location
    work_center: Mapped[Optional[str]] = mapped_column(String(100))
    default_shift: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Compensation (monthly base)
    base_monthly_salary: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        default=Decimal("0"),
    )
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Burden rate (social charges, benefits %)
    burden_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.32"),  # 32% default
    )
    
    # Working hours
    weekly_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("40"),
    )
    
    # Skills (stored as JSON array of skill codes)
    skill_codes: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Certifications (JSON array)
    certifications: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Contact
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<Employee {self.employee_code}: {self.employee_name}>"
    
    @property
    def is_active(self) -> bool:
        return self.status == EmploymentStatus.ACTIVE
    
    @property
    def hourly_base_rate(self) -> Decimal:
        """Calculate base hourly rate from monthly salary."""
        if self.weekly_hours > 0:
            monthly_hours = self.weekly_hours * Decimal("4.33")  # ~4.33 weeks/month
            return self.base_monthly_salary / monthly_hours
        return Decimal("0")
    
    @property
    def hourly_loaded_rate(self) -> Decimal:
        """Calculate fully loaded hourly rate (base + burden)."""
        return self.hourly_base_rate * (1 + self.burden_rate)


