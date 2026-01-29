"""
ProdPlan ONE - TrustIndex Calculator Tests
===========================================

Test TrustIndex calculation:
- Validate component weights sum to 1.0
- Test individual components (completeness, validity, consistency, timeliness)
- Verify TrustIndex calculation (0-1 scale)
"""

import pytest
from src.dqa.trust_index import TrustIndexCalculator, DataQualityComponent


class TestTrustIndexWeights:
    """Test that component weights sum to 1.0."""
    
    def test_component_weights_sum_to_one(self):
        """Test that all component weights sum to exactly 1.0."""
        weights_sum = (
            DataQualityComponent.COMPLETENESS.value +
            DataQualityComponent.VALIDITY.value +
            DataQualityComponent.CONSISTENCY.value +
            DataQualityComponent.TIMELINESS.value
        )
        assert weights_sum == 1.0, f"Component weights sum to {weights_sum}, expected 1.0"
    
    def test_component_weights_are_non_negative(self):
        """Test that all component weights are non-negative."""
        assert DataQualityComponent.COMPLETENESS.value >= 0
        assert DataQualityComponent.VALIDITY.value >= 0
        assert DataQualityComponent.CONSISTENCY.value >= 0
        assert DataQualityComponent.TIMELINESS.value >= 0


class TestTrustIndexCalculation:
    """Test TrustIndex calculation with various scenarios."""
    
    def test_perfect_trust_index(self):
        """Test TrustIndex calculation with perfect data (all components = 1.0)."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int},
            valid_ranges={"field1": (0, 100)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": 50, "field2": 100}
        result = calculator.calculate(entity, latency_ms=0)
        
        assert result["trust_index"] == 1.0
        assert result["components"]["completeness"] == 1.0
        assert result["components"]["validity"] == 1.0
        assert result["components"]["consistency"] == 1.0
        assert result["components"]["timeliness"] == 1.0
        assert len(result["issues"]) == 0
    
    def test_zero_trust_index(self):
        """Test TrustIndex calculation with worst data (all components = 0.0)."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int},
            valid_ranges={"field1": (0, 100)},
            sla_latency_seconds=60,
        )
        
        entity = {}  # Missing all required fields
        result = calculator.calculate(entity, latency_ms=120000)  # 120s latency (2x SLA)
        
        # TrustIndex should be close to 0 (due to missing fields and high latency)
        assert result["trust_index"] < 0.5
        assert len(result["issues"]) > 0
    
    def test_trust_index_between_zero_and_one(self):
        """Test TrustIndex calculation with partial data."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int},
            valid_ranges={"field1": (0, 100)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": 50}  # Missing field2
        result = calculator.calculate(entity, latency_ms=30000)  # 30s latency (within SLA)
        
        # TrustIndex should be between 0 and 1
        assert 0.0 < result["trust_index"] < 1.0
        assert result["trust_index"] >= 0.0
        assert result["trust_index"] <= 1.0


class TestCompletenessComponent:
    """Test completeness component calculation."""
    
    def test_completeness_all_fields_present(self):
        """Test completeness when all required fields are present."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int, "field3": float},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": "value1", "field2": 100, "field3": 3.14}
        result = calculator.calculate(entity)
        
        assert result["components"]["completeness"] == 1.0
    
    def test_completeness_no_fields_present(self):
        """Test completeness when no required fields are present."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {}
        result = calculator.calculate(entity)
        
        assert result["components"]["completeness"] == 0.0
    
    def test_completeness_partial_fields_present(self):
        """Test completeness when some required fields are present."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int, "field3": str},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": "value1"}  # Only 1 of 3 fields
        result = calculator.calculate(entity)
        
        assert result["components"]["completeness"] == pytest.approx(1.0 / 3.0, rel=0.01)


class TestValidityComponent:
    """Test validity component calculation."""
    
    def test_validity_all_values_in_range(self):
        """Test validity when all values are within valid ranges."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={"field1": (0, 100), "field2": (10, 50)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": 50, "field2": 30}
        result = calculator.calculate(entity)
        
        assert result["components"]["validity"] == 1.0
    
    def test_validity_value_out_of_range(self):
        """Test validity when value is out of range."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={"field1": (0, 100)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": 150}  # Out of range
        result = calculator.calculate(entity)
        
        assert result["components"]["validity"] == 0.0
    
    def test_validity_partial_values_in_range(self):
        """Test validity when some values are in range."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={"field1": (0, 100), "field2": (10, 50)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": 50, "field2": 100}  # field2 out of range
        result = calculator.calculate(entity)
        
        assert result["components"]["validity"] == pytest.approx(0.5, rel=0.01)


class TestTimelinessComponent:
    """Test timeliness component calculation."""
    
    def test_timeliness_within_sla(self):
        """Test timeliness when latency is within SLA."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {}
        result = calculator.calculate(entity, latency_ms=30000)  # 30s < 60s SLA
        
        assert result["components"]["timeliness"] == 1.0
    
    def test_timeliness_exceeds_sla(self):
        """Test timeliness when latency exceeds SLA."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {}
        result = calculator.calculate(entity, latency_ms=120000)  # 120s > 60s SLA
        
        # Timeliness should degrade (linear degradation)
        assert result["components"]["timeliness"] < 1.0
        assert result["components"]["timeliness"] >= 0.0
    
    def test_timeliness_double_sla(self):
        """Test timeliness when latency is double SLA."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {}
        result = calculator.calculate(entity, latency_ms=120000)  # 120s = 2x 60s SLA
        
        # Timeliness should be approximately 0 (degradation: 1 - (120-60)/60 = 0)
        assert result["components"]["timeliness"] <= 0.1  # Allow small tolerance


class TestTrustIndexIssuesDetection:
    """Test issue detection in TrustIndex calculation."""
    
    def test_issues_detection_missing_fields(self):
        """Test that missing required fields are detected as issues."""
        calculator = TrustIndexCalculator(
            required_fields={"field1": str, "field2": int},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": "value1"}  # Missing field2
        result = calculator.calculate(entity)
        
        assert len(result["issues"]) > 0
        assert any("Missing required field: field2" in issue for issue in result["issues"])
    
    def test_issues_detection_out_of_range(self):
        """Test that out-of-range values are detected as issues."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={"field1": (0, 100)},
            sla_latency_seconds=60,
        )
        
        entity = {"field1": 150}
        result = calculator.calculate(entity)
        
        assert len(result["issues"]) > 0
        assert any("outside range" in issue.lower() for issue in result["issues"])
    
    def test_issues_detection_latency(self):
        """Test that latency exceeding SLA is detected as issue."""
        calculator = TrustIndexCalculator(
            required_fields={},
            valid_ranges={},
            sla_latency_seconds=60,
        )
        
        entity = {}
        result = calculator.calculate(entity, latency_ms=120000)  # 120s > 60s SLA
        
        assert len(result["issues"]) > 0
        assert any("latency" in issue.lower() for issue in result["issues"])










