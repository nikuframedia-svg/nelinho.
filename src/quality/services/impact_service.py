"""
ProdPlan ONE - Quality Impact Analysis (Sprint R.7 / QA03)
===========================================================

Rolls up rework events per error_code (or per order) into a single
impact report: total events, cumulative cost, hours lost, affected
orders, and a share of total tenant rework.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry


async def most_frequent_error_code(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Optional[str]:
    """The `error_code` with the most rework events in the window.

    Used as the honest default for the diagnostic endpoints (root-cause,
    impact) when the caller does not pick one — the tab opens on whatever
    defect is actually hurting the factory most, never on a guessed code.
    Returns ``None`` when there is no rework at all.
    """
    since = since or datetime.now(timezone.utc) - timedelta(days=90)
    until = until or datetime.now(timezone.utc)
    stmt = (
        select(ReworkEntry.error_code, func.count(ReworkEntry.id).label("n"))
        .where(
            and_(
                ReworkEntry.tenant_id == tenant_id,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )
        .group_by(ReworkEntry.error_code)
        .order_by(func.count(ReworkEntry.id).desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


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
