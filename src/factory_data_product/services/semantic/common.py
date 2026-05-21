"""Shared helpers for the in-memory semantic queries service (Q.67.6.C5).

Holds the cross-cutting concerns that every query needs:
- Active-curated lookup against the IngestEngine.
- Trust status thresholds.
- Confidence scoring formula.
- Canonical "no data" response shape.

These are split into a mixin so the public class assembled in
`__init__.py` can compose them with the per-domain query modules without
re-implementing the helpers in each one.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...ingest.engine import IngestEngine

logger = logging.getLogger(__name__)


class _SemanticCommonMixin:
    """Helpers shared across every public query.

    Subclasses are expected to provide ``self.engine`` (an IngestEngine).
    """

    engine: "IngestEngine"

    def _get_active_curated(self) -> Optional[Dict[str, List[Dict]]]:
        """Get curated data for the active ingestion, or None."""
        active = self.engine.get_active_run()
        if not active:
            logger.warning("No active ingestion run")
            return None

        ingestion_id = str(active["active_ingestion_id"])
        data = self.engine._curated_data.get(ingestion_id)

        if not data:
            logger.warning(f"No curated data for ingestion {ingestion_id}")
            return None

        logger.info(f"Retrieved curated data for ingestion {ingestion_id}")
        return data

    def _get_trust_status(self, confidence: float) -> str:
        """Map a confidence score (0-100) to OK / WARNING / BLOCKED."""
        if confidence >= 85:
            return "OK"
        elif confidence >= 50:
            return "WARNING"
        else:
            return "BLOCKED"

    def _calculate_confidence(
        self,
        base_trust: int,
        coverage_pct: float,
        sample_size: int,
        min_sample: int = 10,
    ) -> float:
        """Confidence = base_trust × coverage_factor × sample_factor."""
        coverage_factor = min(1.0, coverage_pct / 100)

        if sample_size < min_sample:
            sample_factor = sample_size / min_sample
        else:
            sample_factor = 1.0

        confidence = base_trust * coverage_factor * sample_factor
        return round(confidence, 1)

    def _empty_response(self, query_type: str, message: str) -> Dict[str, Any]:
        """Canonical "no data" shape served by any query that can't proceed."""
        return {
            "data": None,
            "data_confidence": 0,
            "trust_status": "BLOCKED",
            "semantic_label": message,
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "source": "no_active_ingestion",
                "error": message,
            },
        }
