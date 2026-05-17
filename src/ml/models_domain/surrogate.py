"""
ProdPlan ONE — SurrogateModel (Sprint H.3)
===========================================

Meta-model that approximates the CPO v4 fitness function. The GA in
Sprint F queries it *before* running the expensive greedy decoder; if
the predicted fitness is far worse than the best known, the candidate
is skipped, saving the real evaluation.

- Input features: a `Chromosome` + `FactoryState` aggregates that
  correlate with fitness (n_ops, avg_duration, edd_gap, buffer_pct,
  quality_weight, n_orders, permutation_entropy).
- Target: real fitness produced by the CPO decoder.
- Algorithm: RandomForestRegressor — robust to noisy labels, no tuning
  needed for the MVP. The GA adds threshold rejection at 1.2x (see plan).

RetrainJob fires every 50 new real evaluations, not on a clock — so its
`schedule_cron` is empty and the GA calls `retrain_if_needed()` directly.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from src.ml.jobs.base import RetrainJob
from src.ml.models_domain._common import wmape

logger = logging.getLogger(__name__)


FEATURE_ORDER: Tuple[str, ...] = (
    "n_ops",
    "n_orders",
    "edd_gap",
    "buffer_pct",
    "quality_weight",
    "avg_duration_min",
    "permutation_entropy",
)


@dataclass
class SurrogateModel:
    """Estimate real-fitness from chromosome+state features."""

    regressor: Optional[RandomForestRegressor] = None
    n_samples_trained: int = 0
    best_known_fitness: float = float("inf")

    def train(
        self,
        samples: List[Dict[str, Any]],
        *,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """
        Each sample: `{"features": {...}, "fitness": float}`. Fitness is
        what the real decoder returned (lower is better in CPO).
        """
        if len(samples) < 20:
            raise ValueError(
                f"SurrogateModel needs >=20 samples; got {len(samples)}"
            )

        X = np.asarray(
            [[s["features"].get(k, 0.0) for k in FEATURE_ORDER] for s in samples],
            dtype=np.float64,
        )
        y = np.asarray([float(s["fitness"]) for s in samples], dtype=np.float64)

        # Hold out 20% for WMAPE
        split = max(4, int(len(samples) * 0.2))
        idx = np.arange(len(samples))
        rng = np.random.default_rng(random_state)
        rng.shuffle(idx)
        val_idx, train_idx = idx[:split], idx[split:]

        # FASE 4.3 — hyperparams from MLConfig (env-overridable).
        from src.ml.config import get_config
        hp = get_config().hyperparams_for("surrogate")
        model = RandomForestRegressor(
            n_estimators=int(hp.get("n_estimators", 120)),
            max_depth=int(hp.get("max_depth", 8)),
            min_samples_leaf=int(hp.get("min_samples_leaf", 3)),
            random_state=random_state,
            n_jobs=1,  # stable determinism in tests
        )
        model.fit(X[train_idx], y[train_idx])
        self.regressor = model
        self.n_samples_trained = len(samples)
        self.best_known_fitness = float(y.min())

        y_pred = model.predict(X[val_idx])
        err = wmape(y[val_idx], y_pred)
        metrics = {
            "wmape": round(err, 4),
            "samples": len(samples),
            "samples_train": len(train_idx),
            "samples_val": len(val_idx),
            "best_known_fitness": self.best_known_fitness,
        }
        logger.info(
            f"SurrogateModel trained: WMAPE={metrics['wmape']}, samples={metrics['samples']}"
        )
        return metrics

    def predict(self, features: Dict[str, Any]) -> float:
        if self.regressor is None:
            raise RuntimeError("SurrogateModel.predict called before train()")
        X = np.asarray(
            [[features.get(k, 0.0) for k in FEATURE_ORDER]], dtype=np.float64
        )
        return float(self.regressor.predict(X)[0])

    def should_skip_candidate(
        self,
        features: Dict[str, Any],
        threshold_factor: float = 1.2,
    ) -> bool:
        """
        True if predicted fitness is `threshold_factor`x worse than the best
        known candidate so far. GA uses this to skip expensive real decode
        calls for candidates that almost certainly won't improve the elite.
        """
        if self.regressor is None or math.isinf(self.best_known_fitness):
            return False
        predicted = self.predict(features)
        # In CPO lower fitness is better. "Worse" = larger.
        return predicted > self.best_known_fitness * threshold_factor


# ---------------------------------------------------------------------------
# Feature extraction helper
# ---------------------------------------------------------------------------

def extract_surrogate_features(
    chromosome: Any,
    *,
    n_ops: int,
    n_orders: int,
    avg_duration_min: float,
) -> Dict[str, float]:
    """
    Build the surrogate's input dict from a CPO chromosome + scheduler
    aggregates. The CPO GA calls this right before the expensive decode.
    """
    permutation = getattr(chromosome, "permutation", None) or []
    entropy = _permutation_entropy(permutation)
    return {
        "n_ops": float(n_ops),
        "n_orders": float(n_orders),
        "edd_gap": float(getattr(chromosome, "edd_gap", 0) or 0),
        "buffer_pct": float(getattr(chromosome, "buffer_pct", 0.0) or 0.0),
        "quality_weight": float(getattr(chromosome, "quality_weight", 0.0) or 0.0),
        "avg_duration_min": float(avg_duration_min),
        "permutation_entropy": float(entropy),
    }


def _permutation_entropy(permutation: Sequence[int]) -> float:
    """
    Shannon entropy of pairwise-ordering patterns (length-3 windows).
    Cheap heuristic: picks up whether a permutation is highly sorted vs.
    shuffled, which correlates with GA exploration stage.
    """
    if len(permutation) < 3:
        return 0.0
    patterns: Counter = Counter()
    for i in range(len(permutation) - 2):
        window = permutation[i : i + 3]
        signature = tuple(
            1 if window[a] < window[b] else 0
            for a in range(3) for b in range(a + 1, 3)
        )
        patterns[signature] += 1
    total = sum(patterns.values())
    if total == 0:
        return 0.0
    return -sum(
        (c / total) * math.log(c / total, 2)
        for c in patterns.values() if c > 0
    )


# ---------------------------------------------------------------------------
# RetrainJob
# ---------------------------------------------------------------------------

class SurrogateRetrainJob(RetrainJob):
    """
    Event-driven retrain: the CPO GA (Sprint F) calls this after every 50
    fresh real evaluations. The cron stays empty — APScheduler does NOT
    register this job automatically.
    """

    model_name = "surrogate"
    schedule_cron = ""  # not on cron

    def __init__(self, sample_provider: Any = None):
        self.sample_provider = sample_provider

    def extract_features(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        if self.sample_provider is None:
            return []
        if callable(self.sample_provider):
            return list(self.sample_provider())
        return list(self.sample_provider)

    def train(self, features: List[Dict[str, Any]]) -> Tuple[SurrogateModel, int]:
        model = SurrogateModel()
        metrics = model.train(features)
        return model, int(metrics["samples"])

    def validate(
        self,
        model: SurrogateModel,
        features: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "wmape": float(_estimate_wmape(model, features)),
            "samples": model.n_samples_trained,
            "best_known_fitness": model.best_known_fitness,
        }


def _estimate_wmape(model: SurrogateModel, samples: List[Dict[str, Any]]) -> float:
    """Quick sanity WMAPE on a sample of samples (yes, really)."""
    if not samples or model.regressor is None:
        return 0.0
    subset = samples[: min(50, len(samples))]
    preds = [model.predict(s["features"]) for s in subset]
    actuals = [float(s["fitness"]) for s in subset]
    return round(wmape(actuals, preds), 4)
