"""Q.68.5.B — quality risk scoring job (batch inference).

Wraps :class:`src.quality.services.defect_risk_service.DefectRiskService`
into a job-friendly entry point that the APScheduler tick can call. The
scoring service already does the heavy lifting (load active artifact,
fetch in-progress orders, build feature rows, predict in batch, sort by
risk band); this module just:

1. Adds the session lifecycle (`get_session_context`) so the scheduler
   doesn't have to know how to open one.
2. Returns a small metrics dict the caller can log uniformly:
   ``{"scored": int, "model_version": int | None, "elapsed_ms": int,
   "high_risk": int}``.
3. Degrades cleanly when no model is active yet (returns ``scored=0``
   with ``model_version=None``) so the first tick on a tenant without
   any training history does not crash the scheduler.

Persistence note: the DefectRiskService returns scored rows but does
*not* persist a `quality_risk_score` column anywhere — Q.66 deliberately
left batch persistence to the read path (the Qualidade page calls the
service on demand). This job exists to drive the *signal*: it warms the
predictor (which forces ``ensure_quality_risk_model`` to train on first
use), emits Prometheus inference metrics via the instrumented
predictor, and gives operators a heartbeat that the scoring pipeline is
healthy. Persisting per-order scores to a dedicated table is left for
Q.68.5.C (out of scope here).
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from src.ml.models.registry import ModelRegistry
from src.quality.services.defect_risk_service import DefectRiskService
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)


async def score_quality_risk_for_tenant(tenant_id: UUID) -> dict[str, Any]:
    """Run batch quality-risk scoring for ``tenant_id``.

    Returns a metrics dict::

        {
            "scored": int,            # number of orders scored
            "model_version": int|None # active artifact version, None if absent
            "high_risk": int,         # orders with risk_band == "alto"
            "elapsed_ms": int,        # wall-clock duration
            "model_available": bool,  # mirrors DefectRiskService output
        }

    Never raises into the scheduler: any failure inside the service is
    logged at warning and reported as ``model_available=False`` so the
    next tick can try again.
    """
    started = time.perf_counter()
    result: dict[str, Any] = {
        "scored": 0,
        "model_version": None,
        "high_risk": 0,
        "elapsed_ms": 0,
        "model_available": False,
    }

    try:
        async with get_session_context() as session:
            # Active version (may be None when no model trained yet).
            try:
                registry = ModelRegistry(session, tenant_id)
                active = await registry.get_active("quality_risk")
                if active is not None:
                    result["model_version"] = int(active.version)
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug(
                    "quality_risk_scoring tenant=%s: get_active probe failed "
                    "(%s); continuing — service will short-circuit.",
                    tenant_id, exc,
                )

            service = DefectRiskService(session, tenant_id)
            payload = await service.defect_risk(top_n=1000)

            model_available = bool(payload.get("model_available", False))
            result["model_available"] = model_available
            if not model_available:
                logger.info(
                    "quality_risk_scoring tenant=%s: no active model — "
                    "skipping (%s).",
                    tenant_id, payload.get("reason", ""),
                )
            else:
                orders = payload.get("orders") or []
                result["scored"] = int(payload.get("total_orders", len(orders)))
                result["high_risk"] = int(payload.get("high_risk_count", 0))

            # Commit picks up any side-effects from ensure_quality_risk_model
            # (it can train+promote a fresh artifact on first use).
            await session.commit()
    except Exception as exc:
        logger.warning(
            "quality_risk_scoring tenant=%s failed: %s",
            tenant_id, exc, exc_info=True,
        )

    result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return result
