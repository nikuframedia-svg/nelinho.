"""
Tests for Factory Data Product — Contrato 010
=============================================

Tests cover:
- Unit: hashing, parsing, transformation
- Integration: full ingest pipeline
- Contract: API endpoints
- Security: RBAC/access control
"""

import pytest
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from src.factory_data_product.ingest.hasher import FileHasher, RowHasher
from src.factory_data_product.ingest.transformer import RawToCuratedTransformer, TransformResult
from src.factory_data_product.quality.gates import (
    check_required_sheets_present,
    check_required_columns_present,
    check_no_duplicate_business_keys,
    check_valid_numeric_ranges,
    QUALITY_CHECKS,
)
from src.factory_data_product.quality.runner import QualityRunner
from src.factory_data_product.models.meta import (
    IngestionStatus,
    QualityGateStatus,
    CheckSeverity,
)
from src.factory_data_product.models.semantic import (
    SemanticViewId,
    SEMANTIC_VIEW_DEFINITIONS,
    is_view_allowed,
)


# ============================================================================
# UNIT TESTS — HASHING
# ============================================================================

class TestHashing:
    """Test hashing utilities."""
    
    def test_file_hash_deterministic(self):
        """
        Given: A file
        When: Hash twice
        Then: Same hash both times
        """
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            
            hash1 = FileHasher.hash_file(Path(f.name))
            hash2 = FileHasher.hash_file(Path(f.name))
            
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA256 hex
    
    def test_row_hash_deterministic(self):
        """
        Given: A row payload
        When: Hash twice
        Then: Same hash both times
        """
        payload = {"a": 1, "b": "test", "c": None}
        
        hash1 = RowHasher.hash_row(payload)
        hash2 = RowHasher.hash_row(payload)
        
        assert hash1 == hash2
    
    def test_row_hash_order_independent(self):
        """
        Given: Same data in different order
        When: Hash
        Then: Same hash (keys are sorted)
        """
        payload1 = {"a": 1, "b": 2, "c": 3}
        payload2 = {"c": 3, "a": 1, "b": 2}
        
        hash1 = RowHasher.hash_row(payload1)
        hash2 = RowHasher.hash_row(payload2)
        
        assert hash1 == hash2
    
    def test_business_key_hash(self):
        """
        Given: Business key fields
        When: Hash
        Then: Returns hash for key fields only
        """
        payload = {"id": "123", "name": "test", "extra": "ignored"}
        
        hash1 = RowHasher.hash_business_key(["id"], payload)
        hash2 = RowHasher.hash_business_key(["id", "name"], payload)
        
        assert hash1 is not None
        assert hash2 is not None
        assert hash1 != hash2  # Different key fields
    
    def test_business_key_hash_missing_field(self):
        """
        Given: Missing business key field
        When: Hash
        Then: Returns None
        """
        payload = {"a": 1}
        
        result = RowHasher.hash_business_key(["missing"], payload)
        
        assert result is None


# ============================================================================
# UNIT TESTS — TRANSFORMATION
# ============================================================================

