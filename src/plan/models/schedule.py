"""
ProdPlan ONE - Production Schedule Model
=========================================
"""

from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey, Date, Time
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class ScheduleStatus(str, Enum):
    """Schedule status."""
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProductionSchedule(TenantBase):
    """
    Production Schedule entity.
    
    Stores scheduled operations for production orders.
    """
    
    __tablename__ = "production_schedules"
    __table_args__ = {"schema": "plan"}
    
    # Order reference
    order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_line: Mapped[int] = mapped_column(Integer, default=1)
    
    # Product
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Operation
    operation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.operations.id"),
        nullable=False,
    )
    operation_sequence: Mapped[int] = mapped_column(Integer, default=0)
    
    # Machine
    machine_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.machines.id"),
    )
    
    # Scheduling
    scheduled_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_start_time: Mapped[Optional[time]] = mapped_column(Time)
    scheduled_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_end_time: Mapped[Optional[time]] = mapped_column(Time)
    
    # Duration
    scheduled_duration_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    setup_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Employee assignment (from HR module)
    assigned_employee_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    
    # Status
    status: Mapped[ScheduleStatus] = mapped_column(
        SQLEnum(ScheduleStatus, name="schedule_status"),
        default=ScheduleStatus.SCHEDULED,
    )
    
    # Actuals
    actual_start: Mapped[Optional[datetime]] = mapped_column()
    actual_end: Mapped[Optional[datetime]] = mapped_column()
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    
    # Batch info
    batch_number: Mapped[Optional[str]] = mapped_column(String(50))
    sequence_in_machine: Mapped[int] = mapped_column(Integer, default=0)
    
    # Planning metadata
    planning_run_id: Mapped[Optional[str]] = mapped_column(String(50))
    engine_used: Mapped[Optional[str]] = mapped_column(String(50))

    # FASE 1B.4 (CRIT-23) — fields the CPO decoder produces per op that
    # the service layer used to drop. Surfaced in the ORM so they
    # actually persist and downstream queries (auditoria, copilot fact
    # packs, twin scenarios) can read them.
    rule_used: Mapped[Optional[str]] = mapped_column(String(32))
    mold_batch_id: Mapped[Optional[str]] = mapped_column(String(64))
    infeasible_reason: Mapped[Optional[str]] = mapped_column(String(255))

    # Sprint R.2 — quality risk score (added in migration 019 but not in
    # the ORM until FASE 1B.4 surfaced the drift). Range 0.0-1.0,
    # rounded to 4 decimals matching Numeric(5, 4) in the DB.
    quality_risk_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4),
    )
    quality_risk_scored_at: Mapped[Optional[datetime]] = mapped_column()

    def __repr__(self) -> str:
        return f"<Schedule {self.order_id} op={self.operation_sequence} @ {self.scheduled_start_date}>"


