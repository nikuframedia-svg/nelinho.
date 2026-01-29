"""
ProdPlan ONE - Operation Model
===============================

Standard operations (routing steps) for production.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class OperationType(str, Enum):
    """Operation type classification."""
    PRODUCTION = "PRODUCTION"
    SETUP = "SETUP"
    INSPECTION = "INSPECTION"
    PACKAGING = "PACKAGING"
    TRANSPORT = "TRANSPORT"


class Operation(TenantBase):
    """
    Standard Operation entity.
    
    Represents a step in the production routing.
    Defines standard times, required skills, and machine assignments.
    """
    
    __tablename__ = "operations"
    __table_args__ = {"schema": "core"}
    
    # Identification
    operation_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    operation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Classification
    operation_type: Mapped[OperationType] = mapped_column(
        SQLEnum(OperationType, name="operation_type"),
        default=OperationType.PRODUCTION,
        nullable=False,
    )
    
    # Machine assignment (NULL for manual operations)
    machine_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.machines.id"),
    )
    
    # Alternative machines (JSON array of machine IDs)
    alternative_machines: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Standard times
    std_time_minutes: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
    )
    setup_time_minutes: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0"),
    )
    
    # Calculated field (stored for convenience)
    std_time_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
    )
    
    # Required skills (JSON array of skill codes)
    skills_required: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Setup family (for setup matrix calculations)
    setup_family: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Capacity
    batch_size: Mapped[int] = mapped_column(Integer, default=1)
    min_batch_size: Mapped[int] = mapped_column(Integer, default=1)
    
    # Sequencing
    default_sequence: Mapped[int] = mapped_column(Integer, default=0)
    
    # Subcontracting
    is_subcontracted: Mapped[bool] = mapped_column(default=False)
    subcontract_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(Text)
    work_instructions: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<Operation {self.operation_code}: {self.operation_name}>"
    
    @property
    def is_manual(self) -> bool:
        return self.machine_id is None
    
    def calculate_duration(self, quantity: int) -> Decimal:
        """Calculate total duration for a quantity."""
        return (self.std_time_minutes * quantity) + self.setup_time_minutes
    
    def calculate_duration_hours(self, quantity: int) -> Decimal:
        """Calculate total duration in hours."""
        return self.calculate_duration(quantity) / 60










