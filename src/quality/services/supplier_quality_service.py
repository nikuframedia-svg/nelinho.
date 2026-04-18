"""
ProdPlan ONE - Supplier Quality Analytics (Sprint R.8 / QA04 / MR03)
=====================================================================

Aggregates `ReworkEntry` grouped by `supplier_id` (or `material_lot_id`)
so planners can see which suppliers carry the largest share of quality
incidents. Complements Sprint O's ROP-based shortage detector.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry


class SupplierQualityService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def by_supplier(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        stmt = (
            select(
                ReworkEntry.supplier_id,
                func.count(ReworkEntry.id).label("events"),
                func.coalesce(func.sum(ReworkEntry.cost_estimate_eur), 0).label("cost"),
            )
            .where(
                and_(
                    ReworkEntry.tenant_id == self.tenant_id,
                    ReworkEntry.supplier_id.is_not(None),
                    ReworkEntry.detected_at >= since,
                    ReworkEntry.detected_at <= until,
                )
            )
            .group_by(ReworkEntry.supplier_id)
        )
        rows = (await self.session.execute(stmt)).all()
        items = [
            {
                "supplier_id": str(supplier_id),
                "events": int(events or 0),
                "cost_estimate_eur": float(cost or 0),
            }
            for supplier_id, events, cost in rows
        ]
        items.sort(key=lambda d: d["events"], reverse=True)
        return items[:top_n]

    async def by_lot(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        stmt = (
            select(
                ReworkEntry.material_lot_id,
                func.count(ReworkEntry.id).label("events"),
            )
            .where(
                and_(
                    ReworkEntry.tenant_id == self.tenant_id,
                    ReworkEntry.material_lot_id.is_not(None),
                    ReworkEntry.detected_at >= since,
                    ReworkEntry.detected_at <= until,
                )
            )
            .group_by(ReworkEntry.material_lot_id)
        )
        rows = (await self.session.execute(stmt)).all()
        items = [
            {
                "material_lot_id": str(lot_id),
                "events": int(events or 0),
            }
            for lot_id, events in rows
        ]
        items.sort(key=lambda d: d["events"], reverse=True)
        return items[:top_n]
