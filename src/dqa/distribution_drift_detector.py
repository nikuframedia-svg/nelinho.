"""
ProdPlan ONE - Distribution Drift Detection
============================================

Detect statistical drift in data distributions using Kolmogorov-Smirnov test.

Onda 3.3 — renamed from `drift_detector.py` to disambiguate from
`src/factory_data_product/ingest/drift_detector.py`, which detects
**schema** drift (added/removed/renamed columns), not distribution drift.
The two responsibilities are independent and the shared name made grep
and imports ambiguous.
"""

import logging
from typing import Any, Dict, List

import numpy as np
from scipy.stats import ks_2samp

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Detect statistical drift in data distributions.
    
    Uses Kolmogorov-Smirnov test to compare recent vs historical distributions.
    Threshold: p-value < 0.05 indicates drift.
    """
    
    def __init__(self, p_value_threshold: float = 0.05):
        self.p_value_threshold = p_value_threshold
    
    def detect_drift(
        self,
        recent_data: List[Dict[str, Any]],
        historical_data: List[Dict[str, Any]],
        field_name: str,
    ) -> Dict[str, Any]:
        """
        Kolmogorov-Smirnov test for drift.
        
        Args:
            recent_data: Recent data samples (last N samples)
            historical_data: Historical baseline (older samples)
            field_name: Field name to check for drift
        
        Returns:
            {
                drifted: bool,
                p_value: float,
                statistic: float,
                msg: str,
            }
        """
        # Extract numeric values
        recent_values = [
            d.get(field_name) for d in recent_data 
            if isinstance(d.get(field_name), (int, float))
        ]
        historical_values = [
            d.get(field_name) for d in historical_data 
            if isinstance(d.get(field_name), (int, float))
        ]
        
        if len(recent_values) < 10 or len(historical_values) < 10:
            return {
                "drifted": False,
                "p_value": 1.0,
                "statistic": 0.0,
                "msg": "Insufficient data for drift detection",
            }
        
        # Kolmogorov-Smirnov test
        statistic, p_value = ks_2samp(recent_values, historical_values)
        
        drifted = p_value < self.p_value_threshold
        
        if drifted:
            recent_mu = np.mean(recent_values)
            historical_mu = np.mean(historical_values)
            logger.warning(
                f"Drift detected in {field_name}: "
                f"historical_mean={historical_mu:.2f}, recent_mean={recent_mu:.2f}, "
                f"p_value={p_value:.4f}"
            )
        
        return {
            "drifted": drifted,
            "p_value": round(p_value, 4),
            "statistic": round(statistic, 4),
            "msg": (
                f"Drift detected in {field_name}" if drifted 
                else f"No drift in {field_name}"
            ),
        }










