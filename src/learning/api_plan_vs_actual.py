"""Q.115.V — GET /v1/learning/plan-vs-actual?days=N

Endpoint read-only. Calcula deltas plano/real a partir de
`plan.plan_execution_observed`. Devolve PlanVsActualReport.
Empty/sample_size=0 quando não há dados (FasesOf vazia em dev).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.execution_learning import PlanExecutionObserved
from src.scheduling.jobs.plan_vs_actual import PlanVsActualReport, _compute_report
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/learning", tags=["Aprendizagem"])

_tenant_id = require_tenant_header


@router.get(
    "/plan-vs-actual",
    response_model=PlanVsActualReport,
    summary="Deltas plano vs real nos últimos N dias",
)
async def get_plan_vs_actual(
    days: int = Query(default=7, ge=1, le=90, description="Janela em dias"),
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PlanVsActualReport:
    """Calcula plan_accuracy_pct e deltas por fase/modelo.

    Devolve sample_size=0 + listas vazias quando não há dados
    (SQLSERVER_ENABLED=false em dev → fases_of_history vazia).
    """
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = select(PlanExecutionObserved).where(
        PlanExecutionObserved.tenant_id == tenant_id,
        PlanExecutionObserved.captured_at >= since,
        PlanExecutionObserved.observed_duration_min.isnot(None),
    )
    result = await session.execute(stmt)
    obs_rows = result.scalars().all()

    rows: List[Dict[str, Any]] = [
        {
            "phase_id": str(o.phase_id),
            "phase_name": str(o.phase_id),
            "modelo_id": str(o.modelo or ""),
            "planned_duration_min": o.planned_duration_min,
            "observed_duration_min": o.observed_duration_min,
            "delta_quality": None,
        }
        for o in obs_rows
    ]

    return _compute_report(tenant_id, days, rows)
