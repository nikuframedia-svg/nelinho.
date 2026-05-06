"""
ProdPlan ONE - OFCH_GRAVIDADE → severity mapping
=================================================

Onda 3.4 — extracted from the now-deleted `curated_transformer.py`. The
NELO ERP records error gravity as integer 1/2/3:
  1 (~84.1% of rows)  — operator-flagged issue, peça still progresses
  2 (~14.0%)          — moderate defect, rework required
  3 (~1.8%)           — critical defect (assumed; pending second-round
                        CEO confirmation, see Sprint Q.8b follow-up A)

CEO confirmed (2026-04-26) all three count as defects ("é um defeito")
for the `quality_risk_score` calculation. The numeric label is preserved
elsewhere as `gravidade_raw` so the UI can still surface granularity.

Used by:
  - `factory_data_product.ingest.transformer._transform_quality_events`
  - `dqa.models.DataQualityIssue.severity` (default value rationale)
  - `quality.models.rework.ReworkEntry.severity` (cross-reference)
"""

from typing import Any, Dict


GRAVIDADE_TO_SEVERITY: Dict[int, str] = {
    1: "low",
    2: "medium",
    3: "high",
}


def map_gravidade_to_severity(gravidade: Any) -> str:
    """Map OFCH_GRAVIDADE → severity string ('low'/'medium'/'high').

    Unknown / missing values default to 'medium' to avoid silently
    discarding records.
    """
    try:
        g = int(gravidade)
    except (TypeError, ValueError):
        return "medium"
    return GRAVIDADE_TO_SEVERITY.get(g, "medium")
