"""
ProdPlan ONE - Machine Model
=============================

Master data for machines and work centers.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class MachineStatus(str, Enum):
    """Machine operational status."""
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    BREAKDOWN = "BREAKDOWN"
    RETIRED = "RETIRED"


class MachineType(str, Enum):
    """Machine type classification."""
    CNC = "CNC"
    PRESS = "PRESS"
    GRINDING = "GRINDING"
    ASSEMBLY = "ASSEMBLY"
    PACKAGING = "PACKAGING"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class Machine(TenantBase):
    """
    Machine entity.
    
    Represents production equipment and work centers.
    Linked to operations for scheduling and capacity planning.
    """
    
    __tablename__ = "machines"
    __table_args__ = {"schema": "core"}
    
    # Identification
    machine_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    machine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Classification
    machine_type: Mapped[MachineType] = mapped_column(
        SQLEnum(MachineType, name="machine_type"),
        default=MachineType.OTHER,
        nullable=False,
    )
    
    # Status
    status: Mapped[MachineStatus] = mapped_column(
        SQLEnum(MachineStatus, name="machine_status"),
        default=MachineStatus.ACTIVE,
        nullable=False,
    )
    
    # Location
    location: Mapped[Optional[str]] = mapped_column(String(100))
    work_center: Mapped[Optional[str]] = mapped_column(String(100))
    line: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Capacity
    capacity_units_per_hour: Mapped[Optional[int]] = mapped_column(Integer)
    speed_factor: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("1.0"),
    )
    
    # Availability
    available_hours_per_day: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        default=Decimal("8.0"),
    )
    available_days_per_week: Mapped[int] = mapped_column(Integer, default=5)
    
    # Maintenance
    maintenance_window: Mapped[Optional[str]] = mapped_column(Text)
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column()
    next_maintenance_date: Mapped[Optional[datetime]] = mapped_column()
    
    # Shifts configuration (JSON)
    shifts_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Capabilities (JSON list of operation codes this machine can perform)
    capabilities: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Energy & Costing
    power_kw: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(Text)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    installation_date: Mapped[Optional[datetime]] = mapped_column()
    
    def __repr__(self) -> str:
        return f"<Machine {self.machine_code}: {self.machine_name}>"
    
    @property
    def is_available(self) -> bool:
        return self.status == MachineStatus.ACTIVE
    
    @property
    def weekly_capacity_hours(self) -> Decimal:
        return self.available_hours_per_day * self.available_days_per_week
    
    @property
    def weekly_capacity_minutes(self) -> Decimal:
        return self.weekly_capacity_hours * 60










