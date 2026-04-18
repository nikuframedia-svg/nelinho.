"""
ProdPlan ONE - Quality Dashboard (Sprint R.4 / QA05)
======================================================

Aggregates rework events by operator / phase / SKU / shift. Each grouping
is a separate method so callers can stitch exactly the dimensions they
need — no forced OLAP-style unions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry

VALID_GROUP_BY = frozenset({"operator", "phase", "sku", "shift"})


class QualityDashboardService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def group_by(
        self,
        *,
        group_by: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        top_n: int = 25,
    ) -> dict[str, Any]:
        if group_by not in VALID_GROUP_BY:
            raise ValueError(
                f"Unsupported group_by '{group_by}'. "
                f"Allowed: {sorted(VALID_GROUP_BY)}"
            )

        since = since or datetime.now(timezone.utc) - timedelta(days=30)
        until = until or datetime.now(timezone.utc)

        base = select(
            func.count(ReworkEntry.id).label("events"),
        ).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.detected_at >= since,
                ReworkEntry.detected_at <= until,
            )
        )

        group_col = self._group_column(group_by)
        stmt = base.add_columns(group_col).where(group_col.is_not(None)).group_by(group_col)

        rows = (await self.session.execute(stmt)).all()
        total = sum(int(r[0] or 0) for r in rows) or 1

        items: list[dict[str, Any]] = []
        for row in rows:
            events = int(row[0] or 0)
            value = str(row[1])
            items.append({
                "key": value,
                "events": events,
                "share_pct": round(100.0 * events / total, 2),
            })
        items.sort(key=lambda d: d["events"], reverse=True)

        return {
            "group_by": group_by,
            "window": {"from": since.isoformat(), "to": until.isoformat()},
            "total_events": sum(i["events"] for i in items),
            "items": items[:top_n],
        }

    def _group_column(self, group_by: str):
        if group_by == "operator":
            return ReworkEntry.causer_employee_id
        if group_by == "phase":
            return ReworkEntry.phase_id_causer
        if group_by == "sku":
            return ReworkEntry.model_id
        if group_by == "shift":
            # Shift is derived from detected_at hour band; SQL-side expression.
            return func.to_char(ReworkEntry.detected_at, "HH24")
        raise ValueError(group_by)
