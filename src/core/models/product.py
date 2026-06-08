"""
ProdPlan ONE - Product Model
=============================

Master data for products (finished goods, semi-finished, raw materials).
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import TenantBase


class ProductType(str, Enum):
    """Product type classification."""
    FINISHED_GOOD = "FINISHED_GOOD"
    SEMI_FINISHED = "SEMI_FINISHED"
    RAW_MATERIAL = "RAW_MATERIAL"
    PACKAGING = "PACKAGING"
    CONSUMABLE = "CONSUMABLE"


class ProductStatus(str, Enum):
    """Product lifecycle status."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DISCONTINUED = "DISCONTINUED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


class Product(TenantBase):
    """
    Product entity.
    
    Represents any item in the production system:
    - Finished goods (K1 Vanquish, K2 Quantium, etc.)
    - Semi-finished goods (sub-assemblies)
    - Raw materials (steel, wood, etc.)
    - Packaging materials
    """
    
    __tablename__ = "products"
    __table_args__ = {"schema": "core"}
    
    # Identification
    product_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Classification
    product_type: Mapped[ProductType] = mapped_column(
        SQLEnum(ProductType, name="product_type"),
        default=ProductType.FINISHED_GOOD,
        nullable=False,
    )
    category: Mapped[Optional[str]] = mapped_column(String(100))
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Status
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(ProductStatus, name="product_status"),
        default=ProductStatus.ACTIVE,
        nullable=False,
    )
    
    # BOM versioning
    bom_version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Planning parameters
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    safety_stock: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        default=Decimal("0"),
    )
    min_order_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        default=Decimal("1"),
    )
    order_multiple: Mapped[Decimal] = mapped_column(
        Numeric(18, 6),
        default=Decimal("1"),
    )
    
    # Costing
    standard_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    # Q.167.F — ERP `P_TP_ID` (raw product-type id). Necessário para o COGS
    # aplicar o factor de correcção de mão-de-obra do ERP (VAR_ID=2) aos
    # componentes P_TP_ID=90. Nullable: produtos não-ERP / sincronizados antes
    # desta coluna ficam NULL e nunca recebem o factor (= `else 1` do ERP).
    erp_product_type_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Units
    base_unit: Mapped[str] = mapped_column(String(10), default="UN")
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Customer reference (for finished goods)
    customer_product_code: Mapped[Optional[str]] = mapped_column(String(100))
    
    # ── Q.115.X5 — Soft-retire ───────────────────────────────────────────────
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retirement_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Product {self.product_code}: {self.product_name}>"

    @property
    def is_finished_good(self) -> bool:
        return self.product_type == ProductType.FINISHED_GOOD
    
    @property
    def is_purchaseable(self) -> bool:
        return self.product_type in (
            ProductType.RAW_MATERIAL,
            ProductType.PACKAGING,
            ProductType.CONSUMABLE,
        )
    
    @property
    def is_manufacturable(self) -> bool:
        return self.product_type in (
            ProductType.FINISHED_GOOD,
            ProductType.SEMI_FINISHED,
        )










