"""
ProdPlan ONE — Feature Extractor Registry
==========================================

Maps `extractor_name → class` so jobs can discover extractors by name
(e.g. `"order"`, `"phase"`, `"worker"`, `"mold"`) without hard imports.
"""

from __future__ import annotations

from typing import Dict, Type

from src.ml.feature_engineering.extractors import (
    FeatureExtractor,
    MoldFeatures,
    OrderFeatures,
    PhaseFeatures,
    WorkerFeatures,
)


_EXTRACTORS: Dict[str, Type[FeatureExtractor]] = {
    OrderFeatures.name: OrderFeatures,
    PhaseFeatures.name: PhaseFeatures,
    WorkerFeatures.name: WorkerFeatures,
    MoldFeatures.name: MoldFeatures,
}


def get_extractor_cls(name: str) -> Type[FeatureExtractor]:
    if name not in _EXTRACTORS:
        raise KeyError(
            f"Unknown feature extractor '{name}'. Available: {list(_EXTRACTORS)}"
        )
    return _EXTRACTORS[name]


def list_extractors() -> Dict[str, Type[FeatureExtractor]]:
    return dict(_EXTRACTORS)


def register_extractor(cls: Type[FeatureExtractor]) -> None:
    """Allow Sprint H / user code to add extractors."""
    _EXTRACTORS[cls.name] = cls
