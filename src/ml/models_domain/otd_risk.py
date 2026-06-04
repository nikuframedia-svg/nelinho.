"""
ProdPlan ONE — OTDRiskModel (Sprint Q.54.F)
============================================

Predicts `P(order misses its transport/delivery date | features)` for an
open production order. Where `QualityRiskModel` scores a *phase*'s defect
risk, this model scores an *order*'s schedule risk: will this kayak ship
late?

Consumed by the Painel / Direção layer so a manager sees, ahead of time,
that a boat is heading for a late delivery — instead of finding out on
the transport day. It is deliberately *not* wired into the CPO fitness
loop: the GA already optimises tardiness directly from the decoder's
exact `total_tardiness_hours`, so an ML estimate there would only add
noise. OTD-risk is a *forecast for humans*, not a scheduler objective.

Baseline model: `GradientBoostingClassifier` (same family as
`QualityRiskModel`) so the registry / promotion / observability plumbing
is identical.

RetrainJob schedule: daily at 03:00 UTC — the late/on-time label settles
as orders complete, and a manager wants a fresh forecast each morning.

Honesty rules (ZERO MOCKS):
  * No history → caller gets `None` from the registry loader and the
    Painel shows an explicit "sem modelo treinado" state.
  * Training needs ≥20 rows with both a late and an on-time example, or
    `train()` raises (RetrainJob records the run as failed, loud).
"""

from __future__ import annotations

import logging

from src.shared.coerce import safe_float as _safe_float
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID

# Q.59.F.3 — numpy/sklearn movidos para dentro dos métodos que os usam
# (`train`, `validate`). Estavam top-level e custavam ~500 ms no arranque.
# PEP 563 ativo (from __future__ import annotations), portanto
# `Optional[GradientBoostingClassifier]` resolve em tempo de check.
if TYPE_CHECKING:
    from sklearn.ensemble import GradientBoostingClassifier

from src.ml.jobs.base import RetrainJob
from src.ml.models_domain._common import encode_categoricals

logger = logging.getLogger(__name__)


# Feature schema. `modelo_id` captures product-family difficulty;
# `n_phases` / `total_planned_hours` size the order; `slack_days` is the
# headroom between the planned finish and the due date (negative = the
# plan itself already overruns); `open_phases` is how much is still left
# to do; `phase_error_rate_mean` folds in the quality drag.
CATEGORICAL_COLS = ("modelo_id",)
NUMERIC_COLS = (
    "n_phases",
    "total_planned_hours",
    "slack_days",
    "open_phases",
    "phase_error_rate_mean",
)


