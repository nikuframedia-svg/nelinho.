"""
E2E Tests — Trust Regression Detection
======================================

Tests for trust index regression detection:
- Trust heatmap generation
- Regression detection between ingestions
- Alert generation
- Improvement priorities
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTrustHeatmapGeneration:
    """Test trust heatmap generation."""
    
    @pytest.mark.asyncio
    async def test_heatmap_generator_instantiates(self):
        """Test TrustHeatmapGenerator can be instantiated."""
        from src.factory_data_product.quality.trust_heatmap import (
            TrustHeatmapGenerator,
            get_trust_heatmap_generator,
        )
        
        generator = TrustHeatmapGenerator()
        assert generator is not None
        
        # Singleton should work
        singleton = get_trust_heatmap_generator()
        assert singleton is not None
    
    @pytest.mark.asyncio
    async def test_generate_heatmap_from_trust_index(self):
        """Test generating heatmap from TRUST_INDEX config."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        from src.factory_data_product.config import TRUST_INDEX
        
        generator = TrustHeatmapGenerator()
        heatmap = generator.generate()
        
        # Should have rows for each segment
        assert len(heatmap.rows) == len(TRUST_INDEX)
        
        # Should have overall trust
        assert 0 <= heatmap.overall_trust <= 100
        
        # Should categorize segments
        total_categorized = (
            len(heatmap.excellent_segments) +
            len(heatmap.good_segments) +
            len(heatmap.warning_segments) +
            len(heatmap.critical_segments)
        )
        assert total_categorized == len(TRUST_INDEX)
    
    @pytest.mark.asyncio
    async def test_heatmap_has_domains(self):
        """Test heatmap has expected domains."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        heatmap = generator.generate()
        
        expected_domains = ["structure", "timing", "quantities", "references", "quality"]
        
        assert heatmap.domains == expected_domains
    
    @pytest.mark.asyncio
    async def test_heatmap_to_dict(self):
        """Test heatmap can be serialized to dict."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        heatmap = generator.generate()
        
        data = heatmap.to_dict()
        
        assert "overall_trust" in data
        assert "overall_status" in data
        assert "domains" in data
        assert "segments" in data
        assert "summary" in data
        assert "generated_at" in data


class TestTrustStatus:
    """Test trust status categorization."""
    
    @pytest.mark.asyncio
    async def test_trust_status_enum(self):
        """Test TrustStatus enum values."""
        from src.factory_data_product.quality.trust_heatmap import TrustStatus
        
        assert TrustStatus.EXCELLENT.value == "excellent"
        assert TrustStatus.GOOD.value == "good"
        assert TrustStatus.WARNING.value == "warning"
        assert TrustStatus.CRITICAL.value == "critical"
    
    @pytest.mark.asyncio
    async def test_status_thresholds(self):
        """Test status is assigned based on correct thresholds."""
        from src.factory_data_product.quality.trust_heatmap import (
            TrustHeatmapGenerator,
            TrustStatus,
        )
        
        generator = TrustHeatmapGenerator()
        
        # Test thresholds
        assert generator._get_status(90) == TrustStatus.EXCELLENT
        assert generator._get_status(85) == TrustStatus.EXCELLENT
        assert generator._get_status(75) == TrustStatus.GOOD
        assert generator._get_status(70) == TrustStatus.GOOD
        assert generator._get_status(60) == TrustStatus.WARNING
        assert generator._get_status(50) == TrustStatus.WARNING
        assert generator._get_status(40) == TrustStatus.CRITICAL
        assert generator._get_status(0) == TrustStatus.CRITICAL


