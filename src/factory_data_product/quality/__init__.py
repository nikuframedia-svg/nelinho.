"""
Quality Gates & Scoring — Contrato 010
======================================

Quality checks for ingestion validation and Trust Index scoring.

Blocking checks:
- required_sheets_present
- required_columns_present
- no_duplicate_business_keys
- valid_numeric_ranges
- referential_integrity_order_phase
- date_parseable_where_required
- pii_policy_enforced

Quality Scoring:
- Trust Index per segment
- Data confidence scoring
- Quality report generation with recommendations
"""

from src.factory_data_product.quality.gates import (
    QualityCheck,
    CheckResult,
    QUALITY_CHECKS,
)
from src.factory_data_product.quality.runner import (
    QualityRunner,
    QualityResult,
)

# Onda 5.1 — `QualityScorer` (scorer.py) was deleted as dead code: it
# was exported here but no consumer imported it. The trust-heatmap
# endpoint uses `TrustHeatmapGenerator` from `trust_heatmap.py` instead.

__all__ = [
    "QualityCheck",
    "CheckResult",
    "QUALITY_CHECKS",
    "QualityRunner",
    "QualityResult",
]


