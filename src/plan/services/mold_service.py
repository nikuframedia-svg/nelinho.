"""
ProdPlan ONE - Mold Service (Sprint R.6.3 / R.6.4 / R.6.5)
============================================================

CRUD + orchestration for Mold/MoldHealth/MoldMaintenanceEvent/MoldDefectLog/
MoldUsageCounter. Used by:

* APScheduler job `_mold_health_scan_job` (daily) — recomputes health for
  every active mold.
* APScheduler job `_mold_preventive_schedule_job` (weekly) — proposes a
  PLANNED maintenance event for molds whose health dropped below the red
  threshold or whose cycle counter exceeds the config threshold.
* Scheduler hook — `increment_cycle()` called from op completion events
  (to be wired in Sprint T when ERP integration lands).
* REST API — `src/plan/api/mold.py`.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.alerts.models import (
    CopilotAlert,
    STATUS_ACTIVE,
)
from src.plan.models.mold import (
    Mold,
    MoldDefectLog,
    MoldHealth,
    MoldMaintenanceEvent,
    MoldUsageCounter,
)
from src.plan.services.mold_health_calculator import MoldHealthCalculator

logger = logging.getLogger(__name__)


CODE_MOLD_MAINT_DUE = "MOLD_MAINT_DUE"
DEFAULT_MAINT_THRESHOLD_CYCLES = 500


class MoldNotFoundError(Exception):
    pass


class MoldService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._calc = MoldHealthCalculator(session, tenant_id)

    # ─── Master CRUD ──────────────────────────────────────────────────────

    async def create_mold(
        self,
        *,
        mold_code: str,
        model_id: str,
        pocket_count: int = 1,
        expected_life_cycles: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Mold:
        existing = await self._find_by_code(mold_code)
        if existing is not None:
            raise ValueError(f"Mold {mold_code} already exists for this tenant")
        mold = Mold(
            id=uuid4(),
            tenant_id=self.tenant_id,
            mold_code=mold_code,
            model_id=model_id,
            name=name,
            pocket_count=pocket_count,
            expected_life_cycles=expected_life_cycles,
            active=True,
            depreciated=False,
        )
        self.session.add(mold)
        # Seed the usage counter so future increments don't race.
        counter = MoldUsageCounter(
            id=uuid4(),
            tenant_id=self.tenant_id,
            mold_id=mold.id,
            shot_count_total=0,
            cycles_since_last_maint=0,
            last_updated_at=datetime.now(timezone.utc),
        )
        self.session.add(counter)
        await self.session.flush()
        return mold

    async def list_molds(self, *, active_only: bool = True) -> list[Mold]:
        stmt = select(Mold).where(Mold.tenant_id == self.tenant_id)
        if active_only:
            stmt = stmt.where(Mold.active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_mold(self, mold_id: UUID) -> Mold:
        stmt = select(Mold).where(
            and_(Mold.tenant_id == self.tenant_id, Mold.id == mold_id),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise MoldNotFoundError(str(mold_id))
        return row

    async def _find_by_code(self, mold_code: str) -> Optional[Mold]:
        stmt = select(Mold).where(
            and_(
                Mold.tenant_id == self.tenant_id,
                Mold.mold_code == mold_code,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ─── Health ───────────────────────────────────────────────────────────

    async def recompute_health(self, mold: Mold) -> MoldHealth:
        result = await self._calc.compute(mold)
        row = MoldHealth(
            id=uuid4(),
            tenant_id=self.tenant_id,
            mold_id=mold.id,
            score_0_100=result.score_0_100,
            risk_category=result.risk_category,
            assessed_at=datetime.now(timezone.utc),
            components=result.components.as_dict(),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def latest_health(self, mold_id: UUID) -> Optional[MoldHealth]:
        stmt = (
            select(MoldHealth)
            .where(
                and_(
                    MoldHealth.tenant_id == self.tenant_id,
                    MoldHealth.mold_id == mold_id,
                )
            )
            .order_by(MoldHealth.assessed_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ─── Maintenance events ───────────────────────────────────────────────

    async def plan_maintenance(
        self,
        *,
        mold_id: UUID,
        planned_date: date,
        maintenance_type: str = "preventive",
        technician_id: Optional[UUID] = None,
        comments: Optional[str] = None,
    ) -> MoldMaintenanceEvent:
        event = MoldMaintenanceEvent(
            id=uuid4(),
            tenant_id=self.tenant_id,
            mold_id=mold_id,
            maintenance_type=maintenance_type,
            planned_date=planned_date,
            technician_id=technician_id,
            comments=comments,
            status="PLANNED",
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def start_maintenance(self, event_id: UUID) -> MoldMaintenanceEvent:
        event = await self._get_event(event_id)
        event.status = "IN_PROGRESS"
        event.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        return event

    async def complete_maintenance(
        self,
        *,
        event_id: UUID,
        actual_duration_h: Optional[Decimal] = None,
        parts_cost_eur: Optional[Decimal] = None,
        labor_cost_eur: Optional[Decimal] = None,
        defects_fixed: Optional[list] = None,
    ) -> MoldMaintenanceEvent:
        event = await self._get_event(event_id)
        event.status = "COMPLETED"
        event.completed_at = datetime.now(timezone.utc)
        event.actual_duration_h = actual_duration_h
        event.parts_cost_eur = parts_cost_eur
        event.labor_cost_eur = labor_cost_eur
        event.defects_fixed = defects_fixed or []

        # Reset the cycle counter.
        stmt = select(MoldUsageCounter).where(
            and_(
                MoldUsageCounter.tenant_id == self.tenant_id,
                MoldUsageCounter.mold_id == event.mold_id,
            )
        )
        counter = (await self.session.execute(stmt)).scalar_one_or_none()
        if counter is not None:
            counter.cycles_since_last_maint = 0
            counter.last_reset_at = datetime.now(timezone.utc)
            counter.last_updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return event

    async def calendar(
        self, *, since: date, until: date,
    ) -> list[MoldMaintenanceEvent]:
        stmt = (
            select(MoldMaintenanceEvent)
            .where(
                and_(
                    MoldMaintenanceEvent.tenant_id == self.tenant_id,
                    MoldMaintenanceEvent.planned_date >= since,
                    MoldMaintenanceEvent.planned_date <= until,
                )
            )
            .order_by(MoldMaintenanceEvent.planned_date)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _get_event(self, event_id: UUID) -> MoldMaintenanceEvent:
        stmt = select(MoldMaintenanceEvent).where(
            and_(
                MoldMaintenanceEvent.tenant_id == self.tenant_id,
                MoldMaintenanceEvent.id == event_id,
            )
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"MoldMaintenanceEvent {event_id} not found")
        return row

    # ─── Usage counter ────────────────────────────────────────────────────

    async def increment_cycle(self, *, mold_id: UUID, amount: int = 1) -> MoldUsageCounter:
        stmt = select(MoldUsageCounter).where(
            and_(
                MoldUsageCounter.tenant_id == self.tenant_id,
                MoldUsageCounter.mold_id == mold_id,
            )
        )
        counter = (await self.session.execute(stmt)).scalar_one_or_none()
        if counter is None:
            counter = MoldUsageCounter(
                id=uuid4(),
                tenant_id=self.tenant_id,
                mold_id=mold_id,
                shot_count_total=amount,
                cycles_since_last_maint=amount,
                last_updated_at=datetime.now(timezone.utc),
            )
            self.session.add(counter)
        else:
            counter.shot_count_total += amount
            counter.cycles_since_last_maint += amount
            counter.last_updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return counter

    # ─── Alerts (AL08 / CG12) ─────────────────────────────────────────────

    async def emit_maintenance_alerts(self) -> int:
        """Scan all active molds and emit MOLD_MAINT_DUE alerts when the
        cycle counter exceeds `mold.maintenance_threshold_cycles`.

        Returns the number of alerts created.
        """
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            cfg = TenantConfigService(self.session, self.tenant_id)
            threshold = int(await cfg.get(
                "mold", "maintenance_threshold_cycles",
                default=DEFAULT_MAINT_THRESHOLD_CYCLES,
            ))
        except Exception:
            threshold = DEFAULT_MAINT_THRESHOLD_CYCLES

        stmt = (
            select(Mold, MoldUsageCounter)
            .join(
                MoldUsageCounter,
                and_(
                    MoldUsageCounter.tenant_id == self.tenant_id,
                    MoldUsageCounter.mold_id == Mold.id,
                ),
                isouter=True,
            )
            .where(
                and_(
                    Mold.tenant_id == self.tenant_id,
                    Mold.active.is_(True),
                )
            )
        )
        rows = (await self.session.execute(stmt)).all()
        created = 0
        for mold, counter in rows:
            if counter is None:
                continue
            if counter.cycles_since_last_maint <= threshold:
                continue
            if await self._alert_exists_for_mold(mold.id):
                continue
            alert = CopilotAlert(
                id=uuid4(),
                tenant_id=self.tenant_id,
                severity="CRITICAL" if counter.cycles_since_last_maint > threshold * 1.5 else "WARN",
                code=CODE_MOLD_MAINT_DUE,
                title=f"Manutenção de molde: {mold.mold_code}",
                message_pt=(
                    f"Molde {mold.mold_code} atingiu {counter.cycles_since_last_maint} ciclos "
                    f"desde a última manutenção (limite {threshold})."
                ),
                context={
                    "mold_id": str(mold.id),
                    "mold_code": mold.mold_code,
                    "cycles_since_last_maint": counter.cycles_since_last_maint,
                    "threshold": threshold,
                },
                entity_refs=[f"mold:{mold.mold_code}"],
                status=STATUS_ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(alert)
            created += 1
        await self.session.flush()
        return created

    async def _alert_exists_for_mold(self, mold_id: UUID) -> bool:
        stmt = select(CopilotAlert.id).where(
            and_(
                CopilotAlert.tenant_id == self.tenant_id,
                CopilotAlert.code == CODE_MOLD_MAINT_DUE,
                CopilotAlert.status == STATUS_ACTIVE,
                CopilotAlert.entity_refs.contains([f"mold:{mold_id}"]),
            )
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    # ─── Preventive planner (R.6.5) ───────────────────────────────────────

    async def propose_preventive_schedule(
        self,
        *,
        horizon_days: int = 14,
    ) -> list[MoldMaintenanceEvent]:
        """Walk red-flagged molds; create a PLANNED maintenance event when
        no future event already exists within the horizon."""
        molds = await self.list_molds()
        created: list[MoldMaintenanceEvent] = []
        today = date.today()
        horizon = today + timedelta(days=horizon_days)
        for mold in molds:
            health = await self.latest_health(mold.id)
            if health is None or health.risk_category != "red":
                continue
            # Skip if there's already a future planned event.
            stmt = (
                select(MoldMaintenanceEvent.id)
                .where(
                    and_(
                        MoldMaintenanceEvent.tenant_id == self.tenant_id,
                        MoldMaintenanceEvent.mold_id == mold.id,
                        MoldMaintenanceEvent.planned_date >= today,
                        MoldMaintenanceEvent.planned_date <= horizon,
                        MoldMaintenanceEvent.status.in_(["PLANNED", "IN_PROGRESS"]),
                    )
                )
                .limit(1)
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if existing:
                continue
            event = await self.plan_maintenance(
                mold_id=mold.id,
                planned_date=today + timedelta(days=3),
                maintenance_type="preventive",
                comments=f"Auto-proposed (health={health.score_0_100}, {health.risk_category})",
            )
            created.append(event)
        return created
