"""
ProdPlan ONE - Supply Chain Models
===================================

SQLAlchemy models for Supply Chain Planning.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, Float, Date, DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class InventoryLedgerEntry(TenantBase):
    """
    Inventory ledger entry (event sourcing pattern).
    
    Tracks all inventory movements (receipts, consumptions, adjustments)
    to maintain complete historical record.
    """
    
    __tablename__ = "inventory_ledger_entries"
    __table_args__ = {"schema": "supply"}
    
    sku_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    qty_opening: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    qty_in: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))  # Receipts
    qty_out: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))  # Consumptions
    qty_closing: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))  # On-hand after
    
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'consume', 'receive', 'adjust'
    reference_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)  # operation_id or po_id


class SupplyForecast(TenantBase):
    """
    Supply forecast for a SKU.
    
    Stores forecast history for demand planning.
    """
    
    __tablename__ = "supply_forecasts"
    __table_args__ = {"schema": "supply"}
    
    sku_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    qty_p50: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # Median forecast
    qty_p90: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)  # Upper interval
    
    wmape: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Weighted MAPE
    quality: Mapped[str] = mapped_column(String(10), nullable=False)  # 'good', 'fair', 'poor'
    
    periods_ahead: Mapped[int] = mapped_column(Integer, nullable=False)


class ROPConfig(TenantBase):
    """
    Reorder Point (ROP) configuration for a SKU.
    
    Calculated ROP with safety stock for inventory management.
    """
    
    __tablename__ = "supply_rop_configs"
    __table_args__ = {"schema": "supply"}
    
    sku_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    avg_daily_demand: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_std_dev: Mapped[float] = mapped_column(Float, nullable=False)
    service_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    
    rop: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    base_rop: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


