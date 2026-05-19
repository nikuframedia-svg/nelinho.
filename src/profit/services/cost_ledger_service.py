"""
ProdPlan ONE - Cost Ledger Service (Sprint Q.53.C)
===================================================

Powers `GET /v1/profit/cost-ledger`, the consolidation layer behind the
future "Custos" page. Today cost lives across ~16 endpoints
(`cogs/calculate`, `oee`, `dashboard`, `sku-profitability`,
`orders/{id}/margin`, rates…); this service folds the persisted
`CostCalculation` rows into one ledger view:

* **cost_by_center** — the six COGS components (material, labor, machine,
  setup, overhead, scrap) summed across all calculated orders. Each
  component is a "cost center" line.
* **per_boat** — COGS detail per work order (the boat), with margin when
  `OrderRevenue` exists.
* **margin_by_product** — COGS / revenue / margin grouped by product type
  (K1, K2, K4…).
* **cost_drivers** — the cost-center lines ranked by € share, so the
  Custos page can show "where the money goes".

Everything is built from data already in Postgres (`profit.cost_calculations`
+ `profit.order_revenue` + `plan.production_orders`). Orders without a
`CostCalculation` are reported as `uncalculated` — never imputed.

CoeficienteX is DINHEIRO but is NOT a COGS component; it is intentionally
absent from this ledger.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.order import ProductionOrder
from src.profit.models.cost import CostCalculation
from src.profit.models.pricing import OrderRevenue

logger = logging.getLogger(__name__)

# The six COGS components, in report order. These ARE the cost centres.
_COST_COMPONENTS = (
    "material",
    "labor",
    "machine",
    "setup",
    "overhead",
    "scrap",
)


@dataclass
class _Bucket:
    """Mutable accumulator for a product-type margin bucket."""

    order_count: int = 0
    cogs_eur: Decimal = field(default_factory=lambda: Decimal("0"))
    revenue_eur: Decimal = field(default_factory=lambda: Decimal("0"))
    revenue_orders: int = 0


class CostLedgerService:
    """Consolidates persisted COGS into a cost-center / per-product ledger."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def ledger(
        self,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 2000,
    ) -> dict[str, Any]:
        """Build the full cost-ledger response."""
        orders = await self._load_orders(date_from, date_to, limit)
        if not orders:
            return _empty_ledger(date_from, date_to)

        keys = [str(o.legacy_id) for o in orders]
        cost_by_order = await self._load_costs(keys)
        rev_by_order = await self._load_revenue(keys)

        per_boat = [
            self._boat_row(o, cost_by_order, rev_by_order) for o in orders
        ]

        cost_by_center = self._cost_by_center(cost_by_order)
        margin_by_product = self._margin_by_product(
            orders, cost_by_order, rev_by_order
        )
        cost_drivers = self._cost_drivers(cost_by_center)

        total_cogs = sum(
            (Decimal(str(c.total_cogs)) for c in cost_by_order.values()),
            Decimal("0"),
        )
        calculated = sum(1 for r in per_boat if r["calculated"])

        return {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "summary": {
                "orders_total": len(orders),
                "orders_calculated": calculated,
                "orders_uncalculated": len(orders) - calculated,
                "total_cogs_eur": _money(total_cogs),
            },
            "cost_by_center": cost_by_center,
            "cost_drivers": cost_drivers,
            "margin_by_product": margin_by_product,
            "per_boat": per_boat,
            "currency": "EUR",
            "source": "profit.cost_calculations",
        }

    # ─── loaders ───────────────────────────────────────────────────────────

    async def _load_orders(
        self,
        date_from: Optional[date],
        date_to: Optional[date],
        limit: int,
    ) -> list[ProductionOrder]:
        stmt = select(ProductionOrder).where(
            ProductionOrder.tenant_id == self.tenant_id
        )
        if date_from is not None:
            stmt = stmt.where(ProductionOrder.created_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(ProductionOrder.created_date <= date_to)
        stmt = stmt.order_by(
            ProductionOrder.created_date.desc().nullslast()
        ).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def _load_costs(
        self, keys: list[str]
    ) -> dict[str, CostCalculation]:
        """Latest `CostCalculation` per order_id (highest version wins)."""
        by_order: dict[str, CostCalculation] = {}
        stmt = (
            select(CostCalculation)
            .where(
                and_(
                    CostCalculation.tenant_id == self.tenant_id,
                    CostCalculation.order_id.in_(keys),
                )
            )
            .order_by(CostCalculation.calculation_version)
        )
        for cc in (await self.session.execute(stmt)).scalars().all():
            by_order[cc.order_id] = cc
        return by_order

    async def _load_revenue(self, keys: list[str]) -> dict[str, Decimal]:
        by_order: dict[str, Decimal] = {}
        stmt = select(OrderRevenue).where(
            and_(
                OrderRevenue.tenant_id == self.tenant_id,
                OrderRevenue.order_id.in_(keys),
            )
        )
        for rv in (await self.session.execute(stmt)).scalars().all():
            by_order[rv.order_id] = Decimal(str(rv.total_revenue_eur))
        return by_order

    # ─── builders (pure) ──────────────────────────────────────────────────

    def _boat_row(
        self,
        order: ProductionOrder,
        cost_by_order: dict[str, CostCalculation],
        rev_by_order: dict[str, Decimal],
    ) -> dict[str, Any]:
        """COGS detail for one boat. No CostCalculation → calculated=False."""
        key = str(order.legacy_id)
        cc = cost_by_order.get(key)
        revenue = rev_by_order.get(key)
        row: dict[str, Any] = {
            "order_id": key,
            "hull": key,
            "product_name": order.product_name,
            "product_type": order.product_type,
            "calculated": cc is not None,
            "cogs_breakdown": None,
            "total_cogs_eur": None,
            "revenue_eur": _money(revenue) if revenue is not None else None,
            "margin_eur": None,
            "margin_pct": None,
        }
        if cc is None:
            return row
        breakdown = {
            comp: _money(getattr(cc, f"{comp}_cost"))
            for comp in _COST_COMPONENTS
        }
        total = Decimal(str(cc.total_cogs))
        row["cogs_breakdown"] = breakdown
        row["total_cogs_eur"] = _money(total)
        if revenue is not None:
            margin = revenue - total
            row["margin_eur"] = _money(margin)
            if revenue > 0:
                row["margin_pct"] = float(
                    (margin / revenue).quantize(Decimal("0.0001"))
                )
        return row

    def _cost_by_center(
        self, cost_by_order: dict[str, CostCalculation]
    ) -> list[dict[str, Any]]:
        """Sum each COGS component across all calculated orders."""
        totals = {comp: Decimal("0") for comp in _COST_COMPONENTS}
        for cc in cost_by_order.values():
            for comp in _COST_COMPONENTS:
                totals[comp] += Decimal(str(getattr(cc, f"{comp}_cost")))
        grand = sum(totals.values(), Decimal("0"))
        return [
            {
                "cost_center": comp,
                "total_eur": _money(totals[comp]),
                "share_pct": (
                    float((totals[comp] / grand).quantize(Decimal("0.0001")))
                    if grand > 0
                    else None
                ),
            }
            for comp in _COST_COMPONENTS
        ]

    def _margin_by_product(
        self,
        orders: list[ProductionOrder],
        cost_by_order: dict[str, CostCalculation],
        rev_by_order: dict[str, Decimal],
    ) -> list[dict[str, Any]]:
        """Group COGS / revenue / margin by product type (K1, K2…)."""
        buckets: dict[str, _Bucket] = {}
        for o in orders:
            key = str(o.legacy_id)
            cc = cost_by_order.get(key)
            if cc is None:
                continue
            ptype = o.product_type or "Outro"
            b = buckets.setdefault(ptype, _Bucket())
            b.order_count += 1
            b.cogs_eur += Decimal(str(cc.total_cogs))
            revenue = rev_by_order.get(key)
            if revenue is not None:
                b.revenue_eur += revenue
                b.revenue_orders += 1

        rows: list[dict[str, Any]] = []
        for ptype, b in buckets.items():
            margin = b.revenue_eur - b.cogs_eur
            has_revenue = b.revenue_orders > 0
            rows.append(
                {
                    "product_type": ptype,
                    "order_count": b.order_count,
                    "orders_with_revenue": b.revenue_orders,
                    "total_cogs_eur": _money(b.cogs_eur),
                    "total_revenue_eur": (
                        _money(b.revenue_eur) if has_revenue else None
                    ),
                    "margin_eur": _money(margin) if has_revenue else None,
                    "margin_pct": (
                        float((margin / b.revenue_eur).quantize(Decimal("0.0001")))
                        if has_revenue and b.revenue_eur > 0
                        else None
                    ),
                }
            )
        rows.sort(key=lambda r: r["total_cogs_eur"], reverse=True)
        return rows

    @staticmethod
    def _cost_drivers(
        cost_by_center: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Rank the cost-center lines by € spend — biggest drivers first."""
        ranked = sorted(
            (c for c in cost_by_center if c["total_eur"] > 0),
            key=lambda c: c["total_eur"],
            reverse=True,
        )
        return [
            {
                "rank": i + 1,
                "cost_center": c["cost_center"],
                "total_eur": c["total_eur"],
                "share_pct": c["share_pct"],
            }
            for i, c in enumerate(ranked)
        ]


def _money(value: Any) -> float:
    """Decimal/None-safe euro rounding to cents."""
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _empty_ledger(
    date_from: Optional[date], date_to: Optional[date]
) -> dict[str, Any]:
    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "summary": {
            "orders_total": 0,
            "orders_calculated": 0,
            "orders_uncalculated": 0,
            "total_cogs_eur": 0.0,
        },
        "cost_by_center": [],
        "cost_drivers": [],
        "margin_by_product": [],
        "per_boat": [],
        "currency": "EUR",
        "source": "profit.cost_calculations",
    }
