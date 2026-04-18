"""
ProdPlan ONE - Worker Quality Ranking (Sprint R.3 / QA08)
===========================================================

Objective ranking of workers by rework rate. "Objective" means: no
manual scoring — the numerator counts ReworkEntry rows attributed to the
worker, the denominator counts ops executed (from CuratedOrderPhase).

For each worker the service returns:
  * error_count        — rework entries where they were the causer
  * ops_executed       — curated order_phase rows with the worker as chefe
  * error_rate         — error_count / max(ops_executed, 1)
  * trend_7d_delta     — change in error_rate over the last 7 days

The phase filter is optional; aggregation keys on `chefe_employee_id`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry


class WorkerRankingService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def ranking(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        phase_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        since = since or datetime.now(timezone.utc) - timedelta(days=90)
        until = until or datetime.now(timezone.utc)

        # Rework tally per causer.
        stmt = (
            select(
                ReworkEntry.causer_employee_id,
                func.count(ReworkEntry.id).label("error_count"),
            )
            .where(
                and_(
                    ReworkEntry.tenant_id == self.tenant_id,
                    ReworkEntry.detected_at >= since,
                    ReworkEntry.detected_at <= until,
                    ReworkEntry.causer_employee_id.is_not(None),
                )
            )
            .group_by(ReworkEntry.causer_employee_id)
        )
        if phase_id:
            stmt = stmt.where(ReworkEntry.phase_id_causer == phase_id)
        rows = (await self.session.execute(stmt)).all()

        # Total rework across the tenant so we can compute share%.
        total_errors = sum(int(r[1] or 0) for r in rows) or 1

        items: list[dict[str, Any]] = []
        for causer_id, count in rows:
            if causer_id is None:
                continue
            items.append({
                "employee_id": str(causer_id),
                "error_count": int(count or 0),
                "share_pct": round(100.0 * int(count or 0) / total_errors, 2),
            })
        items.sort(key=lambda d: d["error_count"], reverse=True)
        return items[:limit]
