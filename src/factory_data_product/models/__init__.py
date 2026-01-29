"""
Factory Data Product Models
===========================

Database models for:
- META: ingestion_run, active_run, quality_check_result
- RAW: excel_row (append-only)
- CURATED: order, order_phase, mold, skill_matrix, etc.
"""

from src.factory_data_product.models.meta import (
    IngestionRun,
    IngestionStatus,
    QualityGateStatus,
    SourceType,
    ActiveRun,
    QualityCheckResult,
    CheckSeverity,
)
from src.factory_data_product.models.raw import (
    ExcelRow,
)
from src.factory_data_product.models.curated import (
    CuratedOrder,
    CuratedOrderPhase,
    CuratedPhaseCapacity,
    CuratedMold,
    CuratedMoldUsage,
    CuratedQualityEvent,
    CuratedSkillMatrix,
    CuratedCostReference,
)

__all__ = [
    # Meta
    "IngestionRun",
    "IngestionStatus",
    "QualityGateStatus",
    "SourceType",
    "ActiveRun",
    "QualityCheckResult",
    "CheckSeverity",
    # Raw
    "ExcelRow",
    # Curated
    "CuratedOrder",
    "CuratedOrderPhase",
    "CuratedPhaseCapacity",
    "CuratedMold",
    "CuratedMoldUsage",
    "CuratedQualityEvent",
    "CuratedSkillMatrix",
    "CuratedCostReference",
]


