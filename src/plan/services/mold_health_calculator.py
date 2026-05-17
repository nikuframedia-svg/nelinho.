"""
ProdPlan ONE - Mold Health Calculator (Sprint R.6.2)
=====================================================

Weighted score (0-100, higher = healthier) combining 4 signals:

  cycles_since_last_maint / expected_life_cycles   (w_cycles)
  defect_count_90d × severity                     (w_defects_90d)
  days_since_last_maint / 90                      (w_days_since_maint)
  rework_rate (linked ReworkEntry rate)           (w_rework_rate)

Weights + thresholds come from TenantConfig (mold.*). The `components`
dict is persisted on `MoldHealth.components` for observability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.mold import (
    Mold,
    MoldDefectLog,
    MoldMaintenanceEvent,
    MoldUsageCounter,
)
from src.quality.models.rework import ReworkEntry

logger = logging.getLogger(__name__)


DEFAULT_WEIGHTS = {
    "cycles": 0.40,
    "defects_90d": 0.20,
    "days_since_maint": 0.20,
    "rework_rate": 0.20,
}
DEFAULT_THRESHOLDS = {
    "red": 40,
    "yellow": 70,
}


@dataclass
class HealthComponents:
    cycles_pct: float = 0.0
    defect_penalty: float = 0.0
    maint_age_pct: float = 0.0
    rework_rate: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "cycles_pct": round(self.cycles_pct, 4),
            "defect_penalty": round(self.defect_penalty, 4),
            "maint_age_pct": round(self.maint_age_pct, 4),
            "rework_rate": round(self.rework_rate, 4),
        }


@dataclass
class HealthResult:
    mold_id: UUID
    score_0_100: int
    risk_category: str
    components: HealthComponents

    def to_dict(self) -> dict[str, Any]:
        return {
            "mold_id": str(self.mold_id),
            "score_0_100": self.score_0_100,
            "risk_category": self.risk_category,
            "components": self.components.as_dict(),
        }


class MoldHealthCalculator:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def load_config(self) -> dict[str, Any]:
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            cfg = TenantConfigService(self.session, self.tenant_id)
            values = await cfg.get_category("mold")
            weights = {
                k: float(values.get(f"health_weight.{k}", DEFAULT_WEIGHTS[k]))
                for k in DEFAULT_WEIGHTS
            }
            thresholds = {
                "red": int(values.get("health.red_threshold", DEFAULT_THRESHOLDS["red"])),
                "yellow": int(values.get("health.yellow_threshold", DEFAULT_THRESHOLDS["yellow"])),
            }
            return {"weights": weights, "thresholds": thresholds}
        except Exception:  # pragma: no cover — defensive
            return {"weights": dict(DEFAULT_WEIGHTS), "thresholds": dict(DEFAULT_THRESHOLDS)}

    async def compute(self, mold: Mold) -> HealthResult:
        cfg = await self.load_config()
        weights = cfg["weights"]
        thresholds = cfg["thresholds"]

        components = HealthComponents(
            cycles_pct=await self._cycles_pct(mold),
            defect_penalty=await self._defect_penalty(mold),
            maint_age_pct=await self._maint_age_pct(mold),
            rework_rate=await self._rework_rate(mold),
        )

        # Score: 100 - weighted sum of penalties.
        penalty = (
            components.cycles_pct * weights["cycles"]
            + components.defect_penalty * weights["defects_90d"]
            + components.maint_age_pct * weights["days_since_maint"]
            + components.rework_rate * weights["rework_rate"]
        )
        raw = 100.0 - penalty * 100.0
        score = max(0, min(100, round(raw)))

        risk = _risk_from_score(score, thresholds)
        return HealthResult(
            mold_id=mold.id,
            score_0_100=score,
            risk_category=risk,
            components=components,
        )

    # ─── signals ──────────────────────────────────────────────────────────

    async def _cycles_pct(self, mold: Mold) -> float:
        """cycles_since_last_maint / max(expected_life_cycles, 1)."""
        stmt = select(MoldUsageCounter).where(
            and_(
                MoldUsageCounter.tenant_id == self.tenant_id,
                MoldUsageCounter.mold_id == mold.id,
            )
        )
        counter = (await self.session.execute(stmt)).scalar_one_or_none()
        if counter is None:
            return 0.0
        expected = max(1, int(mold.expected_life_cycles or 1))
        return max(0.0, min(1.0, int(counter.cycles_since_last_maint) / expected))

    async def _defect_penalty(self, mold: Mold) -> float:
        since = datetime.now(timezone.utc) - timedelta(days=90)
        stmt = select(MoldDefectLog).where(
            and_(
                MoldDefectLog.tenant_id == self.tenant_id,
                MoldDefectLog.mold_id == mold.id,
                MoldDefectLog.detected_at >= since,
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        if not rows:
            return 0.0
        severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.6}
        total = sum(severity_weights.get(row.severity, 0.3) for row in rows)
        # 10 medium defects in 90d → total 3.0 → cap at 1.0.
        return max(0.0, min(1.0, total / 3.0))

    async def _maint_age_pct(self, mold: Mold) -> float:
        stmt = (
            select(func.max(MoldMaintenanceEvent.completed_at))
            .where(
                and_(
                    MoldMaintenanceEvent.tenant_id == self.tenant_id,
                    MoldMaintenanceEvent.mold_id == mold.id,
                    MoldMaintenanceEvent.status == "COMPLETED",
                )
            )
        )
        last_maint = (await self.session.execute(stmt)).scalar_one_or_none()
        if last_maint is None:
            # Never maintained — penalty at 50% rather than 100% (new moulds
            # shouldn't auto-flag red the moment they arrive).
            return 0.5
        if last_maint.tzinfo is None:
            last_maint = last_maint.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - last_maint).days
        return max(0.0, min(1.0, days / 90.0))

    async def _rework_rate(self, mold: Mold) -> float:
        since = datetime.now(timezone.utc) - timedelta(days=90)
        stmt = (
            select(func.count(ReworkEntry.id))
            .where(
                and_(
                    ReworkEntry.tenant_id == self.tenant_id,
                    ReworkEntry.mold_id == mold.mold_code,
                    ReworkEntry.detected_at >= since,
                )
            )
        )
        count = int((await self.session.execute(stmt)).scalar_one_or_none() or 0)
        # 10 rework events in 90d → rate 1.0.
        return max(0.0, min(1.0, count / 10.0))


def _risk_from_score(score: int, thresholds: dict[str, int]) -> str:
    if score < int(thresholds.get("red", 40)):
        return "red"
    if score < int(thresholds.get("yellow", 70)):
        return "yellow"
    return "green"
