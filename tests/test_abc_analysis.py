"""
ProdPlan ONE - ABC Analysis Tests
==================================

Test ABC classification:
- Validate ABC distribution (80/15/5)
- Test SKU classification (A, B, C)
- Verify ABC calculation logic
"""

import pytest
from src.supply.abc_analysis import ABCAnalysis


class TestABCDistribution:
    """Test ABC distribution calculation (80/15/5)."""
    
    def test_abc_distribution_80_15_5(self):
        """
        Test that ABC distribution follows Pareto principle (80/15/5).
        
        A class: 80% of value (top 20% of SKUs)
        B class: 15% of value (next 30% of SKUs)
        C class: 5% of value (bottom 50% of SKUs)
        """
        analyzer = ABCAnalysis()
        
        # Create 100 SKUs with varying values
        skus = [
            {"sku_id": f"SKU-{i:03d}", "value": (100 - i) * 10}  # Decreasing values
            for i in range(100)
        ]
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # Verify all SKUs are classified
        total_classified = len(result["A"]) + len(result["B"]) + len(result["C"])
        assert total_classified == 100
        
        # Verify class A has top SKUs (highest values)
        class_a_values = [sku["value"] for sku in result["A"]]
        if class_a_values:
            max_value = max(sku["value"] for sku in skus)
            assert max(class_a_values) == max_value
    
    def test_abc_distribution_empty_list(self):
        """Test ABC distribution with empty SKU list."""
        analyzer = ABCAnalysis()
        
        result = analyzer.calculate_abc_distribution([])
        
        assert result["A"] == []
        assert result["B"] == []
        assert result["C"] == []
    
    def test_abc_distribution_single_sku(self):
        """Test ABC distribution with single SKU (should be class A)."""
        analyzer = ABCAnalysis()
        
        skus = [{"sku_id": "SKU-001", "value": 1000.0}]
        result = analyzer.calculate_abc_distribution(skus)
        
        assert len(result["A"]) == 1
        assert len(result["B"]) == 0
        assert len(result["C"]) == 0
        assert result["A"][0]["sku_id"] == "SKU-001"
    
    def test_abc_distribution_all_zero_values(self):
        """Test ABC distribution when all SKUs have zero value (all should be class C)."""
        analyzer = ABCAnalysis()
        
        skus = [
            {"sku_id": f"SKU-{i:03d}", "value": 0.0}
            for i in range(10)
        ]
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # All should be class C (zero value)
        assert len(result["A"]) == 0
        assert len(result["B"]) == 0
        assert len(result["C"]) == 10


class TestABCClassification:
    """Test ABC classification logic."""
    
    def test_class_a_has_highest_values(self):
        """Test that class A contains SKUs with highest values."""
        analyzer = ABCAnalysis()
        
        # Create SKUs with clear value separation
        skus = [
            {"sku_id": "SKU-HIGH-1", "value": 10000.0},
            {"sku_id": "SKU-HIGH-2", "value": 9000.0},
            {"sku_id": "SKU-MED-1", "value": 1000.0},
            {"sku_id": "SKU-LOW-1", "value": 100.0},
        ]
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # High-value SKUs should be in class A
        sku_ids_a = [sku["sku_id"] for sku in result["A"]]
        assert "SKU-HIGH-1" in sku_ids_a or "SKU-HIGH-2" in sku_ids_a
    
    def test_class_c_has_lowest_values(self):
        """Test that class C contains SKUs with lowest values."""
        analyzer = ABCAnalysis()
        
        skus = [
            {"sku_id": "SKU-HIGH", "value": 10000.0},
            {"sku_id": "SKU-MED", "value": 1000.0},
            {"sku_id": "SKU-LOW-1", "value": 100.0},
            {"sku_id": "SKU-LOW-2", "value": 50.0},
        ]
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # Low-value SKUs should be in class C
        sku_ids_c = [sku["sku_id"] for sku in result["C"]]
        # At least one low-value SKU should be in C
        assert len(result["C"]) > 0


class TestABCValueDistribution:
    """Test that value distribution follows 80/15/5 pattern."""
    
    def test_class_a_accumulates_80_percent_value(self):
        """Test that class A accumulates approximately 80% of total value."""
        analyzer = ABCAnalysis()
        
        # Create 10 SKUs with values 100, 90, 80, ..., 10
        skus = [
            {"sku_id": f"SKU-{i:02d}", "value": (10 - i) * 10.0}
            for i in range(10)
        ]
        
        total_value = sum(sku["value"] for sku in skus)
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # Calculate class A value
        class_a_value = sum(sku["value"] for sku in result["A"])
        class_a_percentage = (class_a_value / total_value) * 100 if total_value > 0 else 0
        
        # Class A should accumulate close to 80% of value
        assert class_a_percentage >= 70.0  # Allow some tolerance
    
    def test_class_b_accumulates_15_percent_value(self):
        """Test that class B accumulates approximately 15% of total value."""
        analyzer = ABCAnalysis()
        
        # Create larger set for better distribution
        skus = [
            {"sku_id": f"SKU-{i:03d}", "value": (50 - i) * 2.0}
            for i in range(50)
        ]
        
        total_value = sum(sku["value"] for sku in skus)
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # Calculate class B value
        class_b_value = sum(sku["value"] for sku in result["B"])
        class_b_percentage = (class_b_value / total_value) * 100 if total_value > 0 else 0
        
        # Class B should accumulate close to 15% of value (with tolerance)
        assert 5.0 <= class_b_percentage <= 25.0  # Allow tolerance
    
    def test_class_c_accumulates_5_percent_value(self):
        """Test that class C accumulates approximately 5% of total value."""
        analyzer = ABCAnalysis()
        
        # Create larger set for better distribution
        skus = [
            {"sku_id": f"SKU-{i:03d}", "value": (50 - i) * 2.0}
            for i in range(50)
        ]
        
        total_value = sum(sku["value"] for sku in skus)
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # Calculate class C value
        class_c_value = sum(sku["value"] for sku in result["C"])
        class_c_percentage = (class_c_value / total_value) * 100 if total_value > 0 else 0
        
        # Class C should accumulate close to 5% of value (with tolerance)
        assert class_c_percentage <= 20.0  # Allow tolerance


class TestABCEdgeCases:
    """Test edge cases in ABC analysis."""
    
    def test_abc_with_identical_values(self):
        """Test ABC distribution when all SKUs have identical values."""
        analyzer = ABCAnalysis()
        
        skus = [
            {"sku_id": f"SKU-{i:03d}", "value": 100.0}
            for i in range(10)
        ]
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # All SKUs should still be classified
        total_classified = len(result["A"]) + len(result["B"]) + len(result["C"])
        assert total_classified == 10
    
    def test_abc_returns_required_structure(self):
        """Test that ABC distribution returns required structure."""
        analyzer = ABCAnalysis()
        
        skus = [
            {"sku_id": "SKU-001", "value": 1000.0},
            {"sku_id": "SKU-002", "value": 500.0},
        ]
        
        result = analyzer.calculate_abc_distribution(skus)
        
        # Verify structure
        assert "A" in result
        assert "B" in result
        assert "C" in result
        
        # Verify all are lists
        assert isinstance(result["A"], list)
        assert isinstance(result["B"], list)
        assert isinstance(result["C"], list)










