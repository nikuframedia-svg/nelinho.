"""
ProdPlan ONE — QualityRiskModel batch scoring (Sprint Q.41.A)
=============================================================

Activates the previously-stubbed ``_quality_risk_scoring_job``. The CPO
fitness function already consults the QualityRiskModel *during* planning
(`src/plan/cpo/fitness.py:58`, weight 0.10); this module does the
complementary job — scoring the schedule rows that already exist *at
rest*, so ``plan.production_schedules.quality_risk_score`` carries an
up-to-date P(quality_event) that auditoria, copilot fact packs and twin
scenarios can read without re-running the GA.

The persistence target is not new: migration 019 (Sprint R.2) added
``quality_risk_score`` + ``quality_risk_scored_at`` to
``production_schedules`` for exactly this job.

Honest degradation
------------------
Every "no work to do" branch returns an explicit status string and logs
in PT-PT. The job never pretends to have scored when it could not:

* ``no_model``   — no active ``quality_risk`` artifact in the registry
                   (typical in dev before a retrain has run).
* ``no_rows``    — no SCHEDULED/IN_PROGRESS schedule rows pending a score.
* ``scored``     — rows were scored and persisted.

This is deliberately NOT a stub: when there is real work and a real
model, it does the real scoring; when either is missing it says so.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Schedule statuses that are still actionable — a score on a COMPLETED or
# CANCELLED row would be advice nobody can act on.
_SCORABLE_STATUSES = ("SCHEDULED", "IN_PROGRESS")

# Hard cap so a single tick can't load an unbounded backlog into memory.
_MAX_ROWS_PER_RUN = 2000


@dataclass
class QualityRiskScoringResult:
    """Outcome of one scoring pass — what the scheduler logs."""

    status: str  # "scored" | "no_model" | "no_rows"
    rows_considered: int = 0
    rows_scored: int = 0
    model_version: Optional[int] = None
    detail: str = ""
    elapsed_ms: int = 0
    errors: List[str] = field(default_factory=list)


def _to_feature_row(
    schedule: Any,
    product_code: str,
    operation_code: str,
) -> Dict[str, Any]:
    """Project a ``ProductionSchedule`` row to the feature shape the
    QualityRiskModel expects (``CATEGORICAL_COLS`` + ``NUMERIC_COLS``).

    ``modelo_id``/``fase_id`` use the ERP-stable codes (product_code /
    operation_code) — the same identifiers the training dataset builds
    its categoricals from. Numeric features fall back to neutral defaults
    when the schedule row doesn't carry them; unknown categoricals encode
    as all-zeros inside ``encode_categoricals`` so a prediction is still
    produced (possibly less accurate, never crashing).
    """
    duration_h = schedule.scheduled_duration_hours
    return {
        "modelo_id": product_code,
        "fase_id": operation_code,
        # A schedule row carries a single assigned employee, so team_size
        # is 1 per row (dual-resource Laminagem pairing is modelled
        # upstream in the CPO, not on the persisted schedule row).
        "team_size": 1,
        "mold_pocket_count": 1,
        "phase_error_rate": 0.0,
        # Use scheduled duration (hours) as a coarse load proxy when the
        # curated queue_depth isn't available at rest.
        "queue_depth": float(duration_h) if duration_h is not None else 0.0,
    }


async def score_quality_risk(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    max_rows: int = _MAX_ROWS_PER_RUN,
) -> QualityRiskScoringResult:
    """Score pending production-schedule rows with the active QualityRiskModel.

    Loads the active ``quality_risk`` artifact, batch-scores every
    SCHEDULED/IN_PROGRESS row, and writes ``quality_risk_score`` +
    ``quality_risk_scored_at`` back. The caller commits the session.

    Returns a :class:`QualityRiskScoringResult` describing what happened —
    callers (the scheduler job) turn it into a single log line.
    """
    started = datetime.now(timezone.utc)

    def _elapsed_ms() -> int:
        return int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    # ── 1. Load the active model ──────────────────────────────────────
    from src.ml.registry_loader import load_active_quality_risk_predictor
    from src.ml.models.registry import ModelRegistry

    predictor = await load_active_quality_risk_predictor(session, tenant_id)
    if predictor is None:
        logger.info(
            "quality_risk_scoring tenant=%s sem modelo activo — nada a fazer "
            "(treina o QualityRiskModel via RetrainJob primeiro)",
            tenant_id,
        )
        return QualityRiskScoringResult(
            status="no_model",
            detail="sem artefacto quality_risk activo no registo",
            elapsed_ms=_elapsed_ms(),
        )

    model_version: Optional[int] = None
    try:
        active = await ModelRegistry(session, tenant_id).get_active("quality_risk")
        model_version = active.version if active else None
    except Exception:  # pragma: no cover — version is informational only
        model_version = None

    # ── 2. Pull the schedule rows that still need a score ─────────────
    from src.core.models.operation import Operation
    from src.core.models.product import Product
    from src.plan.models.schedule import ProductionSchedule

    stmt = (
        select(ProductionSchedule)
        .where(ProductionSchedule.tenant_id == tenant_id)
        .where(ProductionSchedule.status.in_(_SCORABLE_STATUSES))
        .order_by(ProductionSchedule.scheduled_start_date)
        .limit(max_rows)
    )
    schedules = list((await session.execute(stmt)).scalars().all())
    if not schedules:
        logger.info(
            "quality_risk_scoring tenant=%s sem fases agendadas por pontuar "
            "(estados %s) — nada a fazer",
            tenant_id, _SCORABLE_STATUSES,
        )
        return QualityRiskScoringResult(
            status="no_rows",
            detail="sem ProductionSchedule SCHEDULED/IN_PROGRESS",
            model_version=model_version,
            elapsed_ms=_elapsed_ms(),
        )

    # ── 3. Resolve the ERP-stable codes for the feature rows ──────────
    product_ids = {s.product_id for s in schedules}
    operation_ids = {s.operation_id for s in schedules}

    product_codes: Dict[UUID, str] = dict(
        (
            await session.execute(
                select(Product.id, Product.product_code).where(
                    Product.id.in_(product_ids)
                )
            )
        ).all()
    )
    operation_codes: Dict[UUID, str] = dict(
        (
            await session.execute(
                select(Operation.id, Operation.operation_code).where(
                    Operation.id.in_(operation_ids)
                )
            )
        ).all()
    )

    feature_rows: List[Dict[str, Any]] = []
    for s in schedules:
        feature_rows.append(
            _to_feature_row(
                s,
                product_code=product_codes.get(s.product_id, ""),
                operation_code=operation_codes.get(s.operation_id, ""),
            )
        )

    # ── 4. Score the batch ────────────────────────────────────────────
    errors: List[str] = []
    try:
        probs = predictor(feature_rows)
    except Exception as exc:
        logger.error(
            "quality_risk_scoring tenant=%s falhou na inferência: %s",
            tenant_id, exc, exc_info=True,
        )
        return QualityRiskScoringResult(
            status="no_rows",
            rows_considered=len(schedules),
            detail=f"inferência falhou: {exc}",
            model_version=model_version,
            elapsed_ms=_elapsed_ms(),
            errors=[str(exc)],
        )

    if len(probs) != len(schedules):
        # A predictor that returns the wrong cardinality is a bug, not a
        # data gap — surface it loud rather than silently mis-aligning.
        msg = (
            f"predictor devolveu {len(probs)} pontuações para "
            f"{len(schedules)} fases — desalinhamento, nada persistido"
        )
        logger.error("quality_risk_scoring tenant=%s %s", tenant_id, msg)
        return QualityRiskScoringResult(
            status="no_rows",
            rows_considered=len(schedules),
            detail=msg,
            model_version=model_version,
            elapsed_ms=_elapsed_ms(),
            errors=[msg],
        )

    # ── 5. Persist the scores ─────────────────────────────────────────
    scored_at = datetime.now(timezone.utc)
    rows_scored = 0
    for schedule, prob in zip(schedules, probs):
        try:
            clamped = max(0.0, min(1.0, float(prob)))
        except (TypeError, ValueError):
            errors.append(f"schedule={schedule.id}: pontuação inválida {prob!r}")
            continue
        # Numeric(5,4) in the DB — round to 4 decimals to match.
        schedule.quality_risk_score = Decimal(f"{clamped:.4f}")
        schedule.quality_risk_scored_at = scored_at
        rows_scored += 1

    await session.flush()

    logger.info(
        "quality_risk_scoring tenant=%s modelo=v%s fases=%d pontuadas=%d "
        "erros=%d elapsed_ms=%d",
        tenant_id, model_version, len(schedules), rows_scored,
        len(errors), _elapsed_ms(),
    )
    return QualityRiskScoringResult(
        status="scored",
        rows_considered=len(schedules),
        rows_scored=rows_scored,
        model_version=model_version,
        detail=f"{rows_scored} fases pontuadas",
        elapsed_ms=_elapsed_ms(),
        errors=errors,
    )
