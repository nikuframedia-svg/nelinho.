"""
ProdPlan ONE - ROP Calculation Tests
=====================================

Test Reorder Point (ROP) calculation:
- Validate ROP formula (base ROP + safety stock)
- Test safety stock calculation
- Verify z-score mapping (90%→1.28, 95%→1.645, 99%→2.33)
"""

import pytest
import numpy as np
from src.supply.rop_calculator import ROPCalculator


class TestROPFormula:
    """Test ROP formula: ROP = base_rop + safety_stock."""
    
    def test_rop_formula_base_plus_safety_stock(self):
        """Test that ROP = base_rop + safety_stock."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.95,
        )
        
        # Verify formula: ROP = base_rop + safety_stock
        calculated_rop = result["base_rop"] + result["safety_stock"]
        assert abs(calculated_rop - result["rop"]) < 0.01, "ROP should equal base_rop + safety_stock"
    
    def test_base_rop_is_avg_demand_times_lead_time(self):
        """Test that base_rop = avg_daily_demand × lead_time_days."""
        calculator = ROPCalculator()
        
        avg_daily_demand = 50.0
        lead_time_days = 7
        
        result = calculator.calculate_rop(
            avg_daily_demand=avg_daily_demand,
            lead_time_days=lead_time_days,
            lead_time_std_dev=1.0,
            service_level=0.95,
        )
        
        expected_base_rop = avg_daily_demand * lead_time_days
        assert abs(result["base_rop"] - expected_base_rop) < 0.01


class TestSafetyStockCalculation:
    """Test safety stock calculation: z_score × LT_std × √lead_time_days."""
    
    def test_safety_stock_formula(self):
        """Test safety stock formula: z_score × LT_std × √lead_time_days."""
        calculator = ROPCalculator()
        
        lead_time_days = 5
        lead_time_std_dev = 2.0
        service_level = 0.95
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=lead_time_days,
            lead_time_std_dev=lead_time_std_dev,
            service_level=service_level,
        )
        
        z_score = result["z_score"]
        expected_safety_stock = z_score * lead_time_std_dev * np.sqrt(lead_time_days)
        
        assert abs(result["safety_stock"] - expected_safety_stock) < 0.01
    
    def test_safety_stock_increases_with_service_level(self):
        """Test that safety stock increases with higher service level."""
        calculator = ROPCalculator()
        
        # Lower service level
        result_90 = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.90,
        )
        
        # Higher service level
        result_99 = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.99,
        )
        
        # Safety stock should be higher for 99% service level
        assert result_99["safety_stock"] > result_90["safety_stock"]
    
    def test_safety_stock_increases_with_std_dev(self):
        """Test that safety stock increases with higher lead time std dev."""
        calculator = ROPCalculator()
        
        # Lower std dev
        result_low = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=0.5,
            service_level=0.95,
        )
        
        # Higher std dev
        result_high = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=2.0,
            service_level=0.95,
        )
        
        # Safety stock should be higher for higher std dev
        assert result_high["safety_stock"] > result_low["safety_stock"]


class TestZScoreMapping:
    """Test z-score mapping for service levels."""
    
    def test_z_score_90_percent(self):
        """Test z-score for 90% service level is 1.28."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.90,
        )
        
        assert abs(result["z_score"] - 1.28) < 0.01, f"Expected z-score 1.28 for 90% service level, got {result['z_score']}"
    
    def test_z_score_95_percent(self):
        """Test z-score for 95% service level is 1.645."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.95,
        )
        
        assert abs(result["z_score"] - 1.645) < 0.01, f"Expected z-score 1.645 for 95% service level, got {result['z_score']}"
    
    def test_z_score_99_percent(self):
        """Test z-score for 99% service level is 2.33."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.99,
        )
        
        assert abs(result["z_score"] - 2.33) < 0.01, f"Expected z-score 2.33 for 99% service level, got {result['z_score']}"
    
    def test_z_score_rounds_to_nearest_supported(self):
        """Test that z-score rounds to nearest supported service level."""
        calculator = ROPCalculator()
        
        # Test 92% service level (should round to 90%)
        result_92 = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.92,
        )
        
        # Should use z-score for 90% (1.28)
        assert abs(result_92["z_score"] - 1.28) < 0.01


class TestROPEdgeCases:
    """Test edge cases in ROP calculation."""
    
    def test_rop_with_zero_std_dev(self):
        """Test ROP calculation with zero standard deviation."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=0.0,  # No variability
            service_level=0.95,
        )
        
        # Safety stock should be 0 when std dev is 0
        assert result["safety_stock"] == 0.0
        # ROP should equal base_rop
        assert result["rop"] == result["base_rop"]
    
    def test_rop_with_single_day_lead_time(self):
        """Test ROP calculation with single day lead time."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=1,
            lead_time_std_dev=0.5,
            service_level=0.95,
        )
        
        # Base ROP should equal daily demand
        assert result["base_rop"] == 100.0
        # Safety stock should be: z_score × 0.5 × √1 = z_score × 0.5
        expected_safety_stock = result["z_score"] * 0.5 * np.sqrt(1)
        assert abs(result["safety_stock"] - expected_safety_stock) < 0.01
    
    def test_rop_returns_all_required_fields(self):
        """Test that ROP calculation returns all required fields."""
        calculator = ROPCalculator()
        
        result = calculator.calculate_rop(
            avg_daily_demand=100.0,
            lead_time_days=5,
            lead_time_std_dev=1.0,
            service_level=0.95,
        )
        
        # Verify all required fields are present
        assert "rop" in result
        assert "base_rop" in result
        assert "safety_stock" in result
        assert "z_score" in result
        assert "service_level" in result
        
        # Verify all values are numeric
        assert isinstance(result["rop"], (int, float))
        assert isinstance(result["base_rop"], (int, float))
        assert isinstance(result["safety_stock"], (int, float))
        assert isinstance(result["z_score"], (int, float))
        assert isinstance(result["service_level"], float)










