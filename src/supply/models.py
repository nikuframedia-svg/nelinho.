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

from sqlalchemy import Boolean, String, Integer, Float, Date, DateTime, Numeric, Text, func
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


# ============================================================================
# Sprint O.1 — Material master + in-transit + reconciliation
# ============================================================================

class MaterialMaster(TenantBase):
    """Raw-material master record (MR01/MR05).

    Controls what Sprint O.4 flags as a shortage: a material is scanned iff
    `active=True`, and alerts compare `on_hand + in_transit` against
    `min_stock_qty`. The `critical_flag` is a business marker that raises
    severity from WARN to CRITICAL when tripped.

    NOTE: `sku_id` stays a free-form string (matching `InventoryLedgerEntry`
    and `ROPConfig`) so the ledger continues to work without a UUID
    migration. The uniqueness constraint keeps one row per (tenant, sku).
    """

    __tablename__ = "supply_material_master"
    __table_args__ = {"schema": "supply"}

    sku_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False, default="UN")
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    default_supplier_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )
    # Duplicate of Supplier.lead_time_days so MRP can keep a per-material
    # override when the supplier's default doesn't match reality.
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    # MR05 — min_stock_qty is the "high default" the blueprint calls for.
    # Multiplied at read-time by supply.safety_multiplier (Sprint L.4 config).
    min_stock_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"),
    )
    reorder_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"),
    )
    safety_stock_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    critical_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MaterialInTransit(TenantBase):
    """A pending receipt. One row per `PurchaseOrder` line in flight.

    Sprint O.2 `get_position()` sums `qty` over rows with
    `eta <= horizon` so the UI can show "X units arriving within 14 days".
    Status `OPEN` = in flight; `RECEIVED`/`CANCELLED` are terminal.
    """

    __tablename__ = "supply_material_in_transit"
    __table_args__ = {"schema": "supply"}

    sku_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    purchase_order_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    eta: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    supplier_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StockReconciliation(TenantBase):
    """Physical count vs theoretical ledger variance (ST03).

    `resolved=False` until an adjustment is recorded. Because the adjustment
    is the one-and-only source of truth, resolving simply pivots to an
    `InventoryLedgerEntry` with `transaction_type="adjust"` and marks this
    row resolved.
    """

    __tablename__ = "supply_stock_reconciliation"
    __table_args__ = {"schema": "supply"}

    sku_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    theoretical_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    physical_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    variance_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    variance_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    counted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(),
    )
    counted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_ledger_entry_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )


