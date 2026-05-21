"""
ProdPlan ONE — Plan adherence (Q.53.B)
========================================

The Qualidade page has an "Aderência" tab that was degrading because
`/v1/plan/adherence` did not exist. This service computes **plan vs
realised by phase**:

* **plan** — the operations of the latest `ScheduleCommit` (the CPO's
  committed plan), grouped by `phase_id`. Each op carries a planned
  start/end so we know how many ops were scheduled per phase.
* **realised** — the same ops as they actually ran. `ProductionSchedule`
  rows carry `actual_start`/`actual_end`; we match them to the committed
  ops by `operation_id` and count completions.
* **defect rate** — per phase, from `quality.rework_entry`: the share of
  ops in the phase that triggered a rework event. This is the same
  signal `FactoryState.historical_error_rates` feeds the GA.

`adherence_pct` per phase = realised_ops / planned_ops (capped at 1.0).
The endpoint is read-only — no schedule mutation.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class PlanAdherenceService:
    """Compute plan-vs-realised adherence by phase."""

    def __init__(self, session, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def compute(self) -> Dict[str, Any]:
        """Return the adherence report (per-phase + summary).

        Best-effort: a missing commit / empty schedule returns an
        explicit empty report — never a 500, never a silent mock.
        """
        from sqlalchemy import select

        from src.plan.cpo.commits import ScheduleCommit
        from src.plan.models.schedule import ProductionSchedule
        from src.quality.models.rework import ReworkEntry

        # 1) Latest committed plan.
        stmt = (
            select(ScheduleCommit)
            .where(ScheduleCommit.tenant_id == self.tenant_id)
            .order_by(ScheduleCommit.created_at.desc())
            .limit(1)
        )
        commit = (await self.session.execute(stmt)).scalar_one_or_none()

        planned_by_phase: Dict[str, int] = defaultdict(int)
        planned_op_ids: Dict[str, set] = defaultdict(set)
        if commit is not None:
            for op in commit.operations or []:
                phase = _phase_key(op.get("phase_id"))
                planned_by_phase[phase] += 1
                op_id = op.get("operation_id")
                if op_id:
                    planned_op_ids[phase].add(str(op_id))

        # 2) Realised ops — ProductionSchedule rows that actually ran.
        stmt = select(ProductionSchedule).where(
            ProductionSchedule.tenant_id == self.tenant_id,
        )
        sched_rows = (await self.session.execute(stmt)).scalars().all()
        realised_op_ids = {
            str(r.operation_id)
            for r in sched_rows
            if r.actual_start is not None or r.actual_end is not None
        }

        # 3) Defect rate per phase — rework_entry rows by causer phase.
        stmt = select(ReworkEntry).where(
            ReworkEntry.tenant_id == self.tenant_id,
        )
        rework_rows = (await self.session.execute(stmt)).scalars().all()
        rework_by_phase: Dict[str, int] = defaultdict(int)
        for rw in rework_rows:
            phase = _phase_key(rw.phase_id_causer)
            rework_by_phase[phase] += 1

        # 4) Assemble per-phase rows.
        all_phases = (
            set(planned_by_phase)
            | set(rework_by_phase)
        )
        phases: List[Dict[str, Any]] = []
        total_planned = 0
        total_realised = 0
        for phase in sorted(all_phases):
            planned = planned_by_phase.get(phase, 0)
            realised = len(planned_op_ids.get(phase, set()) & realised_op_ids)
            defects = rework_by_phase.get(phase, 0)
            total_planned += planned
            total_realised += realised
            adherence = (
                min(1.0, realised / planned) if planned > 0 else None
            )
            # Defect rate denominator: planned ops in the phase (the work
            # that ran). When there is no committed plan for the phase but
            # there are rework rows, we still surface the absolute count.
            defect_rate = (
                min(1.0, defects / planned) if planned > 0 else None
            )
            phases.append({
                "phase_id": phase,
                "planned_ops": planned,
                "realised_ops": realised,
                "adherence_pct": (
                    round(adherence * 100.0, 1) if adherence is not None else None
                ),
                "defect_count": defects,
                "defect_rate_pct": (
                    round(defect_rate * 100.0, 1) if defect_rate is not None else None
                ),
            })

        summary_adherence = (
            round(min(1.0, total_realised / total_planned) * 100.0, 1)
            if total_planned > 0 else None
        )
        return {
            "has_committed_plan": commit is not None,
            "commit_sha": (
                commit.commit_sha256[:12] if commit is not None else None
            ),
            "commit_created_at": (
                commit.created_at.isoformat()
                if commit is not None and commit.created_at else None
            ),
            "summary": {
                "total_planned_ops": total_planned,
                "total_realised_ops": total_realised,
                "adherence_pct": summary_adherence,
                "n_phases": len(phases),
            },
            "phases": phases,
        }


def _phase_key(value: Optional[Any]) -> str:
    """Normalise a phase identifier to a non-empty string key."""
    s = str(value or "").strip()
    return s or "(sem fase)"
