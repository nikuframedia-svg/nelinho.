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

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey, Date, Time, Boolean, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase

# Sprint Q.12 — limite legal português (Lei 7/2009, art. 203):
# 8h normal, 10h máximo com banco de horas / compensação. Acima de 10h
# rejeitamos por defeito; turno noturno limitado a 8h.
_MAX_DAILY_HOURS_NORMAL = 8.0
_MAX_DAILY_HOURS_WITH_OVERTIME = 10.0


class IllegalShiftDurationError(ValueError):
    """Raised quando um turno excede o limite legal diário."""


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

    @staticmethod
    def _shift_duration_hours(start: time, end: time, break_minutes: int) -> float:
        """Calcula horas líquidas, incluindo travessia de meia-noite."""
        start_min = start.hour * 60 + start.minute
        end_min = end.hour * 60 + end.minute
        if end_min <= start_min:
            # Turno que cruza meia-noite (ex: 22:00 → 06:00)
            end_min += 24 * 60
        gross_hours = (end_min - start_min) / 60.0
        return max(0.0, gross_hours - (break_minutes / 60.0))


def _validate_shift_legal_hours(mapper, _connection, target: "ShiftSchedule") -> None:
    """SQLAlchemy listener — bloqueia turnos > 10h e calcula `net_hours`.

    Sprint Q.12: a Lei portuguesa 7/2009 (art. 203) estabelece 8h
    normal, 10h máximo. Antes era possível registar `08:00–20:00` (12h)
    sem aviso. `net_hours` ficava `null` por nunca ser calculado.
    """
    if target.start_time is None or target.end_time is None:
        return
    net = ShiftSchedule._shift_duration_hours(
        target.start_time, target.end_time, target.break_minutes or 0
    )
    target.net_hours = Decimal(str(round(net, 2)))
    if net > _MAX_DAILY_HOURS_WITH_OVERTIME:
        raise IllegalShiftDurationError(
            f"Turno de {net:.2f}h excede o limite legal português "
            f"(máx {_MAX_DAILY_HOURS_WITH_OVERTIME}h/dia com compensação)"
        )
    if net > _MAX_DAILY_HOURS_NORMAL and not target.is_overtime:
        raise IllegalShiftDurationError(
            f"Turno de {net:.2f}h excede {_MAX_DAILY_HOURS_NORMAL}h/dia "
            "sem flag is_overtime — marcar como horas extra"
        )


event.listen(ShiftSchedule, "before_insert", _validate_shift_legal_hours)
event.listen(ShiftSchedule, "before_update", _validate_shift_legal_hours)


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


