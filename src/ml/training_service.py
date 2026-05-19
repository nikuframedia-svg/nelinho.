"""
ProdPlan ONE — ML Training Service (Q.53.A)
=============================================

`RetrainJob` (src/ml/jobs/base.py) is the cron-driven retrain lifecycle and
it still works — but it reads its features from the in-memory curated layer,
which is empty in the deployed factory. This service is the **DB-backed**
entry point: it builds the training rows straight from the durable tables
(`factory_curated.order_phase` + `quality.rework_entry`), fits the model,
registers the artifact and promotes it to ACTIVE so the registry stops
returning ``None``.

It is invoked two ways:
  * one-shot, from `scripts/train_ml_models.py`, to seed the registry;
  * on demand, from `GET /v1/quality/defect-risk` when no model is active
    yet (so the Qualidade page is never blocked on an empty registry).

Promotion here is direct (``decision_id=None``) because seeding the very
first model has no prior baseline to govern against. Subsequent retrains go
through the governed `RetrainJob` path with a `DecisionRun`.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.models.registry import ModelRegistry
from src.ml.models_domain.duration import DurationModel
from src.ml.models_domain.quality_risk import QualityRiskModel
from src.ml.models_domain.training_data import (
    build_duration_dataset,
    build_quality_risk_dataset,
)

logger = logging.getLogger(__name__)


class TrainingError(RuntimeError):
    """Raised when a model could not be trained from the available data."""


async def train_quality_risk(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    trained_by: str = "training_service",
    promote: bool = True,
) -> Dict[str, Any]:
    """Train `QualityRiskModel` from the DB and register the artifact.

    Returns a summary dict; raises `TrainingError` when the data layer has
    too few rows to fit a non-degenerate classifier.
    """
    started = time.time()
    rows = await build_quality_risk_dataset(session, tenant_id)
    if not rows:
        raise TrainingError(
            "quality_risk: no training rows — factory_curated.order_phase or "
            "quality.rework_entry is empty. Run the ERP sync first."
        )

    model = QualityRiskModel()
    try:
        metrics = model.train(rows)
    except ValueError as exc:
        raise TrainingError(f"quality_risk: {exc}") from exc

    registry = ModelRegistry(session, tenant_id)
    artifact = await registry.save(
        model_name="quality_risk",
        model=model,
        metrics=metrics,
        trained_by=trained_by,
        training_duration_sec=round(time.time() - started, 3),
        training_samples=int(metrics.get("samples", len(rows))),
    )
    promoted = False
    if promote:
        await registry.promote(artifact.id, decision_id=None, promoted_by=trained_by)
        promoted = True

    logger.info(
        "train_quality_risk: v%s registered (auc=%s, samples=%s, promoted=%s)",
        artifact.version, metrics.get("auc"), metrics.get("samples"), promoted,
    )
    return {
        "model_name": "quality_risk",
        "version": artifact.version,
        "artifact_id": str(artifact.id),
        "metrics": metrics,
        "promoted": promoted,
    }


async def train_duration(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    trained_by: str = "training_service",
    promote: bool = True,
) -> Dict[str, Any]:
    """Train `DurationModel` from the DB and register the artifact."""
    started = time.time()
    rows = await build_duration_dataset(session, tenant_id)
    if not rows:
        raise TrainingError(
            "duration: no training rows — factory_curated.order_phase is "
            "empty. Run the ERP sync first."
        )

    model = DurationModel()
    try:
        metrics = model.train(rows)
    except ValueError as exc:
        raise TrainingError(f"duration: {exc}") from exc

    registry = ModelRegistry(session, tenant_id)
    artifact = await registry.save(
        model_name="duration",
        model=model,
        metrics=metrics,
        trained_by=trained_by,
        training_duration_sec=round(time.time() - started, 3),
        training_samples=int(metrics.get("samples", len(rows))),
    )
    promoted = False
    if promote:
        await registry.promote(artifact.id, decision_id=None, promoted_by=trained_by)
        promoted = True

    logger.info(
        "train_duration: v%s registered (wmape=%s, samples=%s, promoted=%s)",
        artifact.version, metrics.get("wmape"), metrics.get("samples"), promoted,
    )
    return {
        "model_name": "duration",
        "version": artifact.version,
        "artifact_id": str(artifact.id),
        "metrics": metrics,
        "promoted": promoted,
    }


async def ensure_quality_risk_model(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[Dict[str, Any]]:
    """Train + promote `quality_risk` only if no active version exists yet.

    Used by the defect-risk endpoint so the Qualidade page bootstraps the
    model on first use instead of staring at an empty registry. Returns the
    training summary when it trained, ``None`` when a model was already
    active. Swallows `TrainingError` (caller degrades honestly).
    """
    registry = ModelRegistry(session, tenant_id)
    active = await registry.get_active("quality_risk")
    if active is not None:
        return None
    try:
        summary = await train_quality_risk(session, tenant_id)
        await session.commit()
        return summary
    except TrainingError as exc:
        logger.warning("ensure_quality_risk_model: %s", exc)
        await session.rollback()
        return None
