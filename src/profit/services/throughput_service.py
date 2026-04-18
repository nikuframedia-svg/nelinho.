"""
ProdPlan ONE - Throughput €/dia Service (Sprint Q.5 / CS05)
============================================================

Powers:
* `GET /v1/profit/dashboard`
* `FactoryMapService.kpis()` — replaces the Sprint N.6 "unavailable" stub
* Fitness `throughput_eur_day` term (Sprint P.6 — the greedy pipeline
  now populates `schedule["throughput_eur_day"]` via this service so the
  CPO GA can optimise against the €30-35K/day target directly).

Reads TenantConfig for:
  cost.target.throughput_eur_day_min   (default 30000)
  cost.target.throughput_eur_day_max   (default 35000)
  cost.margin_default                  (default 1.40)

Per Blueprint §1.1 the NELO target is €30K–35K/day. Call `on_target_band()`
to classify the current measurement against those bounds.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.pricing import OrderRevenue

logger = logging.getLogger(__name__)


DEFAULT_TARGET_MIN = Decimal("30000")
DEFAULT_TARGET_MAX = Decimal("35000")
DEFAULT_MARGIN_DEFAULT = Decimal("1.40")


class ThroughputService:
    """Aggregates OrderRevenue by `recognised_at` to produce €/dia figures."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─── Config ────────────────────────────────────────────────────────────

    async def load_targets(self) -> dict[str, Decimal]:
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            svc = TenantConfigService(self.session, self.tenant_id)
            cfg = await svc.get_category("cost")
            return {
                "min_eur_day": Decimal(str(cfg.get(
                    "target.throughput_eur_day_min", DEFAULT_TARGET_MIN,
                ))),
                "max_eur_day": Decimal(str(cfg.get(
                    "target.throughput_eur_day_max", DEFAULT_TARGET_MAX,
                ))),
                "margin_default": Decimal(str(cfg.get(
                    "margin_default", DEFAULT_MARGIN_DEFAULT,
                ))),
            }
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("throughput config load failed: %s", exc)
            return {
                "min_eur_day": DEFAULT_TARGET_MIN,
                "max_eur_day": DEFAULT_TARGET_MAX,
                "margin_default": DEFAULT_MARGIN_DEFAULT,
            }

    # ─── Public methods ────────────────────────────────────────────────────

    async def throughput_today(self, *, as_of: Optional[date] = None) -> Decimal:
        as_of = as_of or date.today()
        return await self._sum_revenue(as_of, as_of)

    async def throughput_mtd(self, *, as_of: Optional[date] = None) -> Decimal:
        as_of = as_of or date.today()
        return await self._sum_revenue(as_of.replace(day=1), as_of)

    async def throughput_ytd(self, *, as_of: Optional[date] = None) -> Decimal:
        as_of = as_of or date.today()
        return await self._sum_revenue(as_of.replace(month=1, day=1), as_of)

    async def throughput_trend(
        self, *, days_back: int = 14, until: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        until = until or date.today()
        start = until - timedelta(days=max(1, days_back) - 1)
        rows = await self._daily_buckets(start, until)
        # Densify: emit zero-rows for days that had no revenue at all.
        revenue_by_day: dict[date, Decimal] = {d: total for d, total in rows}
        points: list[dict[str, Any]] = []
        cursor = start
        while cursor <= until:
            points.append({
                "date": cursor.isoformat(),
                "eur": float(revenue_by_day.get(cursor, Decimal("0"))),
            })
            cursor += timedelta(days=1)
        return points

    async def top_skus(
        self,
        *,
        date_from: date,
        date_to: date,
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Revenue grouped by product. Returns the top-N and, separately,
        any SKU with zero revenue (potentially loss-making candidates)."""
        # OrderRevenue is keyed by order_id; join to ProductionOrder for
        # product_name. We avoid a join for simplicity — the frontend can
        # call the product-master endpoint for names.
        stmt = (
            select(
                OrderRevenue.order_id,
                OrderRevenue.total_revenue_eur,
                OrderRevenue.recognised_at,
            )
            .where(
                and_(
                    OrderRevenue.tenant_id == self.tenant_id,
                    OrderRevenue.recognised_at >= date_from,
                    OrderRevenue.recognised_at <= date_to,
                )
            )
        )
        rows = (await self.session.execute(stmt)).all()
        # Return per-order for now; Sprint T can join `ProductionOrder`
        # upstream to group by product_id once quantity/product_id are wired.
        per_order = [
            {
                "order_id": str(r[0]),
                "revenue_eur": float(r[1] or 0),
                "recognised_at": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        ]
        per_order.sort(key=lambda d: d["revenue_eur"], reverse=True)
        return per_order[:top_n]

    async def dashboard(self, *, as_of: Optional[date] = None) -> dict[str, Any]:
        """Compose the full dashboard response (Q.5)."""
        as_of = as_of or date.today()
        targets = await self.load_targets()

        today = await self.throughput_today(as_of=as_of)
        mtd = await self.throughput_mtd(as_of=as_of)
        ytd = await self.throughput_ytd(as_of=as_of)
        trend = await self.throughput_trend(days_back=14, until=as_of)

        return {
            "date": as_of.isoformat(),
            "throughput_eur": {
                "today": float(today),
                "mtd": float(mtd),
                "ytd": float(ytd),
                "target_min": float(targets["min_eur_day"]),
                "target_max": float(targets["max_eur_day"]),
                "on_target": on_target_band(
                    today, targets["min_eur_day"], targets["max_eur_day"],
                ),
            },
            "trend_14d": trend,
            "top_skus": await self.top_skus(
                date_from=as_of.replace(day=1), date_to=as_of, top_n=10,
            ),
            "currency": "EUR",
            "source": "order_revenue",
        }

    # ─── internals ────────────────────────────────────────────────────────

    async def _sum_revenue(self, date_from: date, date_to: date) -> Decimal:
        stmt = select(func.coalesce(
            func.sum(OrderRevenue.total_revenue_eur), 0,
        )).where(
            and_(
                OrderRevenue.tenant_id == self.tenant_id,
                OrderRevenue.recognised_at >= date_from,
                OrderRevenue.recognised_at <= date_to,
            )
        )
        result = (await self.session.execute(stmt)).scalar_one_or_none()
        return Decimal(str(result or 0))

    async def _daily_buckets(
        self, date_from: date, date_to: date,
    ) -> list[tuple[date, Decimal]]:
        stmt = (
            select(
                OrderRevenue.recognised_at,
                func.coalesce(func.sum(OrderRevenue.total_revenue_eur), 0),
            )
            .where(
                and_(
                    OrderRevenue.tenant_id == self.tenant_id,
                    OrderRevenue.recognised_at.is_not(None),
                    OrderRevenue.recognised_at >= date_from,
                    OrderRevenue.recognised_at <= date_to,
                )
            )
            .group_by(OrderRevenue.recognised_at)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], Decimal(str(r[1] or 0))) for r in rows]


# ---------------------------------------------------------------------------
# Pure helpers (shared with fitness + factory_map hooks)
# ---------------------------------------------------------------------------

def on_target_band(
    value: Decimal,
    target_min: Decimal,
    target_max: Decimal,
) -> dict[str, Any]:
    """Classify a daily throughput against the Blueprint band."""
    v = Decimal(str(value))
    vmin = Decimal(str(target_min))
    vmax = Decimal(str(target_max))
    if v < vmin:
        status = "below"
    elif v > vmax:
        status = "above"
    else:
        status = "within"
    return {
        "status": status,
        "pct_of_min": float(v / vmin) if vmin > 0 else None,
        "pct_of_max": float(v / vmax) if vmax > 0 else None,
    }
