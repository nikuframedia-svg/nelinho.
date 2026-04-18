"""
ProdPlan ONE — ML Artifact Storage (Local Filesystem MVP)
==========================================================

Thin wrapper around `joblib.dump`/`joblib.load` rooted at a configurable
filesystem directory. Returns and consumes plain `storage_uri` strings so
the registry can later swap to S3/GCS without changing callers.

URI format: `file://<abs_path>/<model_name>/<version>/model.joblib`
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import joblib

from src.ml.config import MLConfig, get_config

logger = logging.getLogger(__name__)


FILE_SCHEME = "file://"


class ArtifactStorage:
    """File-backed storage for trained model objects."""

    def __init__(self, config: MLConfig = None) -> None:
        self.config = config or get_config()
        self.config.artifact_dir.mkdir(parents=True, exist_ok=True)

    def save(self, model: Any, model_name: str, version: int) -> str:
        """
        Persist `model` and return a `storage_uri` string.

        Caller is responsible for storing the URI in the DB alongside
        metadata (version, metrics, tenant).
        """
        target = self._path_for(model_name, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, target)
        uri = f"{FILE_SCHEME}{target.as_posix()}"
        logger.info(f"Saved model '{model_name}' v{version} to {uri}")
        return uri

    def load(self, storage_uri: str) -> Any:
        path = self._resolve(storage_uri)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact missing at {path}")
        return joblib.load(path)

    def delete(self, storage_uri: str) -> bool:
        path = self._resolve(storage_uri)
        if not path.exists():
            return False
        path.unlink()
        logger.info(f"Deleted model artifact at {path}")
        return True

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    def _path_for(self, model_name: str, version: int) -> Path:
        safe_name = model_name.replace("/", "_").replace("..", "_")
        return self.config.artifact_dir / safe_name / f"v{version}" / "model.joblib"

    def _resolve(self, storage_uri: str) -> Path:
        if storage_uri.startswith(FILE_SCHEME):
            parsed = urlparse(storage_uri)
            # urlparse keeps drive letters like 'c:' in `netloc` on Windows
            path_str = parsed.netloc + parsed.path if parsed.netloc else parsed.path
            return Path(path_str)
        return Path(storage_uri)
