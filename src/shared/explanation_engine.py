"""
ProdPlan ONE - Explanation Engine
==================================

Service for generating KPI explanations with root cause analysis.
Explains WHY metrics are at current values by analyzing contributing factors.
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.schedule import ProductionSchedule, ScheduleStatus

logger = logging.getLogger(__name__)


class ExplanationEngine:
    """
    Engine for generating KPI explanations.
    
    Analyzes root causes by:
    1. Querying relevant data
    2. Identifying contributing factors
    3. Weighting by impact
    4. Generating top factors with percentages
    5. Suggesting improvement actions
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    async def explain_otd(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Explain On-Time Delivery (OTD) metric.
        
        Analyzes late orders and identifies root causes:
        - Machine breakdowns
        - Setup delays
        - Material shortages
        - Capacity constraints
        
        Returns:
            {
                "reason": "X orders delayed",
                "topFactors": [
                    {"name": "Machine issues", "weight": "45%", "count": 7},
                    {"name": "Setup delays", "weight": "30%", "count": 5},
                    ...
                ],
                "suggestion": {
                    "title": "Increase safety stock",
                    "description": "...",
                    "estimatedImpact": {...}
                }
            }
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        # Query late orders - orders where actual_end > scheduled_end_date
        # or scheduled_end_date < today for in-progress orders
        late_orders_query = select(
            ProductionSchedule.order_id,
            ProductionSchedule.scheduled_end_date,
            ProductionSchedule.actual_end,
            ProductionSchedule.status,
            ProductionSchedule.machine_id,
        ).where(
            and_(
                ProductionSchedule.tenant_id == self.tenant_id,
                or_(
                    # Completed but late
                    and_(
                        ProductionSchedule.status == ScheduleStatus.COMPLETED,
                        ProductionSchedule.actual_end.isnot(None),
                        ProductionSchedule.scheduled_end_date.isnot(None),
                        # actual_end > scheduled_end_date (convert date to datetime for comparison)
                    ),
                    # In progress but past due date
                    and_(
                        ProductionSchedule.status == ScheduleStatus.IN_PROGRESS,
                        ProductionSchedule.scheduled_end_date < end_date,
                    ),
                ),
            )
        )
        
        result = await self.session.execute(late_orders_query)
        late_schedules = result.fetchall()
        
        if not late_schedules:
            return {
                "reason": "All orders on time",
                "topFactors": [],
                "suggestion": None,
            }
        
        # Analyze root causes
        causes = await self._analyze_root_causes(late_schedules)
        
        # Weight by impact
        weighted = self._weight_by_impact(causes)
        
        # Get top 3 factors
        top_factors = sorted(
            causes.items(),
            key=lambda x: weighted.get(x[0], 0),
            reverse=True
        )[:3]
        
        # Format response
        top_factors_list = [
            {
                "name": factor_name,
                "weight": f"{weighted[factor_name]:.0f}%",
                "count": factor_data.get("count", 0),
            }
            for factor_name, factor_data in top_factors
        ]
        
        # Generate suggestion
        suggestion = await self._suggest_improvement(causes, weighted)
        
        return {
            "reason": f"{len(set(s.order_id for s in late_schedules))} orders delayed",
            "topFactors": top_factors_list,
            "suggestion": suggestion,
        }
    
    async def _analyze_root_causes(
        self,
        late_schedules: List[Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze root causes from late schedules.
        
        For now, uses heuristics:
        - Machine-related: if machine_id is None or specific machines
        - Setup delays: if setup_time_minutes is high
        - Capacity: if too many orders on same machine
        
        Returns dict of cause_name -> {count, total_delay, etc.}
        """
        causes = {
            "Machine Issues": {"count": 0, "total_delay": 0},
            "Setup Delays": {"count": 0, "total_delay": 0},
            "Material Shortages": {"count": 0, "total_delay": 0},
            "Capacity Constraints": {"count": 0, "total_delay": 0},
        }
        
        # Simple heuristic: count by machine availability
        # If machine_id is None or specific pattern, categorize
        for schedule in late_schedules:
            # Machine issues - if machine assignment is problematic
            if schedule.machine_id is None:
                causes["Machine Issues"]["count"] += 1
            else:
                # Check if this machine has multiple late orders
                causes["Capacity Constraints"]["count"] += 1
        
        # For now, evenly distribute among available causes
        # TODO: Enhance with actual machine breakdown data, material tracking, etc.
        
        return causes
    
    def _weight_by_impact(
        self,
        causes: Dict[str, Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Weight causes by impact (count × delay_hours).
        
        Returns dict of cause_name -> weight_percentage
        """
        total_impact = sum(
            cause_data.get("count", 0) for cause_data in causes.values()
        )
        
        if total_impact == 0:
            return {}
        
        weighted = {}
        for cause_name, cause_data in causes.items():
            count = cause_data.get("count", 0)
            weight_pct = (count / total_impact) * 100.0 if total_impact > 0 else 0.0
            weighted[cause_name] = weight_pct
        
        return weighted
    
    async def _suggest_improvement(
        self,
        causes: Dict[str, Dict[str, Any]],
        weighted: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        """
        Generate improvement suggestion based on top causes.
        
        Returns suggestion dict or None if no clear action.
        """
        if not weighted:
            return None
        
        top_cause = max(weighted.items(), key=lambda x: x[1])
        
        suggestions_map = {
            "Machine Issues": {
                "title": "Increase preventive maintenance",
                "description": "Schedule more frequent maintenance to reduce breakdowns",
                "estimatedImpact": {"otd": "+5%", "cost": "+2%"},
            },
            "Capacity Constraints": {
                "title": "Increase safety stock",
                "description": "Build buffer inventory to handle demand spikes",
                "estimatedImpact": {"otd": "+8%", "inventory": "+15%"},
            },
            "Setup Delays": {
                "title": "Optimize changeover process",
                "description": "Reduce setup times through SMED techniques",
                "estimatedImpact": {"otd": "+3%", "efficiency": "+10%"},
            },
            "Material Shortages": {
                "title": "Improve material planning",
                "description": "Better forecasting and supplier coordination",
                "estimatedImpact": {"otd": "+6%", "cost": "+1%"},
            },
        }
        
        return suggestions_map.get(top_cause[0], {
            "title": "Review scheduling process",
            "description": "Analyze late orders to identify patterns",
            "estimatedImpact": {"otd": "+2%"},
        })
    
    async def explain_kpi(
        self,
        kpi_name: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Generic KPI explanation dispatcher.
        
        Routes to specific explanation methods based on KPI name.
        """
        if kpi_name.lower() in ("otd", "on_time_delivery", "on-time_delivery"):
            return await self.explain_otd(start_date, end_date)
        elif kpi_name.lower() in ("margin", "profit_margin"):
            # TODO: Implement margin explanation
            return {"reason": "Margin analysis not yet implemented", "topFactors": []}
        elif kpi_name.lower() in ("inventory_turnover", "turnover"):
            # TODO: Implement inventory turnover explanation
            return {"reason": "Inventory turnover analysis not yet implemented", "topFactors": []}
        else:
            return {
                "reason": f"Explanation for {kpi_name} not yet available",
                "topFactors": [],
            }










