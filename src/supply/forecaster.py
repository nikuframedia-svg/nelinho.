"""
ProdPlan ONE - ARIMA Forecaster
================================

Demand forecasting using Prophet (Facebook's time series forecasting library).
"""

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not available - forecasting will be limited")


class ARIMAForecaster:
    """
    Forecast demand using ARIMA/Prophet.
    
    Uses Prophet for time series forecasting with:
    - Yearly and weekly seasonality
    - Uncertainty intervals (P50, P90)
    - WMAPE validation
    - Quality classification (good/fair/poor)
    """
    
    def __init__(self, validation_threshold: float = 0.15):  # WMAPE threshold
        self.validation_threshold = validation_threshold
    
    async def forecast(
        self,
        sku_id: str,
        historical_data: List[Dict[str, Any]],  # [{date, quantity}]
        periods_ahead: int = 30,
    ) -> Dict[str, Any]:
        """
        Forecast demand for next N periods.
        
        Args:
            sku_id: SKU identifier
            historical_data: List of dicts with 'date' and 'quantity' keys
            periods_ahead: Number of periods to forecast (default: 30)
        
        Returns:
            {
                sku_id: str,
                forecasts: [{date, qty_p50, qty_p90}],
                wmape: float,
                quality: "good"|"fair"|"poor",
            }
        """
        if not PROPHET_AVAILABLE:
            return {
                "error": "prophet_not_available",
                "message": "Prophet library not installed. Install with: pip install prophet",
            }
        
        # Convert to DataFrame
        df = pd.DataFrame(historical_data)
        if 'date' not in df.columns or 'quantity' not in df.columns:
            return {"error": "invalid_data_format", "message": "Data must have 'date' and 'quantity' columns"}
        
        df['ds'] = pd.to_datetime(df['date'])
        df['y'] = df['quantity'].astype(float)
        df = df[['ds', 'y']].sort_values('ds')
        
        if len(df) < 20:
            logger.warning(
                f"Insufficient history for SKU {sku_id}: {len(df)} data points (need ≥20)"
            )
            return {"error": "insufficient_historical_data", "data_points": len(df)}
        
        # Fit Prophet model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.80,  # 80% confidence interval
        )
        
        try:
            model.fit(df)
        except Exception as e:
            logger.error(f"Prophet model fit failed for SKU {sku_id}: {e}")
            return {"error": "model_fit_failed", "message": str(e)}
        
        # Forecast
        future = model.make_future_dataframe(periods=periods_ahead)
        forecast = model.predict(future)
        
        # Validate with cross-validation (simplified WMAPE on recent data)
        if len(df) >= periods_ahead:
            recent_actual = df['y'].tail(periods_ahead).values
            recent_predicted = forecast['yhat'].tail(periods_ahead).values
            wmape = self._calculate_wmape(pd.Series(recent_actual), pd.Series(recent_predicted))
        else:
            wmape = None
        
        # Quality classification
        if wmape is not None:
            if wmape < 0.10:
                quality = "good"
            elif wmape < self.validation_threshold:
                quality = "fair"
            else:
                quality = "poor"
        else:
            quality = "fair"  # Default if no validation
        
        # Extract P50, P90 forecasts for future periods
        forecasts = []
        future_periods = forecast.tail(periods_ahead)
        
        for _, row in future_periods.iterrows():
            forecasts.append({
                "date": row['ds'].date().isoformat() if hasattr(row['ds'], 'date') else str(row['ds']),
                "qty_p50": max(0.0, float(row['yhat'])),  # Median
                "qty_p90": max(0.0, float(row['yhat_upper'])),  # Upper interval
            })
        
        logger.info(
            f"Forecast generated for SKU {sku_id}: {periods_ahead} periods, "
            f"WMAPE={wmape:.3f if wmape else 'N/A'}, quality={quality}"
        )
        
        return {
            "sku_id": sku_id,
            "forecasts": forecasts,
            "wmape": round(wmape, 4) if wmape is not None else None,
            "quality": quality,
        }
    
    def _calculate_wmape(self, actual: pd.Series, predicted: pd.Series) -> float:
        """
        Weighted Mean Absolute Percentage Error.
        
        Args:
            actual: Actual values
            predicted: Predicted values
        
        Returns:
            WMAPE (0-1 scale, or percentage if multiplied by 100)
        """
        mask = actual != 0
        if not mask.any():
            return 0.0  # No actual values
        
        weighted_error = np.abs((actual[mask] - predicted[mask]) / actual[mask]).mean()
        return float(weighted_error)