class TestRegressionDetection:
    """Test trust regression detection."""
    
    @pytest.mark.asyncio
    async def test_no_regression_on_first_heatmap(self):
        """Test no regression detected on first heatmap."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        heatmap = generator.generate()
        
        has_regression, regressed = generator.detect_regression(None, heatmap)
        
        assert has_regression is False
        assert len(regressed) == 0
    
    @pytest.mark.asyncio
    async def test_regression_detected_on_trust_drop(self):
        """Test regression is detected when trust drops."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        
        # Generate baseline
        trust_before = {
            "Erros": 90,
            "Fases": 85,
            "OrdensFabrico": 80,
        }
        heatmap_before = generator.generate(custom_trust=trust_before)
        
        # Generate with regression
        trust_after = {
            "Erros": 90,  # Same
            "Fases": 75,  # Dropped 10 points (> 5 threshold)
            "OrdensFabrico": 78,  # Dropped 2 points (< 5 threshold)
        }
        heatmap_after = generator.generate(custom_trust=trust_after)
        
        has_regression, regressed = generator.detect_regression(heatmap_before, heatmap_after)
        
        assert has_regression is True
        assert "Fases" in regressed  # Dropped > 5
        assert "OrdensFabrico" not in regressed  # Dropped < 5
    
    @pytest.mark.asyncio
    async def test_no_regression_on_improvement(self):
        """Test no regression detected when trust improves."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        
        trust_before = {"Erros": 80}
        trust_after = {"Erros": 90}  # Improved
        
        heatmap_before = generator.generate(custom_trust=trust_before)
        heatmap_after = generator.generate(custom_trust=trust_after)
        
        has_regression, regressed = generator.detect_regression(heatmap_before, heatmap_after)
        
        assert has_regression is False


class TestImprovementPriorities:
    """Test improvement priority generation."""
    
    @pytest.mark.asyncio
    async def test_get_improvement_priorities(self):
        """Test improvement priorities are generated."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        
        # Create heatmap with some low-trust segments
        trust = {
            "Erros": 90,  # Good
            "Fases": 55,  # Warning
            "OrdensFabrico": 40,  # Critical
        }
        heatmap = generator.generate(custom_trust=trust)
        
        priorities = generator.get_improvement_priorities(heatmap)
        
        # Should prioritize by impact
        assert len(priorities) > 0
        
        # OrdensFabrico should be highest priority (lowest trust)
        assert priorities[0]["segment"] == "OrdensFabrico"
        assert priorities[0]["impact_score"] == 60  # 100 - 40
    
    @pytest.mark.asyncio
    async def test_priorities_include_suggestions(self):
        """Test priorities include improvement suggestions."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        
        trust = {"LowTrustSegment": 40}
        heatmap = generator.generate(custom_trust=trust)
        
        priorities = generator.get_improvement_priorities(heatmap)
        
        assert len(priorities) > 0
        assert "suggestions" in priorities[0]


class TestAlertGeneration:
    """Test alert generation."""
    
    @pytest.mark.asyncio
    async def test_generate_alerts_for_critical(self):
        """Test alerts are generated for critical segments."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        
        trust = {
            "CriticalSegment": 30,  # Critical
            "GoodSegment": 80,
        }
        heatmap = generator.generate(custom_trust=trust)
        
        alerts = generator.generate_alerts(heatmap)
        
        # Should have at least one critical alert
        critical_alerts = [a for a in alerts if a["level"] == "critical"]
        assert len(critical_alerts) > 0
    
    @pytest.mark.asyncio
    async def test_alert_structure(self):
        """Test alert has required fields."""
        from src.factory_data_product.quality.trust_heatmap import TrustHeatmapGenerator
        
        generator = TrustHeatmapGenerator()
        
        trust = {"TestSegment": 40}
        heatmap = generator.generate(custom_trust=trust)
        
        alerts = generator.generate_alerts(heatmap)
        
        for alert in alerts:
            assert "level" in alert
            assert "segment" in alert
            assert "message" in alert
            assert "action" in alert


class TestTrustCell:
    """Test TrustCell data class."""
    
    @pytest.mark.asyncio
    async def test_trust_cell_fields(self):
        """Test TrustCell has required fields."""
        from src.factory_data_product.quality.trust_heatmap import TrustCell, TrustStatus
        
        cell = TrustCell(
            segment="TestSegment",
            domain="structure",
            trust_value=75.0,
            status=TrustStatus.GOOD,
        )
        
        assert cell.segment == "TestSegment"
        assert cell.domain == "structure"
        assert cell.trust_value == 75.0
        assert cell.status == TrustStatus.GOOD
        assert cell.coverage_pct == 0.0  # Default
        assert cell.issues == []  # Default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])





