"""
ProdPlan ONE - Margin Calculator (Sprint Q.3 / CS03)
=====================================================

Combines revenue (from `OrderRevenue` with fallback to `ProductPricing`)
and cost (`OrderCostService`) into a single `OrderMargin` report. Also
exposes pure helpers tests can drive without DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.pricing import OrderRevenue, ProductPricing


@dataclass
class OrderMargin:
    order_id: str
    revenue_eur: Decimal
    cogs_eur: Decimal
    shipping_eur: Decimal
    margin_eur: Decimal = field(init=False)
    margin_pct: Optional[float] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.margin_eur = self.revenue_eur - self.cogs_eur - self.shipping_eur
        if self.revenue_eur > 0:
            self.margin_pct = float(self.margin_eur / self.revenue_eur)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "revenue_eur": float(self.revenue_eur),
            "cogs_eur": float(self.cogs_eur),
            "shipping_eur": float(self.shipping_eur),
            "margin_eur": float(self.margin_eur),
            "margin_pct": (
                round(self.margin_pct, 4) if self.margin_pct is not None else None
            ),
        }


class MarginCalculator:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def compute(
        self,
        *,
        order_id: str,
        cogs_eur: Decimal,
        shipping_eur: Decimal = Decimal("0"),
        product_id: Optional[UUID] = None,
    ) -> OrderMargin:
        """Resolve revenue (OrderRevenue → ProductPricing fallback), then
        subtract COGS + shipping.

        `cogs_eur` and `shipping_eur` are caller-provided because the two
        calculators that produce them (COGSCalculator, OrderCostService)
        have different caching needs. Passing them in keeps
        `MarginCalculator` focused on revenue resolution.
        """
        revenue = await self.resolve_revenue(order_id=order_id, product_id=product_id)
        return OrderMargin(
            order_id=order_id,
            revenue_eur=Decimal(str(revenue)),
            cogs_eur=Decimal(str(cogs_eur)),
            shipping_eur=Decimal(str(shipping_eur)),
        )

    async def resolve_revenue(
        self,
        *,
        order_id: str,
        product_id: Optional[UUID] = None,
    ) -> Decimal:
        """Revenue resolution:
        1. `OrderRevenue.total_revenue_eur` for this order_id
        2. Current `ProductPricing.sale_value_default_eur` for `product_id`
        3. `0` — cannot guess (no margin_default fallback here; callers
           that want the Sprint L cost.margin_default shim invoke it themselves)
        """
        stmt = select(OrderRevenue).where(
            and_(
                OrderRevenue.tenant_id == self.tenant_id,
                OrderRevenue.order_id == order_id,
            )
        )
        revenue_row = (await self.session.execute(stmt)).scalar_one_or_none()
        if revenue_row is not None:
            return Decimal(str(revenue_row.total_revenue_eur))

        if product_id is None:
            return Decimal("0")

        stmt = (
            select(ProductPricing.sale_value_default_eur)
            .where(
                and_(
                    ProductPricing.tenant_id == self.tenant_id,
                    ProductPricing.product_id == product_id,
                    ProductPricing.active.is_(True),
                )
            )
            .order_by(ProductPricing.valid_from.desc())
            .limit(1)
        )
        price = (await self.session.execute(stmt)).scalar_one_or_none()
        if price is None:
            return Decimal("0")
        return Decimal(str(price))


# ---------------------------------------------------------------------------
# Pure helpers (no DB) — used by Sprint Q tests + the greedy pipeline hook
# ---------------------------------------------------------------------------

def compute_throughput_eur_day(
    orders_completed: list[dict[str, Any]],
    *,
    revenue_by_order: dict[str, Decimal],
    days: int = 1,
) -> Decimal:
    """Sum recognised revenue over N days.

    `orders_completed` is a list of `{order_id, completed_at, …}` dicts;
    `revenue_by_order` is pre-resolved so this fn stays a pure divider.
    """
    if days <= 0:
        return Decimal("0")
    total = Decimal("0")
    for order in orders_completed:
        order_id = str(order.get("order_id") or "")
        rev = revenue_by_order.get(order_id, Decimal("0"))
        total += Decimal(str(rev))
    return total / Decimal(str(days))
