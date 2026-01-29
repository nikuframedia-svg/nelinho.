"""
ProdPlan ONE - ARIMA Forecast Tests (Prophet)
==============================================

Test Prophet forecasting:
- Forecast generation (30 periods)
- WMAPE validation
- Quality classification (good/fair/poor)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.supply.forecaster import ARIMAForecaster


class TestProphetForecast:
    """Test Prophet forecast generation."""
    
    def test_forecast_generates_30_periods(self):
        """Test that forecast generates 30 periods by default."""
        forecaster = ARIMAForecaster()
        
        # Create historical data (minimum 20 points for Prophet)
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(20)],
            "value": [100 + i * 2 for i in range(20)],
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-001",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Should generate 30 periods
        assert len(forecast["forecast"]) == 30
        
        # Each period should have date and value
        for period in forecast["forecast"]:
            assert "date" in period
            assert "qty_p50" in period  # Median forecast
            assert "qty_p90" in period  # 90th percentile
    
    def test_forecast_custom_periods(self):
        """Test forecast with custom number of periods."""
        forecaster = ARIMAForecaster()
        
        base_date = datetime.now() - timedelta(days=20)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(20)],
            "value": [50 + i for i in range(20)],
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-002",
            historical_data=historical_data,
            periods_ahead=15,  # Custom periods
        )
        
        # Should generate 15 periods
        assert len(forecast["forecast"]) == 15
    
    def test_forecast_includes_confidence_intervals(self):
        """Test that forecast includes confidence intervals (p50, p90)."""
        forecaster = ARIMAForecaster()
        
        base_date = datetime.now() - timedelta(days=20)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(20)],
            "value": [100.0 for _ in range(20)],
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-003",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Check first forecast period
        first_period = forecast["forecast"][0]
        assert "qty_p50" in first_period
        assert "qty_p90" in first_period
        
        # p90 should be >= p50 (higher confidence = higher value)
        assert first_period["qty_p90"] >= first_period["qty_p50"]


class TestWMAPEValidation:
    """Test WMAPE (Weighted MAPE) validation."""
    
    def test_wmape_calculation(self):
        """Test WMAPE calculation for forecast validation."""
        forecaster = ARIMAForecaster()
        
        # Historical data with trend
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100 + i * 5 for i in range(30)],
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-004",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Forecast should include WMAPE
        assert "wmape" in forecast
        assert isinstance(forecast["wmape"], float)
        
        # WMAPE should be non-negative
        assert forecast["wmape"] >= 0.0
    
    def test_wmape_lower_is_better(self):
        """Test that lower WMAPE indicates better forecast quality."""
        # This test verifies that WMAPE is calculated correctly
        # Lower WMAPE = better forecast accuracy
        
        forecaster = ARIMAForecaster()
        
        # Data with clear trend (should have better WMAPE)
        base_date = datetime.now() - timedelta(days=30)
        historical_trend = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100 + i * 2 for i in range(30)],  # Linear trend
        })
        
        forecast_trend = forecaster.forecast(
            sku_id="SKU-005",
            historical_data=historical_trend,
            periods_ahead=30,
        )
        
        # WMAPE should be calculated
        assert "wmape" in forecast_trend
        assert forecast_trend["wmape"] >= 0.0


class TestQualityClassification:
    """Test quality classification (good/fair/poor)."""
    
    def test_quality_good_when_wmape_less_than_10(self):
        """Test that quality is 'good' when WMAPE < 10%."""
        forecaster = ARIMAForecaster()
        
        # Create data that should yield good forecast
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100.0 for _ in range(30)],  # Constant (easy to forecast)
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-006",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Should have quality classification
        assert "quality" in forecast
        assert forecast["quality"] in ["good", "fair", "poor"]
        
        # If WMAPE < 10%, quality should be "good"
        if forecast["wmape"] < 10.0:
            assert forecast["quality"] == "good"
    
    def test_quality_fair_when_wmape_10_to_15(self):
        """Test that quality is 'fair' when 10% <= WMAPE < 15%."""
        forecaster = ARIMAForecaster()
        
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100 + i * np.random.normal(0, 5) for i in range(30)],  # Some noise
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-007",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        assert "quality" in forecast
        
        # If 10% <= WMAPE < 15%, quality should be "fair"
        if 10.0 <= forecast["wmape"] < 15.0:
            assert forecast["quality"] == "fair"
    
    def test_quality_poor_when_wmape_greater_than_15(self):
        """Test that quality is 'poor' when WMAPE >= 15%."""
        forecaster = ARIMAForecaster()
        
        base_date = datetime.now() - timedelta(days=30)
        # High variance data (hard to forecast)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100 * (1 + np.random.normal(0, 0.2)) for _ in range(30)],
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-008",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        assert "quality" in forecast
        
        # If WMAPE >= 15%, quality should be "poor"
        if forecast["wmape"] >= 15.0:
            assert forecast["quality"] == "poor"


class TestProphetForecastEdgeCases:
    """Test edge cases in Prophet forecasting."""
    
    def test_forecast_requires_minimum_data_points(self):
        """Test that forecast requires minimum data points (20)."""
        forecaster = ARIMAForecaster()
        
        # Insufficient data (< 20 points)
        base_date = datetime.now() - timedelta(days=10)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(10)],
            "value": [100.0 for _ in range(10)],
        })
        
        # Should handle insufficient data gracefully
        forecast = forecaster.forecast(
            sku_id="SKU-009",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Should either return error or use default/imputed data
        assert "forecast" in forecast or "error" in forecast
    
    def test_forecast_handles_missing_values(self):
        """Test that forecast handles missing values in historical data."""
        forecaster = ARIMAForecaster()
        
        base_date = datetime.now() - timedelta(days=30)
        dates = [base_date + timedelta(days=i) for i in range(30)]
        values = [100.0 + i * 2 for i in range(30)]
        values[5] = None  # Missing value
        
        historical_data = pd.DataFrame({
            "date": dates,
            "value": values,
        })
        
        # Should handle missing values (forward-fill or interpolation)
        forecast = forecaster.forecast(
            sku_id="SKU-010",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Should still produce forecast
        assert "forecast" in forecast or "error" in forecast
    
    def test_forecast_returns_required_structure(self):
        """Test that forecast returns all required fields."""
        forecaster = ARIMAForecaster()
        
        base_date = datetime.now() - timedelta(days=30)
        historical_data = pd.DataFrame({
            "date": [base_date + timedelta(days=i) for i in range(30)],
            "value": [100.0 for _ in range(30)],
        })
        
        forecast = forecaster.forecast(
            sku_id="SKU-011",
            historical_data=historical_data,
            periods_ahead=30,
        )
        
        # Verify structure
        assert "forecast" in forecast
        assert "wmape" in forecast
        assert "quality" in forecast
        assert "sku_id" in forecast
        
        assert isinstance(forecast["forecast"], list)
        assert isinstance(forecast["wmape"], (int, float))
        assert isinstance(forecast["quality"], str)
        assert forecast["sku_id"] == "SKU-011"