@dataclass
class OTDRiskModel:
    """Binary classifier: 1 = order expected to miss its date, 0 = on time."""

    classifier: Optional[GradientBoostingClassifier] = None
    vocabulary: Dict[str, List[str]] = field(default_factory=dict)
    positive_rate: float = 0.0  # prior P(late) from training data
    n_samples_trained: int = 0

    def train(
        self,
        rows: List[Dict[str, Any]],
        *,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        if not rows:
            raise ValueError("OTDRiskModel.train called with empty rows")
        if len(rows) < 20:
            raise ValueError(f"OTDRiskModel needs >=20 rows; got {len(rows)}")

        # Q.59.F.3 — imports diferidos para fora do startup.
        import numpy as np
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.metrics import average_precision_score, roc_auc_score
        from sklearn.model_selection import train_test_split

        y = np.asarray([int(r.get("is_late", 0)) for r in rows], dtype=np.int32)
        if y.sum() == 0 or y.sum() == len(y):
            raise ValueError(
                "OTDRiskModel needs at least one late and one on-time sample"
            )

        # Temporal split when every row carries a timestamp — OTD drifts
        # with factory load, so a random split leaks future seasons into
        # training and inflates AUC. Same approach as QualityRiskModel.
        timestamps = [r.get("timestamp") for r in rows]
        has_temporal = len(rows) >= 20 and all(t is not None for t in timestamps)

        if has_temporal:
            order_idx = sorted(range(len(rows)), key=lambda i: timestamps[i])
            split_at = round(len(order_idx) * 0.8)
            train_idx = order_idx[:split_at]
            val_idx = order_idx[split_at:]
            sorted_rows = [rows[i] for i in train_idx + val_idx]
            y = np.concatenate([y[train_idx], y[val_idx]])

            X, vocab = encode_categoricals(sorted_rows, CATEGORICAL_COLS, NUMERIC_COLS)
            self.vocabulary = vocab
            self.n_samples_trained = len(sorted_rows)
            self.positive_rate = float(y.mean())

            X_train = X[: len(train_idx)]
            X_val = X[len(train_idx):]
            y_train = y[: len(train_idx)]
            y_val = y[len(train_idx):]
        else:
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

        # Hyperparams from MLConfig (env-overridable), defaulting to the
        # same values QualityRiskModel uses for its "quality_risk" key
        # unless an "otd_risk" override is configured.
        from src.ml.config import get_config
        hp = get_config().hyperparams_for("otd_risk")
        clf = GradientBoostingClassifier(
            n_estimators=int(hp.get("n_estimators", 120)),
            max_depth=int(hp.get("max_depth", 3)),
            learning_rate=float(hp.get("learning_rate", 0.1)),
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
            # 1 - AUC so the RetrainJob default should_promote (lower
            # WMAPE wins) stays meaningful as a fallback.
            "wmape": round(1.0 - _safe_metric(roc_auc_score, y_val, proba), 4),
        }
        logger.info(
            f"OTDRiskModel trained: AUC={metrics['auc']}, AP={metrics['ap']}, "
            f"positive_rate={metrics['positive_rate']}, samples={metrics['samples']}"
        )
        return metrics

    def predict_proba(self, row: Dict[str, Any]) -> float:
        if self.classifier is None:
            raise RuntimeError("OTDRiskModel.predict_proba called before train()")
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

    def flag_threshold(self, row: Dict[str, Any], threshold: float = 0.5) -> bool:
        """Convenience: True if predicted P(late) >= threshold."""
        return self.predict_proba(row) >= threshold


# ---------------------------------------------------------------------------
# RetrainJob
# ---------------------------------------------------------------------------

class OTDRiskRetrainJob(RetrainJob):
    model_name = "otd_risk"
    schedule_cron = "0 3 * * *"  # daily 03:00 UTC

    def __init__(self, semantic_queries: Any = None):
        self.semantic_queries = semantic_queries

    def extract_features(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        rows = build_training_dataset(self.semantic_queries)
        logger.info(f"OTDRiskRetrainJob extracted {len(rows)} rows")
        return rows

    def train(self, features: List[Dict[str, Any]]) -> Tuple[OTDRiskModel, int]:
        model = OTDRiskModel()
        metrics = model.train(features)
        return model, int(metrics["samples"])

    def validate(
        self,
        model: OTDRiskModel,
        features: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not features or len(features) < 20:
            return {}
        # Q.59.F.3 — imports diferidos.
        import numpy as np
        from sklearn.metrics import average_precision_score, roc_auc_score
        sample = features[:min(200, len(features))]
        probs = model.predict_proba_batch(sample)
        y_true = np.asarray([int(r.get("is_late", 0)) for r in sample])
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
        # Promote on AUC improvement; fall back to RetrainJob default
        # (WMAPE) when AUC is missing.
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
    Build one row per completed order with a binary `is_late` label.

    Joins `CuratedOrder` ⋈ `CuratedOrderPhase` ⋈ `CuratedQualityEvent`.
    An order is `is_late=1` when its real finish (latest phase
    `data_fim_real`) is after its `data_entrega_prevista` (due date).

    Returns ``[]`` when curated data isn't available — the caller
    (`RetrainJob.run`) turns an empty dataset into `EmptyDatasetError`
    so silent training-on-nothing is impossible.
    """
    if semantic_queries is None:
        logger.warning(
            "otd_risk build_training_dataset: semantic_queries is None — "
            "returning empty dataset."
        )
        return []
    engine = getattr(semantic_queries, "engine", None)
    if engine is None:
        logger.warning(
            "otd_risk build_training_dataset: semantic engine missing — "
            "returning empty dataset."
        )
        return []

    active_id = getattr(engine, "_active_ingestion_id", None)
    curated = getattr(engine, "_curated_data", {}) or {}
    scope = curated.get(active_id, {}) if active_id else {}

    phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []
    orders = scope.get("orders") or scope.get("CuratedOrder") or []
    quality = scope.get("quality_events") or scope.get("CuratedQualityEvent") or []

    # Per-phase historical error rate, reused as the order-level mean.
    phase_totals: Dict[str, int] = {}
    phase_errors: Dict[str, int] = {}
    for p in phases:
        fid = str(getattr(p, "fase_id", ""))
        phase_totals[fid] = phase_totals.get(fid, 0) + 1
    for e in quality:
        fid = str(getattr(e, "fase_id", "") or "")
        if fid:
            phase_errors[fid] = phase_errors.get(fid, 0) + 1

    def _phase_error_rate(fid: str) -> float:
        total = phase_totals.get(fid, 0)
        return (phase_errors.get(fid, 0) / total) if total else 0.0

    # Group phases per order.
    phases_by_order: Dict[str, List[Any]] = {}
    for p in phases:
        of_id = str(getattr(p, "of_id", ""))
        if of_id:
            phases_by_order.setdefault(of_id, []).append(p)

    rows: List[Dict[str, Any]] = []
    for o in orders:
        of_id = str(getattr(o, "of_id", "") or "")
        if not of_id:
            continue
        due = getattr(o, "data_entrega_prevista", None)
        if due is None:
            # No promised date → nothing to be late on, skip.
            continue
        order_phases = phases_by_order.get(of_id, [])
        if not order_phases:
            continue

        finish_times = [
            getattr(p, "data_fim_real", None)
            for p in order_phases
            if getattr(p, "data_fim_real", None) is not None
        ]
        if not finish_times:
            # Order not finished yet — no label, exclude from training.
            continue
        real_finish = max(finish_times)

        try:
            is_late = 1 if real_finish > due else 0
        except TypeError:
            # tz-aware vs naive mismatch — skip rather than guess.
            continue

        planned_hours = sum(
            float(getattr(p, "horas_reais", 0) or getattr(p, "horas_standard", 0) or 0)
            for p in order_phases
        )
        slack_days = 0.0
        try:
            slack_days = (due - real_finish).total_seconds() / 86400.0
        except (TypeError, AttributeError):
            slack_days = 0.0

        error_rates = [
            _phase_error_rate(str(getattr(p, "fase_id", ""))) for p in order_phases
        ]
        phase_error_rate_mean = (
            sum(error_rates) / len(error_rates) if error_rates else 0.0
        )

        rows.append({
            "modelo_id": str(getattr(o, "modelo_id", "") or ""),
            "n_phases": len(order_phases),
            "total_planned_hours": round(planned_hours, 2),
            "slack_days": round(slack_days, 2),
            # All phases are finished in the training set, so open=0; the
            # column exists so the inference-time projector (open orders)
            # can feed a non-zero value with the same schema.
            "open_phases": 0,
            "phase_error_rate_mean": round(phase_error_rate_mean, 4),
            "is_late": is_late,
            "timestamp": real_finish,
        })

    return rows


def _safe_metric(fn, y_true, y_score) -> float:
    try:
        return float(fn(y_true, y_score))
    except Exception as e:
        logger.warning(f"Metric {fn.__name__} failed: {e}")
        return 0.0