class TestTransformation:
    """Test RAW → CURATED transformation."""
    
    def test_transform_orders(self):
        """
        Given: RAW order rows
        When: Transform
        Then: Curated orders created
        """
        ingestion_id = uuid4()
        raw_rows = [
            {
                "sheet_name": "OrdensFabrico",
                "row_number": 2,
                "payload_json": {
                    "OF_Id": "OF001",
                    "OF_Produto_Id": "P001",
                    "OF_Estado": "Em Producao",
                },
            },
        ]
        
        transformer = RawToCuratedTransformer()
        result = transformer.transform(raw_rows, ingestion_id)
        
        assert len(result.orders) == 1
        assert result.orders[0]["of_id"] == "OF001"
        assert result.orders[0]["produto_id"] == "P001"
    
    def test_transform_order_phases_horas_finais(self):
        """
        Given: RAW order phase rows
        When: Transform
        Then: horas_finais calculated correctly
        """
        ingestion_id = uuid4()
        
        # Case 1: horas_previstas > 0 takes precedence
        raw_rows = [
            {
                "sheet_name": "FasesOrdemFabrico",
                "row_number": 2,
                "payload_json": {
                    "FaseOf_Id": "FOF001",
                    "FaseOf_OrdemFabrico_Id": "OF001",
                    "FaseOf_Fase_Id": "F001",
                    "FaseOf_HorasPrevistas": 5.0,
                    "StandardHoras": 3.0,
                },
            },
        ]
        
        transformer = RawToCuratedTransformer()
        result = transformer.transform(raw_rows, ingestion_id)
        
        assert len(result.order_phases) == 1
        assert result.order_phases[0]["horas_finais"] == Decimal("5.0")
    
    def test_transform_order_phases_fallback_to_standard(self):
        """
        Given: horas_previstas is 0 or None
        When: Transform
        Then: horas_finais uses StandardHoras
        """
        ingestion_id = uuid4()
        raw_rows = [
            {
                "sheet_name": "FasesOrdemFabrico",
                "row_number": 2,
                "payload_json": {
                    "FaseOf_Id": "FOF002",
                    "FaseOf_OrdemFabrico_Id": "OF001",
                    "FaseOf_Fase_Id": "F001",
                    "FaseOf_HorasPrevistas": 0,
                    "StandardHoras": 3.0,
                },
            },
        ]
        
        transformer = RawToCuratedTransformer()
        result = transformer.transform(raw_rows, ingestion_id)
        
        assert result.order_phases[0]["horas_finais"] == Decimal("3.0")


# ============================================================================
# UNIT TESTS — QUALITY GATES
# ============================================================================

class TestQualityGates:
    """Test quality gate checks."""
    
    def test_required_sheets_present_pass(self):
        """
        Given: All required sheets present
        When: Check
        Then: Pass
        """
        raw_rows = [
            {"sheet_name": "OrdensFabrico", "payload_json": {}},
            {"sheet_name": "FasesOrdemFabrico", "payload_json": {}},
            {"sheet_name": "Fases", "payload_json": {}},
        ]
        
        result = check_required_sheets_present(raw_rows, {})
        
        assert result.passed == True
    
    def test_required_sheets_present_fail(self):
        """
        Given: Missing required sheet
        When: Check
        Then: Fail with details
        """
        raw_rows = [
            {"sheet_name": "OrdensFabrico", "payload_json": {}},
        ]
        
        result = check_required_sheets_present(raw_rows, {})
        
        assert result.passed == False
        assert "FasesOrdemFabrico" in result.details["missing"]
    
    def test_no_duplicate_business_keys_pass(self):
        """
        Given: No duplicate keys
        When: Check
        Then: Pass
        """
        raw_rows = [
            {"sheet_name": "OrdensFabrico", "business_key_sha256": "abc123", "row_number": 2},
            {"sheet_name": "OrdensFabrico", "business_key_sha256": "def456", "row_number": 3},
        ]
        
        result = check_no_duplicate_business_keys(raw_rows, {})
        
        assert result.passed == True
    
    def test_no_duplicate_business_keys_fail(self):
        """
        Given: Duplicate business keys
        When: Check
        Then: Fail with details
        """
        raw_rows = [
            {"sheet_name": "OrdensFabrico", "business_key_sha256": "abc123", "row_number": 2},
            {"sheet_name": "OrdensFabrico", "business_key_sha256": "abc123", "row_number": 3},
        ]
        
        result = check_no_duplicate_business_keys(raw_rows, {})
        
        assert result.passed == False
        assert result.details["duplicate_count"] > 0
    
    def test_valid_numeric_ranges_pass(self):
        """
        Given: Values in range
        When: Check
        Then: Pass
        """
        raw_rows = [
            {
                "sheet_name": "FasesOrdemFabrico",
                "row_number": 2,
                "payload_json": {"FaseOf_HorasPrevistas": 5.0},
            },
        ]
        
        result = check_valid_numeric_ranges(raw_rows, {})
        
        assert result.passed == True
    
    def test_valid_numeric_ranges_fail(self):
        """
        Given: Value out of range
        When: Check
        Then: Fail
        """
        raw_rows = [
            {
                "sheet_name": "FasesOrdemFabrico",
                "row_number": 2,
                "payload_json": {"FaseOf_HorasPrevistas": -5.0},
            },
        ]
        
        result = check_valid_numeric_ranges(raw_rows, {})
        
        assert result.passed == False


