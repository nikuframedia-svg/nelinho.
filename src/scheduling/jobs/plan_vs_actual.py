"""Q.115.V — Job plan-vs-actual diário + modelos Pydantic do report.

Compara planos CPO aprovados (status=LIVE) com execução real em
`plan.fases_of_history`. Calcula deltas por (modelo, fase) e persiste
em `plan.plan_execution_observed` (migration existente via Q.113).

Schedule: 06:30 UTC (após drift detection 06:00).
Apenas lê ScheduleCommit — nunca escreve.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic response schemas (importados pelo endpoint e pelos testes)
# ---------------------------------------------------------------------------


class DeltaByPhase(BaseModel):
    phase_id: str
    phase_name: str
    avg_delta_duration_min: float
    avg_delta_quality: Optional[float]  # null se sem defeitos
    sample_n: int


class DeltaByModel(BaseModel):
    modelo_id: str
    avg_delta_duration_min: float
    avg_delta_quality: Optional[float]
    sample_n: int


class PlanVsActualReport(BaseModel):
    tenant_id: UUID
    days: int
    # 100 × (1 - mean(|delta_duration| / planned_duration))
    plan_accuracy_pct: float
    deltas_by_phase: List[DeltaByPhase]
    deltas_by_model: List[DeltaByModel]
    sample_size: int
    computed_at: datetime


# ---------------------------------------------------------------------------
# Core computation — pura, sem I/O, testável
# ---------------------------------------------------------------------------


def _compute_report(
    tenant_id: UUID,
    days: int,
    rows: List[Dict[str, Any]],
) -> PlanVsActualReport:
    """Calcula PlanVsActualReport a partir de rows já lidas.

    Cada row tem:
      phase_id, phase_name, modelo_id,
      planned_duration_min, observed_duration_min  (observed pode ser None),
      deviation_pct (pode ser None)

    Rows com observed_duration_min=None são ignoradas nos deltas de duração.
    """
    # Filtra linhas com dados completos de duração
    valid = [
        r for r in rows
        if r.get("planned_duration_min") is not None
        and r.get("observed_duration_min") is not None
        and float(r["planned_duration_min"]) > 0
    ]

    if not valid:
        return PlanVsActualReport(
            tenant_id=tenant_id,
            days=days,
            plan_accuracy_pct=0.0,
            deltas_by_phase=[],
            deltas_by_model=[],
            sample_size=0,
            computed_at=datetime.now(timezone.utc),
        )

    # Agrega por fase
    by_phase: Dict[str, Dict[str, Any]] = {}
    by_model: Dict[str, Dict[str, Any]] = {}

    abs_errors: List[float] = []

    for r in valid:
        planned = float(r["planned_duration_min"])
        observed = float(r["observed_duration_min"])
        delta_dur = observed - planned  # positivo = mais lento, negativo = mais rápido
        rel_err = abs(delta_dur) / planned
        abs_errors.append(rel_err)

        phase_id = str(r.get("phase_id", ""))
        phase_name = str(r.get("phase_name", phase_id))
        modelo_id = str(r.get("modelo_id", ""))

        # --- Por fase ---
        if phase_id not in by_phase:
            by_phase[phase_id] = {
                "phase_name": phase_name,
                "deltas": [],
                "quality_deltas": [],
            }
        by_phase[phase_id]["deltas"].append(delta_dur)
        dq = r.get("delta_quality")
        if dq is not None:
            by_phase[phase_id]["quality_deltas"].append(float(dq))

        # --- Por modelo ---
        if modelo_id not in by_model:
            by_model[modelo_id] = {"deltas": [], "quality_deltas": []}
        by_model[modelo_id]["deltas"].append(delta_dur)
        if dq is not None:
            by_model[modelo_id]["quality_deltas"].append(float(dq))

    # Accurácia global
    mean_rel_err = sum(abs_errors) / len(abs_errors)
    accuracy = max(0.0, min(100.0, 100.0 * (1.0 - mean_rel_err)))

    deltas_by_phase = [
        DeltaByPhase(
            phase_id=pid,
            phase_name=agg["phase_name"],
            avg_delta_duration_min=sum(agg["deltas"]) / len(agg["deltas"]),
            avg_delta_quality=(
                sum(agg["quality_deltas"]) / len(agg["quality_deltas"])
                if agg["quality_deltas"]
                else None
            ),
            sample_n=len(agg["deltas"]),
        )
        for pid, agg in by_phase.items()
    ]

    deltas_by_model = [
        DeltaByModel(
            modelo_id=mid,
            avg_delta_duration_min=sum(agg["deltas"]) / len(agg["deltas"]),
            avg_delta_quality=(
                sum(agg["quality_deltas"]) / len(agg["quality_deltas"])
                if agg["quality_deltas"]
                else None
            ),
            sample_n=len(agg["deltas"]),
        )
        for mid, agg in by_model.items()
    ]

    return PlanVsActualReport(
        tenant_id=tenant_id,
        days=days,
        plan_accuracy_pct=round(accuracy, 2),
        deltas_by_phase=deltas_by_phase,
        deltas_by_model=deltas_by_model,
        sample_size=len(valid),
        computed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Job APScheduler — 06:30 UTC
# ---------------------------------------------------------------------------


async def _plan_vs_actual_job(tenant_id: UUID, days: int = 7) -> PlanVsActualReport:
    """
    Job diário plan-vs-actual:
    1. Lê plan.plan_execution_observed para o tenant nos últimos `days` dias
    2. Calcula deltas por (fase, modelo)
    3. Faz log de audit (info-level)
    4. Devolve PlanVsActualReport (não persiste o report — é calculado on-demand)

    Não modifica ScheduleCommit. Não retreina modelos.
    """
    from sqlalchemy import select, text

    from src.plan.models.execution_learning import PlanExecutionObserved
    from src.shared.database import get_session_context

    started = datetime.now(timezone.utc)
    since = started - timedelta(days=days)

    try:
        async with get_session_context() as session:
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
                    "phase_name": str(o.phase_id),  # sem join — phase_name = phase_id
                    "modelo_id": str(o.modelo or ""),
                    "planned_duration_min": o.planned_duration_min,
                    "observed_duration_min": o.observed_duration_min,
                    "delta_quality": None,  # sem defeitos nesta tabela
                }
                for o in obs_rows
            ]

        report = _compute_report(tenant_id, days, rows)

        elapsed_ms = int(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )
        logger.info(
            "plan_vs_actual_job tenant=%s days=%d rows_lidas=%d "
            "sample_size=%d accuracy_pct=%.1f elapsed_ms=%d",
            tenant_id, days, len(rows),
            report.sample_size, report.plan_accuracy_pct, elapsed_ms,
        )
        return report

    except Exception as exc:
        logger.error(
            "plan_vs_actual_job tenant=%s falhou: %s", tenant_id, exc, exc_info=True
        )
        return PlanVsActualReport(
            tenant_id=tenant_id,
            days=days,
            plan_accuracy_pct=0.0,
            deltas_by_phase=[],
            deltas_by_model=[],
            sample_size=0,
            computed_at=datetime.now(timezone.utc),
        )


async def _plan_vs_actual_global_job(tenants: List[UUID], days: int = 7) -> None:
    """Wrapper global: itera todos os tenants e chama _plan_vs_actual_job.

    Registado no scheduler core a 06:30 UTC. Falha de um tenant não bloqueia
    os restantes (best-effort).
    """
    for tid in tenants:
        try:
            await _plan_vs_actual_job(tid, days=days)
        except Exception as exc:  # pragma: no cover — coberto pelo inner try
            logger.error(
                "plan_vs_actual_global_job tenant=%s falhou: %s", tid, exc,
                exc_info=True,
            )
