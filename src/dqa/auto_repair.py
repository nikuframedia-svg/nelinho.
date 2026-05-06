"""
ProdPlan ONE - Auto-Repair Engine
==================================

Automatically repair low-quality data when TrustIndex is 0.65-0.70.

Strategies:
1. Forward-fill: Fill missing values with last historical value
2. Mean imputation: If no history, use mean
3. Outlier clamping: Z-score > 3σ → clamp to ±3σ
"""

import logging
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class AutoRepairEngine:
    """
    Repair low-quality data automatically.

    Triggered when TrustIndex < REPAIR_UPPER_BOUND (default 0.70).

    Strategies:
    - Forward-fill: Missing values → last historical value
    - Mean imputation: If no history → mean of historical values
    - Outlier clamping: Z-score > 3σ → clamp to ±3σ
    """

    # Onda 1.4 — auto-repair triggers below the AUTO_COMMIT gate (0.70 by
    # default). Above the gate, the data is already trusted enough to commit;
    # below, repair-then-recompute is preferable to rejecting outright.
    REPAIR_UPPER_BOUND = 0.70

    def __init__(
        self,
        min_sample_size: int = 10,
        outlier_z_threshold: float = 3.0,
    ) -> None:
        # Onda 3.6 — minimum samples before clamp_outliers will engage. 10
        # is a reasonable z-score floor; tenants with sparse data can drop
        # to 5 (with reduced confidence in the resulting bounds). Wired
        # via TenantConfig at the calling layer; the engine itself stays
        # session-free.
        self.min_sample_size = min_sample_size
        self.outlier_z_threshold = outlier_z_threshold

    def repair(
        self,
        entity: Dict[str, Any],
        trust_index: float,
        historical_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Repair entity when TrustIndex < REPAIR_UPPER_BOUND (0.70).

        Args:
            entity: Entity dictionary to repair
            trust_index: Current TrustIndex (any value in [0, 1])
            historical_data: List of historical entity dictionaries

        Returns:
            {
                entity: Dict (repaired entity),
                repairs: List[Dict] (list of repair actions),
            }
        """
        if trust_index >= self.REPAIR_UPPER_BOUND:
            return {"entity": entity, "repairs": []}
        
        repaired = entity.copy()
        repairs = []
        
        # Strategy 1: Fill missing values via forward-fill or mean
        repaired, forward_fill_repairs = self._fill_missing_values(repaired, historical_data)
        repairs.extend(forward_fill_repairs)
        
        # Strategy 2: Clamp outliers (Z-score > 3σ)
        repaired, outlier_repairs = self._clamp_outliers(repaired, historical_data)
        repairs.extend(outlier_repairs)
        
        logger.info(
            f"Auto-repair applied: {len(repairs)} repairs. "
            f"TrustIndex: {trust_index:.3f} → target: ≥0.70"
        )
        
        return {"entity": repaired, "repairs": repairs}
    
    def _fill_missing_values(
        self,
        entity: Dict[str, Any],
        historical_data: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Fill missing values via forward-fill or mean imputation.
        
        Returns: (repaired_entity, repairs_list)
        """
        repaired = entity.copy()
        repairs = []
        
        for key, value in entity.items():
            if value is None:
                # Try forward-fill (last non-null value from historical)
                historical_values = [
                    d.get(key) for d in historical_data 
                    if d.get(key) is not None
                ]
                
                if historical_values:
                    filled_value = historical_values[-1]  # Last value
                    repaired[key] = filled_value
                    repairs.append({
                        "field": key,
                        "action": "forward_fill",
                        "value": filled_value,
                    })
                else:
                    # Fallback: mean (if numeric)
                    numeric_values = [
                        v for v in historical_values 
                        if isinstance(v, (int, float))
                    ]
                    if numeric_values:
                        mean_value = float(np.mean(numeric_values))
                        repaired[key] = mean_value
                        repairs.append({
                            "field": key,
                            "action": "mean_impute",
                            "value": mean_value,
                        })
        
        return repaired, repairs
    
    def _clamp_outliers(
        self,
        entity: Dict[str, Any],
        historical_data: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Clamp values at Z-score > 3σ.
        
        Returns: (repaired_entity, repairs_list)
        """
        repaired = entity.copy()
        repairs = []
        
        for key, value in entity.items():
            if not isinstance(value, (int, float)):
                continue
            
            # Get historical stats
            historical_values = [
                d.get(key) for d in historical_data 
                if isinstance(d.get(key), (int, float))
            ]
            
            if len(historical_values) < self.min_sample_size:
                continue  # Not enough data

            mu = np.mean(historical_values)
            sigma = np.std(historical_values)

            if sigma == 0:
                continue  # No variance

            z_score = abs((value - mu) / sigma)

            if z_score > self.outlier_z_threshold:
                # Clamp to ±N·σ where N == self.outlier_z_threshold
                z = self.outlier_z_threshold
                clamped_value = np.clip(value, mu - z * sigma, mu + z * sigma)
                repaired[key] = clamped_value
                repairs.append({
                    "field": key,
                    "action": "outlier_clamp",
                    "original": value,
                    "clamped": float(clamped_value),
                    "z_score": round(z_score, 2),
                })
        
        return repaired, repairs










