"""
ProdPlan ONE — ML Configuration
================================

Centralised config for the ML subsystem. Kept deliberately small — most
knobs belong on the model class or the retrain job itself.

Env vars:
- `PRODPLAN_ML_ARTIFACT_DIR` (default: `./ml_artifacts`) — local storage
  root. The ModelRegistry uses `<root>/<model_name>/<version>/model.joblib`.
- `PRODPLAN_ML_AUTO_PROMOTE_MAX_WMAPE_DELTA` (default: `0.05`) — auto
  approve a `model_promotion` decision when the new model's WMAPE improvement
  is positive and below this threshold. Anything outside requires human review.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ARTIFACT_DIR_ENV = "PRODPLAN_ML_ARTIFACT_DIR"
DEFAULT_ARTIFACT_DIR = "./ml_artifacts"

DEFAULT_AUTO_PROMOTE_ENV = "PRODPLAN_ML_AUTO_PROMOTE_MAX_WMAPE_DELTA"
DEFAULT_AUTO_PROMOTE_MAX_DELTA = 0.05


@dataclass(frozen=True)
class MLConfig:
    artifact_dir: Path
    auto_promote_max_wmape_delta: float

    @classmethod
    def from_env(cls) -> "MLConfig":
        root = Path(os.environ.get(DEFAULT_ARTIFACT_DIR_ENV, DEFAULT_ARTIFACT_DIR))
        try:
            delta = float(os.environ.get(DEFAULT_AUTO_PROMOTE_ENV, DEFAULT_AUTO_PROMOTE_MAX_DELTA))
        except (TypeError, ValueError):
            delta = DEFAULT_AUTO_PROMOTE_MAX_DELTA
        return cls(artifact_dir=root, auto_promote_max_wmape_delta=delta)


def get_config() -> MLConfig:
    return MLConfig.from_env()
