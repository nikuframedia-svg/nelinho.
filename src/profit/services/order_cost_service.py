"""
ProdPlan ONE - Order Cost Service (Sprint Q.2 / CS02)
======================================================

Aggregates the cost of a single order: COGS (per-unit × qty, via the
existing COGSCalculator) + shipping (ShippingRate lookup). Used by the
MarginCalculator (Q.3), the SKU profitability endpoint (Q.4), and the
dashboard (Q.5).

Thin — the arithmetic stays in the dataclass so tests can drive it with
stubbed repos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.pricing import OrderRevenue, ShippingRate


@dataclass
class OrderCost:
    order_id: str
    cogs_eur: Decimal = Decimal("0")
    shipping_eur: Decimal = Decimal("0")
    total_eur: Decimal = field(init=False)

    def __post_init__(self) -> None:
        self.total_eur = self.cogs_eur + self.shipping_eur

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "cogs_eur": float(self.cogs_eur),
            "shipping_eur": float(self.shipping_eur),
            "total_eur": float(self.total_eur),
        }


class OrderCostService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def compute(
        self,
        *,
        order_id: str,
        cogs_per_unit_eur: Decimal,
        quantity: Optional[Decimal] = None,
        destination: Optional[str] = None,
        sku_category: Optional[str] = None,
    ) -> OrderCost:
        """Compute the all-in cost of an order.

        `quantity` comes from the caller (usually via OrderRevenue or the
        PO line). When missing we assume 1 unit so at least one data point
        flows through — Sprint T will populate the real quantity from the
        ERP sync.
        """
        qty = Decimal(str(quantity)) if quantity is not None else await self._quantity_for(order_id)
        cogs_total = Decimal(str(cogs_per_unit_eur)) * qty

        shipping = Decimal("0")
        if destination or sku_category:
            rate = await self._best_shipping_rate(destination, sku_category)
            if rate is not None:
                shipping = Decimal(str(rate.flat_cost_eur))

        return OrderCost(
            order_id=order_id,
            cogs_eur=cogs_total,
            shipping_eur=shipping,
        )

    # ─── internals ────────────────────────────────────────────────────────

    async def _quantity_for(self, order_id: str) -> Decimal:
        """Fetch the order's quantity from `OrderRevenue`; default to 1."""
        stmt = select(OrderRevenue.quantity).where(
            and_(
                OrderRevenue.tenant_id == self.tenant_id,
                OrderRevenue.order_id == order_id,
            )
        )
        value = (await self.session.execute(stmt)).scalar_one_or_none()
        if value is None:
            return Decimal("1")
        return Decimal(str(value))

    async def _best_shipping_rate(
        self,
        destination: Optional[str],
        sku_category: Optional[str],
    ) -> Optional[ShippingRate]:
        """Resolution order: exact match → destination/ANY → ANY/ANY.

        Returns None when the entire table is empty (tests do not need to
        seed shipping rates unless they care about shipping).
        """
        tried = [
            (destination or "ANY", sku_category or "ANY"),
            (destination or "ANY", "ANY"),
            ("ANY", "ANY"),
        ]
        for dest, cat in tried:
            stmt = select(ShippingRate).where(
                and_(
                    ShippingRate.tenant_id == self.tenant_id,
                    ShippingRate.destination == dest,
                    ShippingRate.sku_category == cat,
                    ShippingRate.active.is_(True),
                )
            ).limit(1)
            row = (await self.session.execute(stmt)).scalar_one_or_none()
            if row is not None:
                return row
        return None
