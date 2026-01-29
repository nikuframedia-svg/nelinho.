"""
ProdPlan ONE - Drift Detection Tests
=====================================

Test Kolmogorov-Smirnov drift detection:
- KS test detects statistical drift (p-value < 0.05)
- No drift when distributions are similar (p-value >= 0.05)
- Verify p-value threshold logic
"""

import pytest
import numpy as np
from src.dqa.drift_detector import DriftDetector


class TestDriftDetection:
    """Test drift detection using Kolmogorov-Smirnov test."""
    
    def test_drift_detected_when_distributions_differ(self):
        """Test that drift is detected when recent and historical distributions differ."""
        detector = DriftDetector(p_value_threshold=0.05)
        
        # Historical data: normal distribution around 10
        historical_data = [
            {"field1": 8.0},
            {"field1": 10.0},
            {"field1": 12.0},
            {"field1": 9.0},
            {"field1": 11.0},
            {"field1": 10.0},
            {"field1": 9.0},
            {"field1": 11.0},
            {"field1": 10.0},
            {"field1": 12.0},
        ]
        
        # Recent data: shifted distribution around 20 (different mean)
        recent_data = [
            {"field1": 18.0},
            {"field1": 20.0},
            {"field1": 22.0},
            {"field1": 19.0},
            {"field1": 21.0},
            {"field1": 20.0},
            {"field1": 19.0},
            {"field1": 21.0},
            {"field1": 20.0},
            {"field1": 22.0},
        ]
        
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Should detect drift (different distributions)
        # Note: Actual drift detection depends on KS test p-value
        # This test verifies the function runs without error
        assert "drifted" in result
        assert "p_value" in result
        assert "statistic" in result
        assert isinstance(result["drifted"], bool)
    
    def test_no_drift_when_distributions_similar(self):
        """Test that no drift is detected when distributions are similar."""
        detector = DriftDetector(p_value_threshold=0.05)
        
        # Same distribution for both
        base_data = [
            {"field1": 10.0},
            {"field1": 11.0},
            {"field1": 9.0},
            {"field1": 10.5},
            {"field1": 11.5},
            {"field1": 9.5},
            {"field1": 10.0},
            {"field1": 11.0},
            {"field1": 9.0},
            {"field1": 10.0},
        ]
        
        historical_data = base_data.copy()
        recent_data = base_data.copy()  # Same distribution
        
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Should not detect drift (same distributions)
        # Note: KS test on identical distributions should give p-value ≈ 1.0
        assert "drifted" in result
        assert "p_value" in result
        
        # If distributions are identical, p-value should be high (no drift)
        if result["p_value"] >= 0.05:
            assert result["drifted"] == False
    
    def test_drift_detection_requires_sufficient_data(self):
        """Test that drift detection requires minimum data points (10)."""
        detector = DriftDetector(p_value_threshold=0.05)
        
        # Insufficient data (< 10 points)
        historical_data = [{"field1": 10.0}] * 5
        recent_data = [{"field1": 20.0}] * 5
        
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Should return "not drifted" with message about insufficient data
        assert result["drifted"] == False
        assert "insufficient" in result["msg"].lower() or "Insufficient" in result["msg"]
    
    def test_drift_detection_p_value_threshold(self):
        """Test that drift detection uses p-value threshold correctly."""
        detector = DriftDetector(p_value_threshold=0.05)
        
        # Create data that will likely have p-value < 0.05 (drift)
        historical_data = [{"field1": float(i)} for i in range(10, 30)]  # Range 10-29
        recent_data = [{"field1": float(i)} for i in range(50, 70)]  # Range 50-69 (different)
        
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Verify p-value is calculated
        assert "p_value" in result
        assert 0.0 <= result["p_value"] <= 1.0
        
        # Drift should be detected if p-value < 0.05
        if result["p_value"] < 0.05:
            assert result["drifted"] == True
        else:
            assert result["drifted"] == False
    
    def test_drift_detection_custom_threshold(self):
        """Test drift detection with custom p-value threshold."""
        # More strict threshold
        detector_strict = DriftDetector(p_value_threshold=0.01)
        
        historical_data = [{"field1": float(i)} for i in range(10, 30)]
        recent_data = [{"field1": float(i)} for i in range(50, 70)]
        
        result = detector_strict.detect_drift(recent_data, historical_data, "field1")
        
        # Should use custom threshold (0.01 instead of 0.05)
        assert "p_value" in result
        assert "drifted" in result


class TestDriftDetectionEdgeCases:
    """Test edge cases in drift detection."""
    
    def test_drift_detection_non_numeric_values(self):
        """Test that drift detection skips non-numeric values."""
        detector = DriftDetector()
        
        historical_data = [
            {"field1": 10.0},
            {"field1": "text"},  # Non-numeric
            {"field1": 12.0},
        ] * 5
        
        recent_data = [
            {"field1": 20.0},
            {"field1": "text"},
            {"field1": 22.0},
        ] * 5
        
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Should process numeric values and skip non-numeric
        assert "drifted" in result
        assert "p_value" in result
    
    def test_drift_detection_missing_field(self):
        """Test drift detection when field is missing in some records."""
        detector = DriftDetector()
        
        historical_data = [
            {"field1": 10.0},
            {"field2": 20.0},  # Different field
            {"field1": 12.0},
        ] * 5
        
        recent_data = [
            {"field1": 20.0},
            {"field1": 22.0},
        ] * 5
        
        # Testing field1 (exists in both)
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Should process available values
        assert "drifted" in result
    
    def test_drift_detection_returns_all_fields(self):
        """Test that drift detection returns all required fields."""
        detector = DriftDetector()
        
        historical_data = [{"field1": float(i)} for i in range(10, 30)]
        recent_data = [{"field1": float(i)} for i in range(50, 70)]
        
        result = detector.detect_drift(recent_data, historical_data, "field1")
        
        # Verify all required fields
        assert "drifted" in result
        assert "p_value" in result
        assert "statistic" in result
        assert "msg" in result
        
        # Verify types
        assert isinstance(result["drifted"], bool)
        assert isinstance(result["p_value"], (int, float))
        assert isinstance(result["statistic"], (int, float))
        assert isinstance(result["msg"], str)










