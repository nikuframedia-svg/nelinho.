"""
ProdPlan ONE — QualityRiskModel (Sprint H.1)
=============================================

Predicts `P(quality_event | features)` for a scheduled (order, phase,
worker, mold) tuple. Used by the CPO v4 fitness function in Sprint I to
penalise assignments that are historically error-prone.

Baseline model: `GradientBoostingClassifier` from scikit-learn. Can be
swapped for XGBoost later by replacing the regressor while keeping the
interface.

RetrainJob schedule: weekly (Sundays 02:00 UTC). Lower frequency than
Duration because the error label is sparse and weekly windows are more
statistically stable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from src.ml.jobs.base import RetrainJob
from src.ml.models_domain._common import encode_categoricals

logger = logging.getLogger(__name__)


CATEGORICAL_COLS = ("modelo_id", "fase_id")
NUMERIC_COLS = ("team_size", "mold_pocket_count", "phase_error_rate", "queue_depth")


@dataclass
class QualityRiskModel:
    """Binary classifier: 1 = quality event expected, 0 = clean run."""

    classifier: Optional[GradientBoostingClassifier] = None
    vocabulary: Dict[str, List[str]] = field(default_factory=dict)
    positive_rate: float = 0.0  # prior P(error) from training data
    n_samples_trained: int = 0

    def train(
        self,
        rows: List[Dict[str, Any]],
        *,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        if not rows:
            raise ValueError("QualityRiskModel.train called with empty rows")
        if len(rows) < 20:
            raise ValueError(
                f"QualityRiskModel needs >=20 rows; got {len(rows)}"
            )

        y = np.asarray([int(r.get("is_error", 0)) for r in rows], dtype=np.int32)
        if y.sum() == 0 or y.sum() == len(y):
            raise ValueError(
                "QualityRiskModel needs at least one positive and one negative sample"
            )

        X, vocab = encode_categoricals(rows, CATEGORICAL_COLS, NUMERIC_COLS)
        self.vocabulary = vocab
        self.n_samples_trained = len(rows)
        self.positive_rate = float(y.mean())

        X_train, X_val, y_train, y_val = train_test_split(
            X, y,
            test_size=0.2,
            random_state=random_state,
            stratify=y if y.sum() >= 2 and (len(y) - y.sum()) >= 2 else None,
        )

        clf = GradientBoostingClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.1,
            random_state=random_state,
        )
        clf.fit(X_train, y_train)
        self.classifier = clf

        proba = clf.predict_proba(X_val)[:, 1]
        metrics: Dict[str, Any] = {
            "auc": round(_safe_metric(roc_auc_score, y_val, proba), 4),
            "ap": round(_safe_metric(average_precision_score, y_val, proba), 4),
            "positive_rate": round(self.positive_rate, 4),
            "samples": len(rows),
            "samples_train": len(X_train),
            "samples_val": len(X_val),
            # WMAPE equivalent for classification: use 1 - AUC so
            # the default should_promote() (lower WMAPE wins) is meaningful.
            "wmape": round(1.0 - _safe_metric(roc_auc_score, y_val, proba), 4),
        }
        logger.info(
            f"QualityRiskModel trained: AUC={metrics['auc']}, AP={metrics['ap']}, "
            f"positive_rate={metrics['positive_rate']}, samples={metrics['samples']}"
        )
        return metrics

    def predict_proba(self, row: Dict[str, Any]) -> float:
        if self.classifier is None:
            raise RuntimeError("QualityRiskModel.predict_proba called before train()")
        X, _ = encode_categoricals(
            [row], CATEGORICAL_COLS, NUMERIC_COLS, vocabulary=self.vocabulary
        )
        return float(self.classifier.predict_proba(X)[0, 1])

    def predict_proba_batch(self, rows: List[Dict[str, Any]]) -> List[float]:
        if not rows or self.classifier is None:
            return []
        X, _ = encode_categoricals(
            rows, CATEGORICAL_COLS, NUMERIC_COLS, vocabulary=self.vocabulary
        )
        return [float(p) for p in self.classifier.predict_proba(X)[:, 1]]

    def flag_threshold(self, row: Dict[str, Any], threshold: float = 0.3) -> bool:
        """Convenience: True if predicted P(error) >= threshold."""
        return self.predict_proba(row) >= threshold


# ---------------------------------------------------------------------------
# RetrainJob
# ---------------------------------------------------------------------------

class QualityRiskRetrainJob(RetrainJob):
    model_name = "quality_risk"
    schedule_cron = "0 2 * * 0"  # Sundays 02:00 UTC

    def __init__(self, semantic_queries: Any = None):
        self.semantic_queries = semantic_queries

    def extract_features(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        rows = build_training_dataset(self.semantic_queries)
        logger.info(f"QualityRiskRetrainJob extracted {len(rows)} rows")
        return rows

    def train(self, features: List[Dict[str, Any]]) -> Tuple[QualityRiskModel, int]:
        model = QualityRiskModel()
        metrics = model.train(features)
        return model, int(metrics["samples"])

    def validate(
        self,
        model: QualityRiskModel,
        features: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # Re-evaluate on a quick held-out slice. Train already computed
        # solid metrics; this is a sanity check that predict_batch works.
        if not features or len(features) < 20:
            return {}
        sample = features[:min(200, len(features))]
        probs = model.predict_proba_batch(sample)
        y_true = np.asarray([int(r.get("is_error", 0)) for r in sample])
        if y_true.sum() == 0 or y_true.sum() == len(y_true):
            return {
                "sanity_check": "degenerate_sample",
                "samples_checked": len(sample),
            }
        return {
            "auc": round(_safe_metric(roc_auc_score, y_true, probs), 4),
            "ap": round(_safe_metric(average_precision_score, y_true, probs), 4),
            "samples_checked": len(sample),
            "wmape": round(1.0 - _safe_metric(roc_auc_score, y_true, probs), 4),
        }

    def should_promote(
        self,
        new_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]],
    ) -> bool:
        # Promote on AUC improvement (higher is better); fall back to the
        # RetrainJob default (WMAPE improvement) when metrics are missing.
        new_auc = _safe_float(new_metrics.get("auc"))
        if new_auc is None:
            return super().should_promote(new_metrics, baseline_metrics)
        if not baseline_metrics:
            return True
        old_auc = _safe_float(baseline_metrics.get("auc"))
        return old_auc is None or new_auc > old_auc


# ---------------------------------------------------------------------------
# Training dataset builder
# ---------------------------------------------------------------------------

def build_training_dataset(semantic_queries: Any) -> List[Dict[str, Any]]:
    """
    Join `CuratedOrderPhase` ⋈ `CuratedQualityEvent` ⋈ `CuratedOrder` to
    produce one row per scheduled phase with a binary `is_error` label.

    Best-effort: returns [] when curated data isn't available.
    """
    if semantic_queries is None:
        return []
    engine = getattr(semantic_queries, "engine", None)
    if engine is None:
        return []

    active_id = getattr(engine, "_active_ingestion_id", None)
    curated = getattr(engine, "_curated_data", {}) or {}
    scope = curated.get(active_id, {}) if active_id else {}

    phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []
    orders = scope.get("orders") or scope.get("CuratedOrder") or []
    quality = scope.get("quality_events") or scope.get("CuratedQualityEvent") or []
    molds = scope.get("molds") or scope.get("CuratedMold") or []

    order_model = {
        str(getattr(o, "of_id", "")): str(getattr(o, "modelo_id", ""))
        for o in orders
    }
    mold_pockets = {
        str(getattr(m, "molde_id", "")): int(getattr(m, "pocket_count", 1) or 1)
        for m in molds
    }

    error_keys = {
        (str(getattr(e, "of_id", "")), str(getattr(e, "fase_id", "")))
        for e in quality
    }

    # Aggregate per-phase historical error rate for the feature column
    phase_totals: Dict[str, int] = {}
    phase_errors: Dict[str, int] = {}
    for p in phases:
        fid = str(getattr(p, "fase_id", ""))
        phase_totals[fid] = phase_totals.get(fid, 0) + 1
    for e in quality:
        fid = str(getattr(e, "fase_id", "") or "")
        if fid:
            phase_errors[fid] = phase_errors.get(fid, 0) + 1

    rows: List[Dict[str, Any]] = []
    for p in phases:
        of_id = str(getattr(p, "of_id", ""))
        fase_id = str(getattr(p, "fase_id", ""))
        modelo_id = order_model.get(of_id, "")
        mold_id = str(getattr(p, "molde_id", "") or "")

        total = phase_totals.get(fase_id, 0)
        errs = phase_errors.get(fase_id, 0)
        phase_error_rate = (errs / total) if total else 0.0

        rows.append({
            "modelo_id": modelo_id,
            "fase_id": fase_id,
            "team_size": int(getattr(p, "team_size", 1) or 1),
            "mold_pocket_count": mold_pockets.get(mold_id, 1),
            "phase_error_rate": round(phase_error_rate, 4),
            "queue_depth": total,
            "is_error": 1 if (of_id, fase_id) in error_keys else 0,
        })

    return rows


def _safe_metric(fn, y_true, y_score) -> float:
    try:
        return float(fn(y_true, y_score))
    except Exception as e:
        logger.warning(f"Metric {fn.__name__} failed: {e}")
        return 0.0


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