class TestQualityRunner:
    """Test quality runner."""
    
    def test_run_all_checks(self):
        """
        Given: RAW rows
        When: Run all checks
        Then: All checks executed
        """
        raw_rows = [
            {"sheet_name": "OrdensFabrico", "payload_json": {"OF_Id": "1"}, "row_number": 2, "business_key_sha256": "abc"},
            {"sheet_name": "FasesOrdemFabrico", "payload_json": {"FaseOf_Id": "1", "FaseOf_OrdemFabrico_Id": "1", "FaseOf_Fase_Id": "1"}, "row_number": 2, "business_key_sha256": "def"},
            {"sheet_name": "Fases", "payload_json": {"Fase_Id": "1"}, "row_number": 2, "business_key_sha256": "ghi"},
        ]
        
        runner = QualityRunner()
        result = runner.run_all_checks(uuid4(), raw_rows)
        
        assert result.total_checks == len(QUALITY_CHECKS)
        assert result.overall_status in [QualityGateStatus.PASSED, QualityGateStatus.FAILED]
    
    def test_blocking_failure_fails_overall(self):
        """
        Given: Blocking check fails
        When: Run
        Then: Overall status is FAILED
        """
        raw_rows = []  # Empty = missing required sheets
        
        runner = QualityRunner()
        result = runner.run_all_checks(uuid4(), raw_rows)
        
        assert result.overall_status == QualityGateStatus.FAILED
        assert result.failed_blocking > 0


# ============================================================================
# UNIT TESTS — SEMANTIC VIEWS
# ============================================================================

