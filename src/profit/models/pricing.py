"""
ProdPlan ONE - Pricing / Revenue / Shipping models (Sprint Q.0 / Q.2)
======================================================================

Blueprint v2.0 CS01-CS06 + CG13 demand explicit revenue data so the CPO
fitness function (P.6) can maximise throughput €/dia and the Factory Map
(N.6) can surface the €30–35K/dia target. Three new tables drive this:

* **ProductPricing** — per-product list price, versioned by `valid_from`.
  A single product can have many rows; the "current" one is the most
  recent with `valid_from <= today`.
* **OrderRevenue** — per-order override that wins over ProductPricing
  when present. Populated by the ERP sync (Sprint T) or by hand for
  exceptional deals.
* **ShippingRate** — flat freight cost per (destination, sku_category).
  Kept deliberately simple — a formula engine lives in Sprint U.

All three tables are tenant-scoped. Currency defaults to EUR per
Blueprint §1 ("Cliente: NELO, Portugal") but the column is open for
future multi-currency support.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class ProductPricing(TenantBase):
    """Per-product list price with a validity start date.

    The "current" row for `product_id=X` is the latest `valid_from <= today`
    WHERE `active=True`. Admins edit via `POST /v1/profit/pricing/products/{id}`.
    """

    __tablename__ = "product_pricing"
    __table_args__ = (
        Index("ix_product_pricing_product", "product_id"),
        Index("ix_product_pricing_tenant_product_valid",
              "tenant_id", "product_id", "valid_from"),
        UniqueConstraint(
            "tenant_id", "product_id", "valid_from",
            name="uq_product_pricing_validity",
        ),
        {"schema": "profit"},
    )

    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
    )
    sale_value_default_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    valid_from: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today,
    )
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OrderRevenue(TenantBase):
    """Explicit per-order revenue, overriding `ProductPricing`."""

    __tablename__ = "order_revenue"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "order_id",
            name="uq_order_revenue_order",
        ),
        Index("ix_order_revenue_tenant_order", "tenant_id", "order_id"),
        {"schema": "profit"},
    )

    order_id: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("1"),
    )
    unit_price_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_revenue_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    recognised_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")


class ShippingRate(TenantBase):
    """Flat shipping cost lookup. Resolution order: (destination, category)
    → (destination, ANY) → (ANY, ANY). The `cost_formula_expr` column is a
    free-form string for Sprint U where we introduce simple evaluator
    templates; today callers use `flat_cost_eur`.
    """

    __tablename__ = "shipping_rate"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "destination", "sku_category",
            name="uq_shipping_rate_dest_category",
        ),
        Index("ix_shipping_rate_dest", "destination"),
        {"schema": "profit"},
    )

    destination: Mapped[str] = mapped_column(String(100), nullable=False, default="ANY")
    sku_category: Mapped[str] = mapped_column(String(64), nullable=False, default="ANY")
    flat_cost_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0"),
    )
    cost_formula_expr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
