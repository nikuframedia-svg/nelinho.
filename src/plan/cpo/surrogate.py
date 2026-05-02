"""
ProdPlan ONE — CPO Surrogate Adapter (Sprint F.3)
==================================================

Thin wrapper around `src.ml.models_domain.surrogate.SurrogateModel` (built
in Sprint H) tailored for the CPO GA loop:

- Collects (features, fitness) samples **inline** during a schedule() run.
- Retrains every `retrain_every` real evaluations (default 50).
- Exposes `should_skip_candidate(chromo, context, threshold_factor=1.2)`
  so the GA can skip expensive real decode calls when the surrogate
  predicts a candidate is clearly worse than the best known.
- Persists the trained artifact via `ModelRegistry` **only when the
  session is available** — during a single schedule() call the surrogate
  lives in memory (the persistence hook is exposed for Sprint I).

The GA calls:
    surrogate = CPOSurrogateLayer(enabled=True)
    ...
    for chromo in population:
        ctx = {"n_ops": n_ops, "n_orders": n_orders, "avg_duration_min": avg_d}
        if surrogate.should_skip_candidate(chromo, ctx):
            continue
        schedule = decoder.decode(chromo, ...)
        fit = compute_fitness(schedule)
        surrogate.record(chromo, ctx, fit)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.ml.models_domain.surrogate import (
    SurrogateModel,
    extract_surrogate_features,
)
from src.plan.cpo.chromosome import Chromosome

logger = logging.getLogger(__name__)


DEFAULT_RETRAIN_EVERY = 50
DEFAULT_MIN_SAMPLES_TO_TRAIN = 20
DEFAULT_THRESHOLD_FACTOR = 1.2


@dataclass
class CPOSurrogateLayer:
    """
    Accumulates samples during a GA run, retrains a `SurrogateModel`
    when the sample count crosses the retrain threshold, and exposes
    a skip-candidate test for GA filtering.

    Defaults keep the layer completely off (`enabled=False`) so Sprint E
    tests and bench runs that pre-date the surrogate don't pay for it.
    """

    enabled: bool = False
    retrain_every: int = DEFAULT_RETRAIN_EVERY
    min_samples_to_train: int = DEFAULT_MIN_SAMPLES_TO_TRAIN
    threshold_factor: float = DEFAULT_THRESHOLD_FACTOR

    _samples: List[Dict[str, Any]] = field(default_factory=list)
    _samples_since_last_train: int = 0
    _model: Optional[SurrogateModel] = None
    _last_metrics: Dict[str, Any] = field(default_factory=dict)
    _skips_attempted: int = 0
    _skips_applied: int = 0

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    @property
    def is_trained(self) -> bool:
        return self._model is not None and self._model.regressor is not None

    def record(
        self,
        chromosome: Chromosome,
        context: Dict[str, Any],
        fitness: float,
    ) -> None:
        """Store one (features, fitness) sample and retrain if due."""
        if not self.enabled:
            return
        features = extract_surrogate_features(
            chromosome,
            n_ops=int(context.get("n_ops", 0) or 0),
            n_orders=int(context.get("n_orders", 0) or 0),
            avg_duration_min=float(context.get("avg_duration_min", 0.0) or 0.0),
        )
        self._samples.append({"features": features, "fitness": float(fitness)})
        self._samples_since_last_train += 1
        if (
            self._samples_since_last_train >= self.retrain_every
            and len(self._samples) >= self.min_samples_to_train
        ):
            self._retrain()

    def should_skip_candidate(
        self,
        chromosome: Chromosome,
        context: Dict[str, Any],
    ) -> bool:
        """
        True if the surrogate predicts this candidate is clearly worse
        than the best known by more than `threshold_factor`x.
        Always False when disabled or untrained.
        """
        if not self.enabled or not self.is_trained:
            return False
        self._skips_attempted += 1
        features = extract_surrogate_features(
            chromosome,
            n_ops=int(context.get("n_ops", 0) or 0),
            n_orders=int(context.get("n_orders", 0) or 0),
            avg_duration_min=float(context.get("avg_duration_min", 0.0) or 0.0),
        )
        # FASE 6.1 (HIGH-13) — assert was stripped under `python -O`,
        # which would have crashed the GA when surrogate skipped a
        # candidate after `is_trained` evaluated True but `_model`
        # was somehow reset. Convert to a runtime guard.
        if self._model is None:  # pragma: no cover — defensive (is_trained checked above)
            raise RuntimeError(
                "CPOSurrogateLayer.should_skip_candidate: _model is None "
                "despite is_trained=True — internal state corruption."
            )
        skip = self._model.should_skip_candidate(
            features, threshold_factor=self.threshold_factor
        )
        if skip:
            self._skips_applied += 1
        return skip

    def snapshot(self) -> Dict[str, Any]:
        """Observability: ops telemetry for the CPO engine to expose."""
        return {
            "enabled": self.enabled,
            "samples": len(self._samples),
            "samples_since_last_train": self._samples_since_last_train,
            "trained": self.is_trained,
            "best_known_fitness": (
                self._model.best_known_fitness if self.is_trained else None
            ),
            "last_metrics": dict(self._last_metrics),
            "skips_attempted": self._skips_attempted,
            "skips_applied": self._skips_applied,
        }

    def reset(self) -> None:
        """Drop all state — used by tests and between runs if desired."""
        self._samples.clear()
        self._samples_since_last_train = 0
        self._model = None
        self._last_metrics = {}
        self._skips_attempted = 0
        self._skips_applied = 0

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    def _retrain(self) -> None:
        try:
            model = self._model or SurrogateModel()
            metrics = model.train(self._samples)
            self._model = model
            self._last_metrics = metrics
            self._samples_since_last_train = 0
            logger.info(
                f"CPO surrogate retrained: samples={metrics.get('samples')} "
                f"WMAPE={metrics.get('wmape')}"
            )
        except Exception as e:
            # Never let a surrogate glitch sink the GA — log and continue.
            logger.warning(f"CPO surrogate retrain failed: {e}")
            self._samples_since_last_train = 0
