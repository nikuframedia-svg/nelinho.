"""
ProdPlan ONE — ML Configuration
================================

Centralised config for the ML subsystem.

Env vars:
- `PRODPLAN_ML_ARTIFACT_DIR` (default: `./ml_artifacts`) — local storage
  root. The ModelRegistry uses `<root>/<model_name>/<version>/model.joblib`.
- `PRODPLAN_ML_AUTO_PROMOTE_MAX_WMAPE_DELTA` (default: `0.05`) — auto
  approve a `model_promotion` decision when the new model's WMAPE improvement
  is positive and below this threshold. Anything outside requires human review.
- `PRODPLAN_ML_HYPERPARAMS_JSON` — JSON-encoded dict of per-model
  hyperparameters (FASE 4.3, auditoria HIGH note). Schema:

      {
        "duration":     {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.08},
        "quality_risk": {"n_estimators": 120, "max_depth": 3, "learning_rate": 0.10},
        "surrogate":    {"n_estimators": 120, "max_depth": 8, "min_samples_leaf": 3}
      }

  Unknown keys are ignored; missing keys fall back to the
  ``DEFAULT_HYPERPARAMS`` baked into this module so that legacy code
  paths keep working unchanged. Override per-tenant in production by
  exporting the env var on the worker that runs the retrain jobs.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


DEFAULT_ARTIFACT_DIR_ENV = "PRODPLAN_ML_ARTIFACT_DIR"
DEFAULT_ARTIFACT_DIR = "./ml_artifacts"

DEFAULT_AUTO_PROMOTE_ENV = "PRODPLAN_ML_AUTO_PROMOTE_MAX_WMAPE_DELTA"
DEFAULT_AUTO_PROMOTE_MAX_DELTA = 0.05

DEFAULT_HYPERPARAMS_ENV = "PRODPLAN_ML_HYPERPARAMS_JSON"

# Legacy values from src/ml/models_domain/{duration,quality_risk,surrogate}.py
# kept here verbatim so swapping to config-driven hyperparams is a no-op
# until someone explicitly tunes the env var.
DEFAULT_HYPERPARAMS: Dict[str, Dict[str, Any]] = {
    "duration": {
        "n_estimators": 100,
        "max_depth": 4,
        "learning_rate": 0.08,
    },
    "quality_risk": {
        "n_estimators": 120,
        "max_depth": 3,
        "learning_rate": 0.10,
    },
    "surrogate": {
        "n_estimators": 120,
        "max_depth": 8,
        "min_samples_leaf": 3,
    },
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MLConfig:
    artifact_dir: Path
    auto_promote_max_wmape_delta: float
    hyperparams: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_HYPERPARAMS.items()}
    )

    def hyperparams_for(self, model_name: str) -> Dict[str, Any]:
        """Return hyperparams for ``model_name`` merged over the defaults.

        Missing keys fall back to ``DEFAULT_HYPERPARAMS[model_name]`` so
        a partial env override still ships every tunable. Unknown
        ``model_name`` returns an empty dict (caller stays with its
        own hardcoded defaults).
        """
        defaults = DEFAULT_HYPERPARAMS.get(model_name, {})
        merged = {**defaults, **self.hyperparams.get(model_name, {})}
        return merged

    @classmethod
    def from_env(cls) -> "MLConfig":
        root = Path(os.environ.get(DEFAULT_ARTIFACT_DIR_ENV, DEFAULT_ARTIFACT_DIR))
        try:
            delta = float(os.environ.get(DEFAULT_AUTO_PROMOTE_ENV, DEFAULT_AUTO_PROMOTE_MAX_DELTA))
        except (TypeError, ValueError):
            delta = DEFAULT_AUTO_PROMOTE_MAX_DELTA

        hyperparams = {k: dict(v) for k, v in DEFAULT_HYPERPARAMS.items()}
        raw = os.environ.get(DEFAULT_HYPERPARAMS_ENV)
        if raw:
            try:
                override = json.loads(raw)
                if isinstance(override, dict):
                    for model_name, params in override.items():
                        if not isinstance(params, dict):
                            continue
                        hyperparams.setdefault(model_name, {}).update(params)
                else:
                    logger.warning(
                        "%s parsed but not a dict — ignoring override.",
                        DEFAULT_HYPERPARAMS_ENV,
                    )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.warning(
                    "%s could not be parsed (%s) — using defaults.",
                    DEFAULT_HYPERPARAMS_ENV, exc,
                )

        return cls(
            artifact_dir=root,
            auto_promote_max_wmape_delta=delta,
            hyperparams=hyperparams,
        )


def get_config() -> MLConfig:
    return MLConfig.from_env()