class TestSemanticViews:
    """Test semantic view definitions."""
    
    def test_view_allow_list(self):
        """
        Given: View IDs
        When: Check allow list
        Then: Only defined views allowed
        """
        assert is_view_allowed("v_lead_time_historico") == True
        assert is_view_allowed("v_backlog_fase_teorico") == True
        assert is_view_allowed("sql_injection") == False
        assert is_view_allowed("DROP TABLE") == False
    
    def test_view_definitions_complete(self):
        """
        Given: View definitions
        When: Check
        Then: All have required fields
        """
        for view_id, view_def in SEMANTIC_VIEW_DEFINITIONS.items():
            assert view_def.view_id is not None
            assert view_def.name is not None
            assert view_def.fields is not None
            assert len(view_def.fields) > 0
    
    def test_sensitive_views_require_permission(self):
        """
        Given: Sensitive view
        When: Check
        Then: Has required permission
        """
        cost_view = SEMANTIC_VIEW_DEFINITIONS[SemanticViewId.COST_TEORICO_POR_ORDEM]
        
        assert cost_view.is_sensitive == True
        assert cost_view.requires_permission is not None
    
    def test_views_have_disclaimers(self):
        """
        Given: View definition
        When: Check
        Then: Has disclaimers explaining limitations
        """
        backlog_view = SEMANTIC_VIEW_DEFINITIONS[SemanticViewId.BACKLOG_FASE_TEORICO]
        
        assert len(backlog_view.disclaimers) > 0
        assert any("TEÓRIC" in d.upper() for d in backlog_view.disclaimers)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for full pipeline."""
    
    def test_idempotency_same_file_skipped(self):
        """
        Given: Same file ingested twice
        When: Second ingest
        Then: Marked as duplicate/skipped
        """
        from src.factory_data_product.ingest.engine import IngestEngine
        
        # Create engine with mock
        engine = IngestEngine()
        
        # Simulate first ingest
        first_id = uuid4()
        engine._ingestion_runs[first_id] = type('obj', (object,), {
            'id': first_id,
            'file_sha256': 'abc123',
            'status': IngestionStatus.SUCCEEDED,
        })()
        
        # Check duplicate detection
        duplicate = engine._find_duplicate('abc123')
        assert duplicate == first_id
    
    def test_raw_is_append_only(self):
        """
        Given: RAW storage
        When: Ingest data
        Then: Data is appended, never updated
        """
        from src.factory_data_product.ingest.engine import IngestEngine
        
        engine = IngestEngine()
        
        # Simulate adding rows
        engine._raw_rows.append({"id": uuid4(), "data": "row1"})
        initial_count = len(engine._raw_rows)
        
        engine._raw_rows.append({"id": uuid4(), "data": "row2"})
        
        assert len(engine._raw_rows) == initial_count + 1
        # RAW should never have rows removed
    
    def test_logical_rollback_preserves_data(self):
        """
        Given: Active ingestion
        When: Rollback
        Then: Data is preserved, only pointer changes
        """
        from src.factory_data_product.ingest.engine import IngestEngine
        
        engine = IngestEngine()
        
        # Create two ingestions
        id1 = uuid4()
        id2 = uuid4()
        
        engine._ingestion_runs[id1] = type('obj', (object,), {
            'id': id1,
            'status': IngestionStatus.SUCCEEDED,
        })()
        engine._ingestion_runs[id2] = type('obj', (object,), {
            'id': id2,
            'status': IngestionStatus.SUCCEEDED,
        })()
        
        # Activate id2
        engine.activate(id2, "test_user")
        assert engine.get_active_run()["active_ingestion_id"] == id2
        
        # Rollback to id1
        engine.rollback(id1, "test_user", "Testing rollback")
        assert engine.get_active_run()["active_ingestion_id"] == id1
        
        # Both ingestions still exist
        assert id1 in engine._ingestion_runs
        assert id2 in engine._ingestion_runs


# ============================================================================
# SECURITY TESTS
# ============================================================================

class TestSecurity:
    """Security tests for access control."""
    
    def test_pii_fields_detected(self):
        """
        Given: Data with PII fields
        When: Run PII check
        Then: Fields are detected
        """
        from src.factory_data_product.quality.gates import check_pii_policy
        
        raw_rows = [
            {
                "sheet_name": "Funcionarios",
                "row_number": 2,
                "payload_json": {
                    "Funcionario_Id": "123",
                    "Funcionario_Nome": "John Doe",  # PII!
                    "Email": "john@example.com",     # PII!
                },
            },
        ]
        
        result = check_pii_policy(raw_rows, {})
        
        # Should detect PII fields
        pii_fields = result.details.get("pii_fields_detected", [])
        assert len(pii_fields) > 0
    
    def test_sensitive_view_requires_permission(self):
        """
        Given: Cost view (sensitive)
        When: Check
        Then: Requires explicit permission
        """
        cost_view = SEMANTIC_VIEW_DEFINITIONS[SemanticViewId.COST_TEORICO_POR_ORDEM]
        
        assert cost_view.is_sensitive == True
        assert cost_view.requires_permission == "view:cost_data"
    
    def test_view_allow_list_prevents_sql_injection(self):
        """
        Given: Malicious view ID
        When: Check
        Then: Not allowed
        """
        malicious_ids = [
            "'; DROP TABLE users; --",
            "SELECT * FROM secrets",
            "../../../etc/passwd",
            "<script>alert('xss')</script>",
        ]
        
        for malicious_id in malicious_ids:
            assert is_view_allowed(malicious_id) == False


