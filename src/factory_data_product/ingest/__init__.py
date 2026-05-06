"""
Factory Data Product — Ingest Engine
====================================

Core ingestion functionality:
- Excel parsing
- SHA256 hashing
- RAW → CURATED transformation
- HorasPrevistas_Final derivation
- Schema Drift Detection (P2)
"""

from src.factory_data_product.ingest.engine import IngestEngine, IngestResult
from src.factory_data_product.ingest.parser import ExcelParser
from src.factory_data_product.ingest.hasher import FileHasher, RowHasher
from src.factory_data_product.ingest.transformer import RawToCuratedTransformer
from src.factory_data_product.ingest.gravidade import (
    GRAVIDADE_TO_SEVERITY,
    map_gravidade_to_severity,
)
from src.factory_data_product.ingest.drift_detector import (
    SchemaDriftDetector,
    DriftReport,
    DriftItem,
    DriftType,
    DriftSeverity,
    DriftBlockingError,
    get_drift_detector,
)

# Onda 3.4 — `CuratedTransformer` (curated_transformer.py) was deleted as
# dead code: the module shipped 487 lines of an alternative transform
# pipeline that was never wired into the engine. Its only durable export,
# the OFCH_GRAVIDADE mapping, now lives in `gravidade.py`.

__all__ = [
    "IngestEngine",
    "IngestResult",
    "ExcelParser",
    "FileHasher",
    "RowHasher",
    "RawToCuratedTransformer",
    # Gravidade utility (formerly inside the deleted curated_transformer)
    "GRAVIDADE_TO_SEVERITY",
    "map_gravidade_to_severity",
    # Drift Detection
    "SchemaDriftDetector",
    "DriftReport",
    "DriftItem",
    "DriftType",
    "DriftSeverity",
    "DriftBlockingError",
    "get_drift_detector",
]


