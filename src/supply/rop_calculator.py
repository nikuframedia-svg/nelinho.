"""
ProdPlan ONE - ROP Calculator
==============================

Calculate Reorder Point (ROP) and safety stock.
"""

import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


class ROPCalculator:
    """
    Calculate reorder point and safety stock.
    
    Formula:
        ROP = (avg_daily_demand × lead_time_days) + (z_score × LT_std × √lead_time_days)
        Safety Stock = z_score × LT_std × √lead_time_days
    
    Where:
        - avg_daily_demand: Average daily demand (units)
        - lead_time_days: Lead time in days
        - LT_std: Standard deviation of lead time
        - z_score: Service level quantile (90%→1.28, 95%→1.645, 99%→2.33)
    """
    
    def calculate_rop(
        self,
        avg_daily_demand: float,
        lead_time_days: int,
        lead_time_std_dev: float,
        service_level: float = 0.95,  # 95% fill rate
    ) -> Dict[str, float]:
        """
        Calculate ROP and safety stock.
        
        Args:
            avg_daily_demand: Average daily demand (units)
            lead_time_days: Lead time in days
            lead_time_std_dev: Standard deviation of lead time
            service_level: Service level (0.90, 0.95, or 0.99)
        
        Returns:
            {
                rop: float (total ROP),
                base_rop: float (avg demand × lead time),
                safety_stock: float,
                z_score: float,
                service_level: float,
            }
        """
        # Get z-score for service level
        z_score = self._z_score_from_service_level(service_level)
        
        # Base ROP (avg usage during lead time)
        base_rop = avg_daily_demand * lead_time_days
        
        # Safety stock
        safety_stock = z_score * lead_time_std_dev * np.sqrt(lead_time_days)
        
        # Total ROP
        rop = base_rop + safety_stock
        
        result = {
            "rop": round(rop, 2),
            "base_rop": round(base_rop, 2),
            "safety_stock": round(safety_stock, 2),
            "z_score": round(z_score, 3),
            "service_level": service_level,
        }
        
        logger.debug(
            f"ROP calculated: base={base_rop:.2f}, safety={safety_stock:.2f}, "
            f"total={rop:.2f} (service_level={service_level})"
        )
        
        return result
    
    def _z_score_from_service_level(self, service_level: float) -> float:
        """
        Approximate z-score from service level.
        
        Hardcoded mapping:
        - 90% → 1.28
        - 95% → 1.645
        - 99% → 2.33
        
        Args:
            service_level: Service level (0.90, 0.95, or 0.99)
        
        Returns:
            Z-score for the service level
        """
        service_to_z = {
            0.90: 1.28,
            0.95: 1.645,
            0.99: 2.33,
        }
        
        # Round to nearest supported service level
        rounded_level = min(service_to_z.keys(), key=lambda x: abs(x - service_level))
        return service_to_z[rounded_level]










