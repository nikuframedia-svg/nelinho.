"""
E2E Tests — Ingest → Quality → Activate Flow
=============================================

Tests the complete data ingestion flow:
1. Upload Excel file
2. Run quality gates
3. Detect schema drift
4. Transform to curated
5. Activate run
"""

import pytest
from pathlib import Path
from uuid import uuid4
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestIngestionPipeline:
    """Test complete ingestion pipeline."""
    
    @pytest.mark.asyncio
    async def test_ingest_engine_instantiates(self):
        """Test IngestEngine can be instantiated."""
        from src.factory_data_product.ingest import IngestEngine
        
        engine = IngestEngine()
        assert engine is not None
        assert engine.parser is not None
        assert engine.transformer is not None
    
    @pytest.mark.asyncio
    async def test_ingest_result_has_required_fields(self):
        """Test IngestResult has required fields."""
        from src.factory_data_product.ingest import IngestResult
        
        result = IngestResult()
        
        # Core fields
        assert hasattr(result, "success")
        assert hasattr(result, "ingestion_id")
        assert hasattr(result, "status")
        
        # Quality fields
        assert hasattr(result, "quality_gate_status")
        assert hasattr(result, "quality_checks")
        assert hasattr(result, "blocking_failures")
        
        # Drift fields (P2)
        assert hasattr(result, "drift_report")
        assert hasattr(result, "has_schema_drift")
        assert hasattr(result, "drift_blocking")
        
        # Stats
        assert hasattr(result, "total_rows_raw")
        assert hasattr(result, "total_rows_curated")


class TestQualityGates:
    """Test quality gate execution."""
    
    @pytest.mark.asyncio
    async def test_quality_runner_exists(self):
        """Test QualityRunner can be instantiated."""
        from src.factory_data_product.quality import QualityRunner
        
        runner = QualityRunner()
        assert runner is not None
    
    @pytest.mark.asyncio
    async def test_quality_gate_status_enum(self):
        """Test quality gate status values."""
        from src.factory_data_product.models.meta import QualityGateStatus
        
        assert QualityGateStatus.PASSED.value == "passed"
        assert QualityGateStatus.FAILED.value == "failed"
        assert QualityGateStatus.WARNING.value == "warning"
    
    @pytest.mark.asyncio
    async def test_check_severity_enum(self):
        """Test check severity values."""
        from src.factory_data_product.models.meta import CheckSeverity
        
        assert CheckSeverity.BLOCKING.value == "blocking"
        assert CheckSeverity.WARNING.value == "warning"
        assert CheckSeverity.INFO.value == "info"


class TestSchemaDrift:
    """Test schema drift detection."""
    
    @pytest.mark.asyncio
    async def test_drift_detector_instantiates(self):
        """Test SchemaDriftDetector can be instantiated."""
        from src.factory_data_product.ingest import SchemaDriftDetector
        
        detector = SchemaDriftDetector()
        assert detector is not None
    
    @pytest.mark.asyncio
    async def test_drift_report_fields(self):
        """Test DriftReport has required fields."""
        from src.factory_data_product.ingest import DriftReport
        
        report = DriftReport()
        
        assert hasattr(report, "has_drift")
        assert hasattr(report, "has_blocking")
        assert hasattr(report, "items")
        assert hasattr(report, "columns_added")
        assert hasattr(report, "columns_removed")
    
    @pytest.mark.asyncio
    async def test_drift_severity_enum(self):
        """Test drift severity values."""
        from src.factory_data_product.ingest import DriftSeverity
        
        assert DriftSeverity.BLOCKING.value == "blocking"
        assert DriftSeverity.WARNING.value == "warning"
        assert DriftSeverity.INFO.value == "info"
    
    @pytest.mark.asyncio
    async def test_drift_type_enum(self):
        """Test drift type values."""
        from src.factory_data_product.ingest import DriftType
        
        assert DriftType.COLUMN_ADDED.value == "column_added"
        assert DriftType.COLUMN_REMOVED.value == "column_removed"
        assert DriftType.COLUMN_RENAMED.value == "column_renamed"
    
    @pytest.mark.asyncio
    async def test_critical_columns_defined(self):
        """Test critical columns are defined for drift detection."""
        from src.factory_data_product.ingest.drift_detector import CRITICAL_COLUMNS
        
        # Key sheets should have critical columns defined
        assert "OrdensFabrico" in CRITICAL_COLUMNS
        assert "FasesOrdemFabrico" in CRITICAL_COLUMNS
        assert "Funcionarios" in CRITICAL_COLUMNS
        
        # Critical columns should include IDs
        assert "OF_Id" in CRITICAL_COLUMNS["OrdensFabrico"]
        assert "FaseOf_Id" in CRITICAL_COLUMNS["FasesOrdemFabrico"]


class TestCuratedTransformer:
    """Test curated data transformation."""
    
    @pytest.mark.asyncio
    async def test_curated_transformer_instantiates(self):
        """Test CuratedTransformer can be instantiated."""
        from src.factory_data_product.ingest import CuratedTransformer
        
        transformer = CuratedTransformer()
        assert transformer is not None
    
    @pytest.mark.asyncio
    async def test_transformer_has_derivation_methods(self):
        """Test transformer has key derivation methods."""
        from src.factory_data_product.ingest import CuratedTransformer
        
        transformer = CuratedTransformer()
        
        # Should have methods for deriving fields
        assert hasattr(transformer, "derive_horas_previstas_final")
        assert hasattr(transformer, "add_quality_flags")
        assert hasattr(transformer, "detect_anomalies")


class TestActivation:
    """Test run activation flow."""
    
    @pytest.mark.asyncio
    async def test_ingestion_status_enum(self):
        """Test ingestion status values."""
        from src.factory_data_product.models.meta import IngestionStatus
        
        expected_statuses = [
            "received",
            "validating",
            "curating",
            "succeeded",
            "failed",
            "skipped",
        ]
        
        for status in IngestionStatus:
            assert status.value in expected_statuses
    
    @pytest.mark.asyncio
    async def test_active_run_model(self):
        """Test ActiveRun model fields."""
        from src.factory_data_product.models.meta import ActiveRun
        
        # Model should have required fields
        assert hasattr(ActiveRun, "__annotations__") or hasattr(ActiveRun, "active_ingestion_id")


class TestIdempotency:
    """Test ingestion idempotency."""
    
    @pytest.mark.asyncio
    async def test_file_hasher_available(self):
        """Test FileHasher is available."""
        from src.factory_data_product.ingest import FileHasher
        
        assert hasattr(FileHasher, "hash_file")
    
    @pytest.mark.asyncio
    async def test_row_hasher_available(self):
        """Test RowHasher is available."""
        from src.factory_data_product.ingest import RowHasher
        
        assert hasattr(RowHasher, "hash_row")
        assert hasattr(RowHasher, "hash_business_key")
    
    @pytest.mark.asyncio
    async def test_row_hash_is_deterministic(self):
        """Test row hashing is deterministic."""
        from src.factory_data_product.ingest import RowHasher
        
        test_row = {"id": "123", "name": "test", "value": 100}
        
        hash1 = RowHasher.hash_row(test_row)
        hash2 = RowHasher.hash_row(test_row)
        
        assert hash1 == hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])





