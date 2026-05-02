"""
ProdPlan ONE — ML Registry Loader (FASE 0 wiring)
==================================================

Helpers that turn a persisted `MLModelArtifact` into a concrete callable the
scheduler can invoke at runtime. Bridges the gap between the ML registry
(Sprint G) and the consumers in `src/plan/` that were previously holding
`None` placeholders (DEVA-01 + DEVA-02).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.models.registry import ModelRegistry

logger = logging.getLogger(__name__)


QualityRiskPredictor = Callable[[List[Dict[str, Any]]], List[float]]
DurationPredictor = Callable[[List[Dict[str, Any]]], List[Dict[str, float]]]


async def load_active_quality_risk_predictor(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[QualityRiskPredictor]:
    """Return a callable predictor or None when no active artifact exists.

    The callable adapts `QualityRiskModel.predict_proba_batch` so the CPO
    fitness loop can call ``predictor(feature_rows) -> List[float]``
    without touching ML internals.
    """
    registry = ModelRegistry(session, tenant_id)
    try:
        active = await registry.get_active("quality_risk")
    except Exception as exc:
        logger.warning("quality_risk: get_active failed (%s) — predictor disabled", exc)
        return None
    if active is None:
        return None
    try:
        model = registry.load(active.storage_uri)
    except Exception as exc:
        logger.warning(
            "quality_risk: load failed for v%s (%s) — predictor disabled",
            active.version, exc,
        )
        return None
    if not hasattr(model, "predict_proba_batch"):
        logger.warning(
            "quality_risk: artifact v%s has no predict_proba_batch — skip",
            active.version,
        )
        return None
    return model.predict_proba_batch  # type: ignore[return-value]


async def load_active_duration_predictor(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[Any]:
    """Return the active `DurationModel` instance or None.

    Returns the model object itself (not a thin lambda) because callers
    typically need both ``predict_batch`` and ``predict`` and the routing
    resolver also reads ``model.median_residual_h`` for the p90 fallback.
    """
    registry = ModelRegistry(session, tenant_id)
    try:
        active = await registry.get_active("duration")
    except Exception as exc:
        logger.warning("duration: get_active failed (%s) — predictor disabled", exc)
        return None
    if active is None:
        return None
    try:
        model = registry.load(active.storage_uri)
    except Exception as exc:
        logger.warning(
            "duration: load failed for v%s (%s) — predictor disabled",
            active.version, exc,
        )
        return None
    if not hasattr(model, "predict_batch") and not hasattr(model, "predict"):
        logger.warning(
            "duration: artifact v%s has no predict/predict_batch — skip",
            active.version,
        )
        return None
    return model
