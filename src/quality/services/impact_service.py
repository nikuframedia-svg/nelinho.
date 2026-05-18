"""
ProdPlan ONE - Quality Impact Analysis (Sprint R.7 / QA03 · Q.37.A)
=====================================================================

Rolls up rework events per error_code (or per order) into a single
impact report: total events, cumulative cost, hours lost, affected
orders, and a share of total tenant rework.

Q.37.A adds `cost_summary` — the factory-wide €-cost rollup (not tied to
one error_code) that answers the CEO question "quanto custou o retrabalho".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry

# Q.37.A — dimensions the factory-wide cost rollup can break down by.
VALID_COST_GROUP_BY = frozenset({"error_code", "phase", "model", "of_id"})


class ImpactService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def impact_by_error(
        self,
        *,
        error_code: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> dict[str, Any]:
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        stmt = select(
            func.count(ReworkEntry.id),
            func.coalesce(func.sum(ReworkEntry.cost_estimate_eur), 0),
            func.coalesce(func.sum(ReworkEntry.hours_lost), 0),
            func.count(func.distinct(ReworkEntry.of_id)),
        ).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.error_code == error_code,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )
        row = (await self.session.execute(stmt)).one()
        events = int(row[0] or 0)
        total_cost = Decimal(str(row[1] or 0))
        total_hours = Decimal(str(row[2] or 0))
        affected_orders = int(row[3] or 0)

        # Share of total rework across tenant in the same window.
        total_stmt = select(func.count(ReworkEntry.id)).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )
        total_all = int((await self.session.execute(total_stmt)).scalar_one_or_none() or 0) or 1
        share_pct = round(100.0 * events / total_all, 2)

        return {
            "error_code": error_code,
            "window": {"from": since.isoformat(), "to": until.isoformat()},
            "events": events,
            "affected_orders": affected_orders,
            "cost_estimate_eur": float(total_cost),
            "hours_lost": float(total_hours),
            "share_pct_of_total_rework": share_pct,
        }

    async def cost_summary(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        group_by: Optional[str] = None,
        top_n: int = 20,
    ) -> dict[str, Any]:
        """Factory-wide rework cost rollup (Q.37.A).

        Unlike `impact_by_error` (a single error_code), this answers
        "quanto custou o retrabalho" across all rework in the window —
        total €, hours lost, affected orders, plus an optional breakdown.

        `cost_coverage_pct` is the honesty signal: how much of the rework
        actually has a € estimate recorded. Quality events imported from
        the curated layer often leave `cost_estimate_eur` NULL, so a low
        coverage means the headline € is an under-count, not a fact.
        """
        if group_by is not None and group_by not in VALID_COST_GROUP_BY:
            raise ValueError(
                f"Unsupported group_by '{group_by}'. "
                f"Allowed: {sorted(VALID_COST_GROUP_BY)}"
            )

        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        window = and_(
            ReworkEntry.tenant_id == self.tenant_id,
            ReworkEntry.detected_at >= since,
            ReworkEntry.detected_at <= until,
        )

        agg_stmt = select(
            func.count(ReworkEntry.id),
            func.count(ReworkEntry.cost_estimate_eur),
            func.coalesce(func.sum(ReworkEntry.cost_estimate_eur), 0),
            func.coalesce(func.sum(ReworkEntry.hours_lost), 0),
            func.count(func.distinct(ReworkEntry.of_id)),
        ).where(window)
        agg_rows = (await self.session.execute(agg_stmt)).all()
        agg = agg_rows[0] if agg_rows else (0, 0, 0, 0, 0)

        events = int(agg[0] or 0)
        events_with_cost = int(agg[1] or 0)
        total_cost = Decimal(str(agg[2] or 0))
        total_hours = Decimal(str(agg[3] or 0))
        affected_orders = int(agg[4] or 0)
        coverage = round(100.0 * events_with_cost / events, 2) if events else 0.0

        breakdown: list[dict[str, Any]] = []
        if group_by is not None:
            col = self._cost_group_column(group_by)
            br_stmt = (
                select(
                    col,
                    func.count(ReworkEntry.id),
                    func.coalesce(func.sum(ReworkEntry.cost_estimate_eur), 0),
                    func.coalesce(func.sum(ReworkEntry.hours_lost), 0),
                )
                .where(window)
                .where(col.is_not(None))
                .group_by(col)
            )
            br_rows = (await self.session.execute(br_stmt)).all()
            for r in br_rows:
                breakdown.append({
                    "key": str(r[0]),
                    "events": int(r[1] or 0),
                    "cost_estimate_eur": float(Decimal(str(r[2] or 0))),
                    "hours_lost": float(Decimal(str(r[3] or 0))),
                })
            breakdown.sort(key=lambda d: d["cost_estimate_eur"], reverse=True)
            breakdown = breakdown[: max(1, top_n)]

        return {
            "window": {"from": since.isoformat(), "to": until.isoformat()},
            "events": events,
            "events_with_cost_estimate": events_with_cost,
            "cost_coverage_pct": coverage,
            "cost_estimate_eur": float(total_cost),
            "hours_lost": float(total_hours),
            "affected_orders": affected_orders,
            "group_by": group_by,
            "breakdown": breakdown,
        }

    def _cost_group_column(self, group_by: str):
        if group_by == "error_code":
            return ReworkEntry.error_code
        if group_by == "phase":
            return ReworkEntry.phase_id_causer
        if group_by == "model":
            return ReworkEntry.model_id
        if group_by == "of_id":
            return ReworkEntry.of_id
        raise ValueError(group_by)
