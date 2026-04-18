"""
ProdPlan ONE — Feature Extractors
==================================

Abstract `FeatureExtractor` plus 4 concrete stubs aligned with the Sprint H
models (QualityRisk/Duration use these). Each extractor consumes the curated
layer via `SemanticQueriesInMemory` (never the raw Excel) and returns a
flat `Dict[str, float|str]`.

Sprint G delivers the interface + one-shot derivations from curated data.
Sprint H plugs these into `RetrainJob` subclasses and trains real models.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


FeatureDict = Dict[str, Any]


class FeatureExtractor(ABC):
    """
    Abstract base. Subclasses implement `extract(entity, context) -> FeatureDict`.

    `entity` is the object under analysis (order dict, phase row, worker id,
    mold id). `context` carries shared resources — typically a
    `SemanticQueriesInMemory` instance + tenant_id + active_ingestion_id —
    so extractors don't each re-query for common aggregates.
    """

    #: Stable name for Prometheus labels and feature-schema hashing.
    name: str = "base"

    def __init__(self, tenant_id: UUID, semantic_queries: Any = None) -> None:
        self.tenant_id = tenant_id
        self.semantic = semantic_queries

    @abstractmethod
    def extract(
        self,
        entity: Any,
        context: Optional[FeatureDict] = None,
    ) -> FeatureDict:
        ...

    # ------------------------------------------------------------------ #
    # Helpers shared across subclasses                                   #
    # ------------------------------------------------------------------ #

    def _curated(self, key: str) -> Any:
        """Fetch a bucket from the semantic engine's curated_data (best effort)."""
        if self.semantic is None:
            return []
        engine = getattr(self.semantic, "engine", None)
        if engine is None:
            return []
        active = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active, {}) if active else {}
        return scope.get(key, [])


# ----------------------------------------------------------------------
# Concrete extractors (Sprint G: lightweight; Sprint H extends)
# ----------------------------------------------------------------------

class OrderFeatures(FeatureExtractor):
    name = "order"

    def extract(self, entity: Dict[str, Any], context: Optional[FeatureDict] = None) -> FeatureDict:
        order = entity
        return {
            "of_id": str(order.get("of_id", "")),
            "modelo_id": str(order.get("modelo_id", "")),
            "quantidade": _safe_float(order.get("quantidade")),
            "has_due_date": order.get("data_entrega_prevista") is not None,
        }


class PhaseFeatures(FeatureExtractor):
    """Features for a single (order, phase) execution."""

    name = "phase"

    def extract(self, entity: Dict[str, Any], context: Optional[FeatureDict] = None) -> FeatureDict:
        """
        `entity` expects keys: of_id, fase_id, modelo_id.
        Emits features that the QualityRisk and Duration models will consume.
        """
        of_id = str(entity.get("of_id", ""))
        fase_id = str(entity.get("fase_id", ""))
        modelo_id = str(entity.get("modelo_id", ""))

        # Historical error rate for this phase (from CuratedQualityEvent)
        errors = self._curated("quality_events") or self._curated("CuratedQualityEvent") or []
        error_count = sum(
            1 for e in errors if str(getattr(e, "fase_id", "") or "") == fase_id
        )
        phase_rows = self._curated("order_phases") or self._curated("CuratedOrderPhase") or []
        phase_count = sum(
            1 for p in phase_rows if str(getattr(p, "fase_id", "") or "") == fase_id
        )
        error_rate = (error_count / phase_count) if phase_count else 0.0

        # Median historical duration (from state-style aggregation)
        durations = [
            float(getattr(p, "horas_reais", 0) or getattr(p, "horas_finais", 0) or 0)
            for p in phase_rows
            if str(getattr(p, "fase_id", "") or "") == fase_id
            and str(getattr(p, "modelo_id", "") or modelo_id) == modelo_id
        ]
        durations = [d for d in durations if d > 0]
        median_duration = _median(durations) if durations else None

        # is_rework — proxy: any error flagged on this phase for this order
        is_rework = any(
            str(getattr(e, "of_id", "") or "") == of_id
            and str(getattr(e, "fase_id", "") or "") == fase_id
            for e in errors
        )

        return {
            "fase_id": fase_id,
            "modelo_id": modelo_id,
            "historical_error_rate": round(error_rate, 4),
            "median_duration_h": median_duration,
            "is_rework": is_rework,
            "queue_depth_proxy": phase_count,
        }


class WorkerFeatures(FeatureExtractor):
    name = "worker"

    def extract(self, entity: Any, context: Optional[FeatureDict] = None) -> FeatureDict:
        funcionario_id = str(entity)
        skill_rows = self._curated("skill_matrix") or self._curated("CuratedSkillMatrix") or []
        fases_capable = {
            str(getattr(s, "fase_id", "") or "")
            for s in skill_rows
            if str(getattr(s, "funcionario_id", "") or "") == funcionario_id
            and getattr(s, "apto", True)
        }
        return {
            "funcionario_id": funcionario_id,
            "n_fases_aptos": len(fases_capable),
        }


class MoldFeatures(FeatureExtractor):
    name = "mold"

    def extract(self, entity: Any, context: Optional[FeatureDict] = None) -> FeatureDict:
        molde_id = str(entity)
        molds = self._curated("molds") or self._curated("CuratedMold") or []
        uses = self._curated("mold_usage") or self._curated("CuratedMoldUsage") or []

        info = next(
            (m for m in molds if str(getattr(m, "molde_id", "") or "") == molde_id),
            None,
        )
        n_uses = sum(
            1 for u in uses if str(getattr(u, "molde_id", "") or "") == molde_id
        )
        return {
            "molde_id": molde_id,
            "modelo_id": str(getattr(info, "modelo_id", "") or "") if info else "",
            "pocket_count": int(getattr(info, "pocket_count", 1) or 1) if info else 1,
            "em_manutencao": bool(getattr(info, "em_manutencao", False)) if info else False,
            "uses_total": n_uses,
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _median(values):
    from statistics import median
    return float(median(values))
