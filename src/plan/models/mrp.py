"""
ProdPlan ONE - MRP Models
==========================
"""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class RequirementType(str, Enum):
    """Requirement type."""
    GROSS = "GROSS"
    NET = "NET"
    PLANNED = "PLANNED"


class MaterialRequirement(TenantBase):
    """
    Material Requirement entity.
    
    Stores MRP calculation results.
    """
    
    __tablename__ = "material_requirements"
    __table_args__ = {"schema": "plan"}
    
    # MRP run reference
    mrp_run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Material
    material_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
        index=True,
    )
    
    # Requirements
    gross_requirement: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    on_hand_inventory: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    on_order_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    net_requirement: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    
    # Planning
    order_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=0)
    order_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    
    # Supplier
    supplier_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.suppliers.id"),
    )
    
    # Status
    is_purchased: Mapped[bool] = mapped_column(default=True)
    po_created: Mapped[bool] = mapped_column(default=False)
    
    def __repr__(self) -> str:
        return f"<MaterialReq {self.material_id}: {self.net_requirement}>"


class POStatus(str, Enum):
    """Purchase order status."""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ORDERED = "ORDERED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class PurchaseOrder(TenantBase):
    """
    Purchase Order entity.
    
    Generated from MRP.
    """
    
    __tablename__ = "purchase_orders"
    __table_args__ = {"schema": "plan"}
    
    # PO identification
    po_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # Supplier
    supplier_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.suppliers.id"),
        nullable=False,
    )
    
    # Material
    material_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
    )
    
    # Quantity & Cost
    order_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(10), default="UN")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Dates
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_date: Mapped[Optional[date]] = mapped_column(Date)
    
    # Status
    status: Mapped[POStatus] = mapped_column(
        SQLEnum(POStatus, name="po_status"),
        default=POStatus.DRAFT,
    )
    
    # MRP reference
    mrp_run_id: Mapped[Optional[str]] = mapped_column(String(50))
    source_requirement_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    def __repr__(self) -> str:
        return f"<PO {self.po_number}: {self.order_quantity} of {self.material_id}>"


