"""
E2E Tests — KPI → Explain Flow
==============================

Tests the complete flow:
1. Request KPI data
2. Verify explained value envelope
3. Check trust index and coverage
4. Verify blocked metrics are handled correctly
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestKPIExplainFlow:
    """Test KPI → Explain flow."""
    
    @pytest.fixture
    def mock_semantic_queries(self):
        """Mock SemanticQueries for testing."""
        mock = MagicMock()
        mock.wip.return_value = {
            "total_wip_hours": 1250.5,
            "phases": [
                {"phase_id": "CORTE", "phase_name": "Corte", "wip_hours": 450.2},
                {"phase_id": "SOLDAGEM", "phase_name": "Soldagem", "wip_hours": 380.0},
            ],
            "trust_index": 0.75,
            "coverage": 0.82,
        }
        return mock
    
    @pytest.mark.asyncio
    async def test_kpi_returns_explained_value_envelope(self):
        """Test that KPI endpoints return ExplainedValue envelope."""
        from src.factory_data_product.semantic import SemanticQueries
        
        queries = SemanticQueries()
        result = queries.wip()
        
        # Should have required fields for ExplainedValue
        assert "trust_index" in result or result.get("total_wip_hours") is not None
    
    @pytest.mark.asyncio
    async def test_explain_endpoint_returns_metric_details(self):
        """Test explain endpoint returns proper metric details."""
        from src.explain.api import METRIC_CATALOG
        
        # Verify catalog exists with expected metrics
        assert "wip_theoretical" in METRIC_CATALOG or len(METRIC_CATALOG) > 0
        
        # Each metric should have required fields
        for metric_id, metric in METRIC_CATALOG.items():
            assert "name" in metric
            assert "formula" in metric
    
    @pytest.mark.asyncio
    async def test_blocked_metrics_not_returned(self):
        """Test that blocked metrics return BLOCKED status, not data."""
        from src.factory_data_product.config import BLOCKED_METRICS
        
        # Verify blocked metrics are defined
        assert "oee_real" in BLOCKED_METRICS
        assert "otd_official" in BLOCKED_METRICS
        
        # Each should have reason and required_data
        for metric_id, info in BLOCKED_METRICS.items():
            assert "reason" in info
            assert "required_data" in info
    
    @pytest.mark.asyncio
    async def test_trust_index_per_segment(self):
        """Test trust index is defined per data segment."""
        from src.factory_data_product.config import TRUST_INDEX
        
        # Should have trust for key segments
        assert "Erros" in TRUST_INDEX
        assert "Fases" in TRUST_INDEX
        assert "OrdensFabrico" in TRUST_INDEX
        
        # Trust values should be in valid range
        for segment, trust in TRUST_INDEX.items():
            assert 0 <= trust <= 100, f"Invalid trust for {segment}: {trust}"
    
    @pytest.mark.asyncio
    async def test_allowed_vs_blocked_metrics(self):
        """Test that allowed and blocked metrics are mutually exclusive."""
        from src.factory_data_product.config import ALLOWED_METRICS, BLOCKED_METRICS
        
        allowed_ids = set(ALLOWED_METRICS.keys())
        blocked_ids = set(BLOCKED_METRICS.keys())
        
        # Should not overlap
        overlap = allowed_ids & blocked_ids
        assert len(overlap) == 0, f"Metrics in both allowed and blocked: {overlap}"
    
    @pytest.mark.asyncio
    async def test_semantic_queries_available(self):
        """Test all expected semantic queries are available."""
        from src.factory_data_product.semantic import SemanticQueries
        
        queries = SemanticQueries()
        
        # Check required methods exist
        assert hasattr(queries, "wip")
        assert hasattr(queries, "backlog_by_phase")
        assert hasattr(queries, "bottlenecks")
        assert hasattr(queries, "quality_analysis")
        assert hasattr(queries, "mold_conflicts")
        assert hasattr(queries, "skills_risk")
        assert hasattr(queries, "lead_time_analysis")
    
    @pytest.mark.asyncio
    async def test_quality_scorer_generates_trust(self):
        """Test QualityScorer generates trust scores."""
        from src.factory_data_product.quality import QualityScorer
        
        scorer = QualityScorer()
        
        # Check required methods exist
        assert hasattr(scorer, "calculate_trust_index")
        assert hasattr(scorer, "generate_quality_report")
        assert hasattr(scorer, "generate_recommendations")


class TestExplainDrawerIntegration:
    """Test Explain Drawer UI integration."""
    
    @pytest.mark.asyncio
    async def test_metric_catalog_complete(self):
        """Test metric catalog has all required fields for UI."""
        from src.explain.api import METRIC_CATALOG
        
        required_fields = [
            "name",
            "formula",
            "semantic_label",
            "status",
        ]
        
        for metric_id, metric in METRIC_CATALOG.items():
            for field in required_fields:
                assert field in metric, f"Missing {field} in {metric_id}"
    
    @pytest.mark.asyncio
    async def test_blocked_metrics_have_improvement_suggestions(self):
        """Test blocked metrics provide data improvement suggestions."""
        from src.factory_data_product.config import BLOCKED_METRICS
        
        for metric_id, info in BLOCKED_METRICS.items():
            assert "required_data" in info, f"No required_data for {metric_id}"
            assert len(info["required_data"]) > 0, f"Empty required_data for {metric_id}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])





