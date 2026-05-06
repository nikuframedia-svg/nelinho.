"""
ProdPlan ONE - Legacy Allocation Model
======================================

Model for legacy allocations (from SQLite migration).

DEPRECATED (Sprint Q.12): only the SQLAlchemy class is kept so Alembic
autogenerate doesn't propose dropping the table. No service code reads
from it anymore — `HRAllocation` em ``src.hr.models.allocation`` is the
canonical model. Remove together with the corresponding table in a
future sprint after confirming nothing in `factory_data_product`
ingestion still backfills it.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Integer, Date, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class LegacyAllocation(TenantBase):
    """
    Legacy Allocation entity.
    
    Stores employee allocations from the legacy SQLite database.
    """
    
    __tablename__ = "legacy_allocations"
    __table_args__ = (
        Index("ix_legacy_allocations_start_date", "start_date"),
        Index("ix_legacy_allocations_employee_id", "employee_id"),
        Index("ix_legacy_allocations_phase_name", "phase_name"),
        Index("ix_legacy_allocations_order_id", "order_id"),
        {"schema": "hr"},
    )
    
    # Order and Phase
    order_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    phase_id: Mapped[Optional[int]] = mapped_column(Integer)
    phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Employee
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Role
    is_leader: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Dates
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    
    def __repr__(self) -> str:
        return f"<LegacyAllocation {self.employee_name} -> Order {self.order_id} ({self.phase_name})>"
