"""
ProdPlan ONE — RetrainJob Base
===============================

Abstract lifecycle for a scheduled model retrain. Concrete subclasses live
in Sprint H (`src/ml/models_domain/`); this module only codifies the flow
so every model retrains the same way.

Lifecycle:
    1. extract_features(tenant_id)     — pull training data from curated
    2. train(features)                  — fit model
    3. validate(model, features)        — emit metrics dict
    4. should_promote(new, baseline)    — policy hook; default: WMAPE better
    5. save via ModelRegistry           — persist artifact + row
    6. propose_promotion via governance — creates DecisionRun
    7. (governance approves) → registry.promote()

Jobs register their `schedule_cron` with APScheduler in `start_scheduler`.
"""

from __future__ import annotations

import logging

from src.shared.coerce import safe_float as _safe_float
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.models.orm import MLModelArtifact
from src.ml.models.promotion import propose_promotion
from src.ml.models.registry import ModelRegistry
from src.ml.observability.metrics import (
    ml_training_duration_seconds,
    ml_training_runs_total,
    ml_training_samples_total,
    ml_validation_metric,
)

logger = logging.getLogger(__name__)


class EmptyDatasetError(RuntimeError):
    """Raised when a RetrainJob's `extract_features` produced an empty
    dataset. Surfaces loud (FASE 1B.7 / CRIT-04) instead of letting the
    job train on nothing and silently mark the run as success.
    """


def _is_empty_features(features: Any) -> bool:
    """Best-effort emptiness check across the formats subclasses use.

    `extract_features` returns a list-of-dicts in the current code base
    but DataFrames / numpy arrays are also common in ML, so we accept
    anything with ``len()``. None always counts as empty.
    """
    if features is None:
        return True
    try:
        return len(features) == 0
    except TypeError:
        return False  # non-sized: trust the subclass to validate


class RetrainJob(ABC):
    """
    Base class for a periodic retrain. Subclasses fix `model_name` and
    implement `extract_features`, `train`, `validate`.
    """

    #: Stable identifier used for ModelRegistry rows and Prometheus labels.
    model_name: str = "unnamed_model"

    #: Cron expression for APScheduler (UTC). Override per model.
    schedule_cron: str = "0 2 * * *"

    # -------------------- Required subclass methods ------------------- #

    @abstractmethod
    def extract_features(self, tenant_id: UUID) -> Any:
        """Return a feature matrix / training dataset."""

    @abstractmethod
    def train(self, features: Any) -> Tuple[Any, int]:
        """
        Return `(trained_model, n_samples)`. The samples count is recorded
        in the artifact row and in Prometheus counters.
        """

    @abstractmethod
    def validate(self, model: Any, features: Any) -> Dict[str, Any]:
        """
        Produce a metrics dict (e.g. `{"wmape": 0.08, "auc": 0.82}`).
        Used by `should_promote` and recorded in the artifact row.
        """

    # -------------------- Overridable defaults ------------------------ #

    def should_promote(
        self,
        new_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Default policy: promote iff we have no baseline yet, or WMAPE
        strictly improved. Subclasses can override (e.g., gate on AUC).
        """
        if not baseline_metrics:
            return True
        new_wmape = _safe_float(new_metrics.get("wmape"))
        old_wmape = _safe_float(baseline_metrics.get("wmape"))
        if new_wmape is None or old_wmape is None:
            return False
        return new_wmape < old_wmape

    # -------------------- Orchestration ------------------------------- #

    async def run(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        governance_service: Optional[Any] = None,
        proposed_by: str = "retrain_job",
    ) -> Dict[str, Any]:
        """
        Execute the full retrain lifecycle. Caller commits the session.

        Returns a summary dict with `status`, `artifact_id`, `metrics`,
        `decision_id`, `training_duration_sec`.
        """
        started = time.time()
        registry = ModelRegistry(session, tenant_id)
        baseline = await registry.get_active(self.model_name)
        baseline_metrics = baseline.metrics if baseline else None

        try:
            features = self.extract_features(tenant_id)
            # FASE 1B.7 (CRIT-04) — refuse to train on an empty dataset.
            # Without this guard, downstream `train()` would either crash
            # with an opaque sklearn error or (worse) silently fit a
            # degenerate model that gets persisted and proposed for
            # promotion. Raise a typed exception so the surrounding try
            # records the run as failure with a clear reason.
            if _is_empty_features(features):
                raise EmptyDatasetError(
                    f"{self.model_name}: extract_features returned an empty "
                    f"dataset for tenant={tenant_id} — likely a curated-layer "
                    "outage or a tenant with no historical phase rows. "
                    "Ingest data via /v1/factory-data/ingest before retrying."
                )
            with ml_training_duration_seconds.labels(model_name=self.model_name).time():
                model, n_samples = self.train(features)
            metrics = self.validate(model, features)
        except Exception as e:
            ml_training_runs_total.labels(model_name=self.model_name, outcome="failure").inc()
            logger.error(f"Retrain failed for {self.model_name}: {e}", exc_info=True)
            return {
                "status": "failed",
                "model_name": self.model_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "training_duration_sec": round(time.time() - started, 3),
            }

        # Persist the artifact regardless of promotion outcome — it's still
        # useful audit data ("we tried, metrics were X, chose not to promote").
        duration_sec = round(time.time() - started, 3)
        artifact = await registry.save(
            model_name=self.model_name,
            model=model,
            metrics=metrics,
            trained_by=proposed_by,
            training_duration_sec=duration_sec,
            training_samples=n_samples,
        )
        ml_training_samples_total.labels(model_name=self.model_name).inc(n_samples or 0)
        for metric_name, metric_value in metrics.items():
            if _safe_float(metric_value) is not None:
                ml_validation_metric.labels(
                    model_name=self.model_name,
                    metric_name=metric_name,
                ).set(float(metric_value))

        decision_id: Optional[str] = None
        promoted = False
        if self.should_promote(metrics, baseline_metrics) and governance_service is not None:
            try:
                decision = await propose_promotion(
                    governance=governance_service,
                    artifact=artifact,
                    baseline_metrics=baseline_metrics,
                    proposed_by=proposed_by,
                )
                decision_id = decision.get("id")
                promoted = decision.get("status") == "approved"
            except Exception as e:
                logger.warning(f"Governance proposal failed for {self.model_name}: {e}")

        ml_training_runs_total.labels(
            model_name=self.model_name,
            outcome="success",
        ).inc()

        return {
            "status": "success",
            "model_name": self.model_name,
            "artifact_id": str(artifact.id),
            "version": artifact.version,
            "metrics": metrics,
            "baseline_metrics": baseline_metrics,
            "decision_id": decision_id,
            "auto_promoted": promoted,
            "training_duration_sec": duration_sec,
            "training_samples": n_samples,
        }
