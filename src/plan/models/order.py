"""
ProdPlan ONE - Production Order Model
======================================

Model for production orders (legacy compatibility).
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, String, Integer, Date, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class OrderStatus(str, Enum):
    """Order status."""
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProductionOrder(TenantBase):
    """
    Production Order entity (legacy compatibility).
    
    Stores production orders from the legacy SQLite database.
    """
    
    __tablename__ = "production_orders"
    __table_args__ = (
        Index("ix_production_orders_created_date", "created_date"),
        Index("ix_production_orders_status", "status"),
        Index("ix_production_orders_product_type", "product_type"),
        Index("ix_production_orders_current_phase", "current_phase_name"),
        {"schema": "plan"},
    )
    
    # Note: No foreign keys to avoid dependency issues during migration
    
    # Legacy ID (from SQLite)
    legacy_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    
    # Product
    product_id: Mapped[Optional[int]] = mapped_column(Integer)  # Legacy product ID
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[str] = mapped_column(String(50))  # K1, K2, K4, C1, C2, C4, Other
    
    # Phase
    current_phase_id: Mapped[Optional[int]] = mapped_column(Integer)
    current_phase_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Dates
    created_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_date: Mapped[Optional[date]] = mapped_column(Date)
    transport_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Status
    status: Mapped[OrderStatus] = mapped_column(
        String(20),
        default=OrderStatus.IN_PROGRESS,
        nullable=False,
    )
    
    # ── Q.115.X5 — Soft-cancel ───────────────────────────────────────────────
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Order {self.legacy_id}: {self.product_name} ({self.status.value})>"
