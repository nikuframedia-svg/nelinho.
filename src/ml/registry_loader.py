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
# Sprint Q.54.F — OTD-risk shares the quality-risk shape: a batch of
# order feature rows → a batch of P(late) floats in [0, 1].
OTDRiskPredictor = Callable[[List[Dict[str, Any]]], List[float]]


def _instrumented_predictor(fn: Callable, *, model_name: str) -> Callable:
    """FASE 4.2 (HIGH-55/56) — wrap a predict callable with Prometheus
    latency + error metrics. Defensive on import: tests that don't pull
    in prometheus_client get the bare callable back.
    """
    try:
        from src.ml.observability.metrics import (
            ml_inference_errors_total,
            ml_inference_latency_ms,
        )
    except Exception:  # pragma: no cover — defensive
        return fn

    import time

    def wrapped(*args, **kwargs):
        started = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            try:
                ml_inference_errors_total.labels(
                    model_name=model_name,
                    error_type=type(exc).__name__,
                ).inc()
            except Exception:  # noqa: S110  Q.61.06: metrics best-effort; never cascade
                pass
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            try:
                ml_inference_latency_ms.labels(model_name=model_name).observe(elapsed_ms)
            except Exception:  # noqa: S110  Q.61.06: metrics best-effort; never cascade
                pass

    wrapped.__name__ = getattr(fn, "__name__", "predict")
    wrapped.__qualname__ = getattr(fn, "__qualname__", "predict")
    return wrapped


async def load_active_quality_risk_predictor(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[QualityRiskPredictor]:
    """Return a callable predictor or None when no active artifact exists.

    The callable adapts `QualityRiskModel.predict_proba_batch` so the CPO
    fitness loop can call ``predictor(feature_rows) -> List[float]``
    without touching ML internals.

    FASE 4.2 (HIGH-55/56) — the returned callable is wrapped with
    Prometheus instrumentation: each call emits
    ``ml_inference_latency_ms`` (histogram) and exceptions bump
    ``ml_inference_errors_total`` (counter). Dashboards that watch ML
    inference health can finally see traffic.
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
    return _instrumented_predictor(
        model.predict_proba_batch, model_name="quality_risk",
    )


async def load_active_otd_risk_predictor(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[OTDRiskPredictor]:
    """Return a callable OTD-risk predictor or None when no active
    artifact exists.

    Sprint Q.54.F. The callable adapts ``OTDRiskModel.predict_proba_batch``
    so the Painel / Direção layer can call ``predictor(order_rows) ->
    List[float]`` (P(late) per order) without touching ML internals.
    Mirrors ``load_active_quality_risk_predictor`` exactly — same
    instrumentation, same graceful-None fallbacks.
    """
    registry = ModelRegistry(session, tenant_id)
    try:
        active = await registry.get_active("otd_risk")
    except Exception as exc:
        logger.warning("otd_risk: get_active failed (%s) — predictor disabled", exc)
        return None
    if active is None:
        return None
    try:
        model = registry.load(active.storage_uri)
    except Exception as exc:
        logger.warning(
            "otd_risk: load failed for v%s (%s) — predictor disabled",
            active.version, exc,
        )
        return None
    if not hasattr(model, "predict_proba_batch"):
        logger.warning(
            "otd_risk: artifact v%s has no predict_proba_batch — skip",
            active.version,
        )
        return None
    return _instrumented_predictor(
        model.predict_proba_batch, model_name="otd_risk",
    )


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
    # FASE 4.2 (HIGH-55/56) — instrument predict + predict_batch in
    # place so callers (RoutingResolver) automatically feed Prometheus.
    if hasattr(model, "predict"):
        model.predict = _instrumented_predictor(model.predict, model_name="duration")
    if hasattr(model, "predict_batch"):
        model.predict_batch = _instrumented_predictor(
            model.predict_batch, model_name="duration",
        )
    return model
