"""
ProdPlan ONE - HR Allocation Models
====================================
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey, Date, Time, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class AllocationStatus(str, Enum):
    """Allocation status."""
    PLANNED = "PLANNED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HRAllocation(TenantBase):
    """
    HR Allocation entity.
    
    Assigns employees to production operations.
    """
    
    __tablename__ = "hr_allocations"
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
    
    # Allocation details
    allocation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[Optional[time]] = mapped_column(Time)
    end_time: Mapped[Optional[time]] = mapped_column(Time)
    
    # Hours
    allocated_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    actual_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    
    # Cost
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    
    # Status
    status: Mapped[AllocationStatus] = mapped_column(
        SQLEnum(AllocationStatus, name="allocation_status"),
        default=AllocationStatus.PLANNED,
    )
    
    # Skill match
    skill_match: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<Allocation {self.employee_id} -> {self.order_id}: {self.allocated_hours}h>"


class ShiftType(str, Enum):
    """Shift type."""
    DAY = "DAY"
    EVENING = "EVENING"
    NIGHT = "NIGHT"
    SPLIT = "SPLIT"


class ShiftSchedule(TenantBase):
    """
    Shift Schedule entity.
    
    Defines shift patterns for employees.
    """
    
    __tablename__ = "shift_schedules"
    __table_args__ = {"schema": "hr"}
    
    # Employee
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=False,
        index=True,
    )
    
    # Shift
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_type: Mapped[ShiftType] = mapped_column(
        SQLEnum(ShiftType, name="shift_type"),
        default=ShiftType.DAY,
    )
    
    # Times
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=60)
    
    # Calculated
    net_hours: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    
    # Overrides
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False)
    overtime_multiplier: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    
    # Status
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self) -> str:
        return f"<Shift {self.employee_id} @ {self.shift_date}: {self.shift_type.value}>"


class Skill(TenantBase):
    """
    Skill entity.
    
    Defines available skills/competencies.
    """
    
    __tablename__ = "skills"
    __table_args__ = {"schema": "hr"}
    
    skill_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Certification
    requires_certification: Mapped[bool] = mapped_column(Boolean, default=False)
    certification_validity_months: Mapped[Optional[int]] = mapped_column(Integer)
    
    def __repr__(self) -> str:
        return f"<Skill {self.skill_code}: {self.skill_name}>"


class ProficiencyLevel(int, Enum):
    """Proficiency levels."""
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4
    MASTER = 5


class EmployeeSkill(TenantBase):
    """
    Employee Skill mapping.
    
    Links employees to skills with proficiency.
    """
    
    __tablename__ = "employee_skills"
    __table_args__ = {"schema": "hr"}
    
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hr.skills.id"),
        nullable=False,
    )
    
    proficiency_level: Mapped[int] = mapped_column(Integer, default=1)
    
    # Certification
    is_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    certification_date: Mapped[Optional[date]] = mapped_column(Date)
    certification_expiry: Mapped[Optional[date]] = mapped_column(Date)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<EmpSkill {self.employee_id} has {self.skill_id} @L{self.proficiency_level}>"


