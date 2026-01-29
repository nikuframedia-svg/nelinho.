"""
ProdPlan ONE - ABC Analysis
============================

ABC classification for inventory management.

Classification:
- A (80% of value): Top SKUs by turnover (20% of SKUs)
- B (15% of value): Medium SKUs (30% of SKUs)
- C (5% of value): Low SKUs (50% of SKUs)
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ABCAnalysis:
    """
    ABC classification for inventory.
    
    Classifies SKUs by turnover value using Pareto principle.
    """
    
    def classify_sku(self, value: float, turnover: float) -> str:
        """
        Classify a single SKU (simplified - requires distribution context).
        
        This is a placeholder. Real classification requires full distribution.
        Use calculate_abc_distribution() for accurate classification.
        
        Args:
            value: SKU value
            turnover: SKU turnover
        
        Returns:
            "A", "B", or "C"
        """
        # This is simplified - real classification needs full distribution
        # Return based on turnover threshold (placeholder)
        if turnover > 0.8:
            return "A"
        elif turnover > 0.5:
            return "B"
        else:
            return "C"
    
    def calculate_abc_distribution(
        self,
        skus_list: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Calculate ABC distribution for a list of SKUs.
        
        Args:
            skus_list: List of SKU dicts with 'sku_id' and 'value' keys
        
        Returns:
            {
                "A": [list of SKU dicts - top 20% by value, 80% of total],
                "B": [list of SKU dicts - next 30%, 15% of total],
                "C": [list of SKU dicts - bottom 50%, 5% of total],
            }
        """
        if not skus_list:
            return {"A": [], "B": [], "C": []}
        
        # Sort SKUs by value (descending)
        sorted_skus = sorted(skus_list, key=lambda x: x.get("value", 0), reverse=True)
        
        # Calculate total value
        total_value = sum(sku.get("value", 0) for sku in sorted_skus)
        
        if total_value == 0:
            # All SKUs have zero value - classify all as C
            return {"A": [], "B": [], "C": sorted_skus}
        
        # Classify SKUs
        class_a = []  # Top 20% of SKUs, 80% of value
        class_b = []  # Next 30% of SKUs, 15% of value
        class_c = []  # Bottom 50% of SKUs, 5% of value
        
        cumulative_value = 0.0
        cumulative_percentage = 0.0
        
        for sku in sorted_skus:
            sku_value = sku.get("value", 0)
            cumulative_value += sku_value
            cumulative_percentage = (cumulative_value / total_value) * 100
            
            if cumulative_percentage <= 80.0:
                class_a.append(sku)
            elif cumulative_percentage <= 95.0:  # 80% + 15% = 95%
                class_b.append(sku)
            else:
                class_c.append(sku)
        
        logger.info(
            f"ABC classification: A={len(class_a)} SKUs ({cumulative_percentage:.1f}% of value), "
            f"B={len(class_b)} SKUs, C={len(class_c)} SKUs"
        )
        
        return {
            "A": class_a,
            "B": class_b,
            "C": class_c,
        }










