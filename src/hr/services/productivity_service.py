"""
ProdPlan ONE - Productivity Service
====================================

Business logic for productivity tracking.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.hr.models.productivity import EmployeeProductivity
from src.hr.engines.productivity_adapter import ProductivityAdapter, ProductionRecord
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import ProductivityRecordedEvent


class ProductivityService:
    """
    Service for productivity tracking.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._adapter = ProductivityAdapter()
    
    async def record_productivity(
        self,
        employee_id: UUID,
        operation_id: UUID,
        order_id: str,
        record_date: date,
        standard_hours: Decimal,
        actual_hours: Decimal,
        standard_quantity: Decimal,
        actual_quantity: Decimal,
        good_quantity: Decimal,
    ) -> EmployeeProductivity:
        """
        Record productivity for an operation.
        """
        # Calculate metrics
        efficiency = Decimal("0")
        if actual_hours > 0:
            efficiency = (standard_hours / actual_hours * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        
        quality = Decimal("0")
        if actual_quantity > 0:
            quality = (good_quantity / actual_quantity * 100).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        
        bonus_eligible = efficiency >= 100 and quality >= 98
        
        record = EmployeeProductivity(
            tenant_id=self.tenant_id,
            employee_id=employee_id,
            operation_id=operation_id,
            order_id=order_id,
            record_date=record_date,
            standard_hours=standard_hours,
            actual_hours=actual_hours,
            standard_quantity=standard_quantity,
            actual_quantity=actual_quantity,
            good_quantity=good_quantity,
            efficiency_percent=efficiency,
            quality_percent=quality,
            bonus_eligible=bonus_eligible,
        )
        
        self.session.add(record)
        await self.session.flush()
        
        # Publish event
        await publish_event(
            Topics.PRODUCTIVITY_RECORDED,
            ProductivityRecordedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "employee_id": str(employee_id),
                    "operation_id": str(operation_id),
                    "actual_hours": float(actual_hours),
                    "standard_hours": float(standard_hours),
                    "efficiency_percent": float(efficiency),
                    "quality_score": float(quality),
                    "bonus_eligible": bonus_eligible,
                },
            ),
        )
        
        return record
    
    async def get_employee_productivity(
        self,
        employee_id: UUID,
        from_date: date = None,
        to_date: date = None,
    ) -> Dict[str, Any]:
        """Get productivity summary for an employee."""
        query = select(EmployeeProductivity).where(
            and_(
                EmployeeProductivity.employee_id == employee_id,
                EmployeeProductivity.tenant_id == self.tenant_id,
            )
        )
        
        if from_date:
            query = query.where(EmployeeProductivity.record_date >= from_date)
        if to_date:
            query = query.where(EmployeeProductivity.record_date <= to_date)
        
        result = await self.session.execute(query)
        records = list(result.scalars().all())
        
        if not records:
            return {
                "employee_id": str(employee_id),
                "records_count": 0,
                "avg_efficiency": 0,
                "avg_quality": 0,
                "bonus_eligible": False,
            }
        
        total_std_hours = sum(r.standard_hours for r in records)
        total_act_hours = sum(r.actual_hours for r in records)
        total_act_qty = sum(r.actual_quantity for r in records)
        total_good_qty = sum(r.good_quantity for r in records)
        
        avg_efficiency = (total_std_hours / total_act_hours * 100) if total_act_hours > 0 else Decimal("0")
        avg_quality = (total_good_qty / total_act_qty * 100) if total_act_qty > 0 else Decimal("0")
        
        return {
            "employee_id": str(employee_id),
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "records_count": len(records),
            "total_standard_hours": float(total_std_hours),
            "total_actual_hours": float(total_act_hours),
            "avg_efficiency_percent": float(avg_efficiency),
            "avg_quality_percent": float(avg_quality),
            "bonus_eligible": avg_efficiency >= 100 and avg_quality >= 98,
        }
    
    async def get_team_productivity(
        self,
        employee_ids: List[UUID],
        from_date: date = None,
        to_date: date = None,
    ) -> Dict[str, Any]:
        """Get productivity for a team."""
        individual = []
        
        for emp_id in employee_ids:
            summary = await self.get_employee_productivity(emp_id, from_date, to_date)
            individual.append(summary)
        
        if not individual:
            return {"team_size": 0, "avg_efficiency": 0, "avg_quality": 0}
        
        # Calculate team averages
        total_std = sum(s.get("total_standard_hours", 0) for s in individual)
        total_act = sum(s.get("total_actual_hours", 0) for s in individual)
        
        team_efficiency = (total_std / total_act * 100) if total_act > 0 else 0
        
        return {
            "team_size": len(employee_ids),
            "avg_efficiency_percent": round(team_efficiency, 1),
            "individual_summaries": individual,
        }
    
    async def get_order_productivity(
        self,
        order_id: str,
    ) -> Dict[str, Any]:
        """Get productivity for an order."""
        query = select(EmployeeProductivity).where(
            and_(
                EmployeeProductivity.order_id == order_id,
                EmployeeProductivity.tenant_id == self.tenant_id,
            )
        )
        
        result = await self.session.execute(query)
        records = list(result.scalars().all())
        
        if not records:
            return {
                "order_id": order_id,
                "records_count": 0,
            }
        
        total_std = sum(r.standard_hours for r in records)
        total_act = sum(r.actual_hours for r in records)
        total_qty = sum(r.actual_quantity for r in records)
        total_good = sum(r.good_quantity for r in records)
        
        return {
            "order_id": order_id,
            "records_count": len(records),
            "total_standard_hours": float(total_std),
            "total_actual_hours": float(total_act),
            "efficiency_percent": float((total_std / total_act * 100) if total_act > 0 else 0),
            "quality_percent": float((total_good / total_qty * 100) if total_qty > 0 else 0),
            "employees_involved": list(set(str(r.employee_id) for r in records)),
        }










