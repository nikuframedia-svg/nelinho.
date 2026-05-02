"""Schedule fact pack for the Copilot (FASE 3.7 / HIGH-52).

When a user asks ``"qual é o plano para amanhã?"`` the copilot needs a
deterministic summary of the current schedule it can cite. Before this
module the copilot had no wiring to ``plan.production_schedules`` —
the auditoria PLANO (Decide) flagged it as a missing data source. This
package fills that gap with a pure-Python helper:

    fact_pack = await build_schedule_fact_pack(
        session, tenant_id, days_ahead=7,
    )

Returns a :class:`ScheduleFactPack` dataclass that's trivial to render
into the existing prompt's FACT PACK section. The helper is read-only
and respects tenant scoping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.schedule import ProductionSchedule, ScheduleStatus


@dataclass
class ScheduleFactPack:
    """Deterministic summary of the active schedule for a horizon.

    Designed to render cleanly inside the copilot's FACT PACK prompt
    section — every field is a primitive or a list of primitives.
    """

    tenant_id: str
    window_start: str  # ISO date
    window_end: str    # ISO date
    total_rows: int = 0
    rows_by_status: Dict[str, int] = field(default_factory=dict)
    distinct_orders: int = 0
    distinct_machines: int = 0
    next_7_days_by_day: List[Dict[str, Any]] = field(default_factory=list)
    flagged_infeasible: int = 0
    avg_quality_risk: Optional[float] = None
    latest_planning_run_id: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "total_rows": self.total_rows,
            "rows_by_status": self.rows_by_status,
            "distinct_orders": self.distinct_orders,
            "distinct_machines": self.distinct_machines,
            "next_7_days_by_day": self.next_7_days_by_day,
            "flagged_infeasible": self.flagged_infeasible,
            "avg_quality_risk": self.avg_quality_risk,
            "latest_planning_run_id": self.latest_planning_run_id,
            "notes": self.notes,
        }


async def build_schedule_fact_pack(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    days_ahead: int = 7,
    today: Optional[date] = None,
) -> ScheduleFactPack:
    """Build the schedule fact pack for the given tenant + window.

    Read-only. Filters every query by ``tenant_id`` so multi-tenant
    contamination (HIGH-50 in the auditoria) cannot leak through this
    code path. Defaults to a 7-day window starting at ``today``.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    horizon_end = today + timedelta(days=days_ahead)

    fact = ScheduleFactPack(
        tenant_id=str(tenant_id),
        window_start=today.isoformat(),
        window_end=horizon_end.isoformat(),
    )

    base = and_(
        ProductionSchedule.tenant_id == tenant_id,
        ProductionSchedule.scheduled_start_date >= today,
        ProductionSchedule.scheduled_start_date <= horizon_end,
    )

    # 1. total rows + distinct orders + machines
    totals_stmt = select(
        func.count(ProductionSchedule.id),
        func.count(func.distinct(ProductionSchedule.order_id)),
        func.count(func.distinct(ProductionSchedule.machine_id)),
    ).where(base)
    total, n_orders, n_machines = (await session.execute(totals_stmt)).one()
    fact.total_rows = int(total or 0)
    fact.distinct_orders = int(n_orders or 0)
    fact.distinct_machines = int(n_machines or 0)

    if fact.total_rows == 0:
        fact.notes.append(
            "Nenhum ProductionSchedule planeado para o horizonte. "
            "Corre /v1/plan/cpo/schedule antes de perguntar pelo plano."
        )
        return fact

    # 2. rows_by_status — useful to see if the plan is mostly SCHEDULED,
    #    IN_PROGRESS or already COMPLETED.
    status_stmt = (
        select(ProductionSchedule.status, func.count(ProductionSchedule.id))
        .where(base)
        .group_by(ProductionSchedule.status)
    )
    fact.rows_by_status = {
        (s.value if hasattr(s, "value") else str(s)): int(c)
        for s, c in (await session.execute(status_stmt)).all()
    }

    # 3. flagged infeasible (FASE 1B.4 / CRIT-23 added this column).
    infeasible_stmt = select(func.count(ProductionSchedule.id)).where(
        and_(base, ProductionSchedule.infeasible_reason.isnot(None))
    )
    fact.flagged_infeasible = int(
        (await session.execute(infeasible_stmt)).scalar() or 0
    )

    # 4. avg_quality_risk over rows that have a score.
    risk_stmt = select(func.avg(ProductionSchedule.quality_risk_score)).where(
        and_(base, ProductionSchedule.quality_risk_score.isnot(None))
    )
    avg_risk = (await session.execute(risk_stmt)).scalar()
    if avg_risk is not None:
        fact.avg_quality_risk = round(float(avg_risk), 4)

    # 5. day-by-day breakdown (orders + ops counts) so the model can
    #    answer "amanhã" / "quarta-feira" style queries deterministically.
    by_day_stmt = (
        select(
            ProductionSchedule.scheduled_start_date,
            func.count(ProductionSchedule.id).label("ops"),
            func.count(func.distinct(ProductionSchedule.order_id)).label("orders"),
        )
        .where(base)
        .group_by(ProductionSchedule.scheduled_start_date)
        .order_by(ProductionSchedule.scheduled_start_date)
    )
    fact.next_7_days_by_day = [
        {
            "date": d.isoformat() if d else None,
            "ops": int(ops),
            "orders": int(orders),
        }
        for d, ops, orders in (await session.execute(by_day_stmt)).all()
    ]

    # 6. latest planning_run_id (most recent created_at within window).
    latest_stmt = (
        select(ProductionSchedule.planning_run_id)
        .where(base)
        .where(ProductionSchedule.planning_run_id.isnot(None))
        .order_by(ProductionSchedule.created_at.desc())
        .limit(1)
    )
    latest_run = (await session.execute(latest_stmt)).scalar_one_or_none()
    fact.latest_planning_run_id = latest_run

    # 7. soft warnings — surfaced in the prompt so the model can hedge.
    if fact.flagged_infeasible > 0:
        fact.notes.append(
            f"{fact.flagged_infeasible} operações marcadas infeasible "
            "pelo decoder — ver `infeasible_reason` em ProductionSchedule."
        )
    if ScheduleStatus.IN_PROGRESS.value not in fact.rows_by_status:
        fact.notes.append(
            "Nenhuma operação IN_PROGRESS na janela — confirma se há "
            "atrasos no kickoff do plano actual."
        )

    return fact
