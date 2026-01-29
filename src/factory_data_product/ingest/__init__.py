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
from src.factory_data_product.ingest.curated_transformer import CuratedTransformer
from src.factory_data_product.ingest.drift_detector import (
    SchemaDriftDetector,
    DriftReport,
    DriftItem,
    DriftType,
    DriftSeverity,
    DriftBlockingError,
    get_drift_detector,
)

__all__ = [
    "IngestEngine",
    "IngestResult",
    "ExcelParser",
    "FileHasher",
    "RowHasher",
    "RawToCuratedTransformer",
    "CuratedTransformer",
    # Drift Detection
    "SchemaDriftDetector",
    "DriftReport",
    "DriftItem",
    "DriftType",
    "DriftSeverity",
    "DriftBlockingError",
    "get_drift_detector",
]


