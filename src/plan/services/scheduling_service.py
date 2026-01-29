"""
ProdPlan ONE - Scheduling Service
==================================

Business logic for production scheduling.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.plan.engines.scheduling_adapter import (
    SchedulingAdapter,
    SchedulingOperation,
    SchedulingMachine,
    SchedulerEngine,
    DispatchRule,
)
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import ScheduleCreatedEvent


class SchedulingService:
    """
    Service for production scheduling.
    
    Orchestrates schedule generation using the scheduling engine.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._adapter = SchedulingAdapter()
    
    async def generate_schedule(
        self,
        orders: List[Dict[str, Any]],
        machines: List[Dict[str, Any]],
        operations: List[Dict[str, Any]],
        engine: SchedulerEngine = SchedulerEngine.HEURISTIC,
        rule: DispatchRule = DispatchRule.EDD,
        horizon_start: datetime = None,
        planning_weeks: int = 4,
    ) -> Dict[str, Any]:
        """
        Generate production schedule.
        
        Args:
            orders: List of production orders with qty, due_date
            machines: List of available machines
            operations: List of operations (routing) for each order
            engine: Scheduling engine to use
            rule: Dispatch rule (for heuristic)
            horizon_start: Start of planning horizon
            planning_weeks: Number of weeks to plan
        
        Returns:
            Scheduling result with operations and KPIs
        """
        horizon_start = horizon_start or datetime.now()
        horizon_end = horizon_start + timedelta(weeks=planning_weeks)
        planning_run_id = f"plan-{uuid4().hex[:8]}"
        
        # Configure adapter
        self._adapter.configure(engine=engine, rule=rule)
        
        # Convert to scheduling format
        sched_operations = []
        for op in operations:
            sched_operations.append(SchedulingOperation(
                operation_id=str(op.get("operation_id", uuid4())),
                order_id=str(op.get("order_id", "")),
                product_id=str(op.get("product_id", "")),
                sequence=int(op.get("sequence", 0)),
                operation_code=str(op.get("operation_code", "")),
                duration_minutes=float(op.get("duration_minutes", 0)),
                machine_id=str(op.get("machine_id", "")) if op.get("machine_id") else None,
                due_date=op.get("due_date"),
                priority=float(op.get("priority", 1.0)),
            ))
        
        sched_machines = []
        for m in machines:
            sched_machines.append(SchedulingMachine(
                machine_id=str(m.get("machine_id", "")),
                name=str(m.get("name", "")),
                capacity=int(m.get("capacity", 1)),
            ))
        
        # Run scheduling
        result = self._adapter.schedule(
            operations=sched_operations,
            machines=sched_machines,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
        )
        
        # Save to database
        for op_data in result.operations:
            schedule = ProductionSchedule(
                tenant_id=self.tenant_id,
                order_id=op_data["order_id"],
                product_id=UUID(op_data["product_id"]) if op_data.get("product_id") else None,
                operation_id=UUID(op_data["operation_id"]) if op_data.get("operation_id") else None,
                operation_sequence=0,
                machine_id=None,  # Would need to resolve
                quantity=Decimal("1"),  # Would come from order
                scheduled_start_date=datetime.fromisoformat(op_data["start_time"]).date(),
                scheduled_end_date=datetime.fromisoformat(op_data["end_time"]).date(),
                scheduled_duration_hours=Decimal(str(op_data["duration_minutes"] / 60)),
                status=ScheduleStatus.SCHEDULED,
                planning_run_id=planning_run_id,
                engine_used=engine.value,
            )
            self.session.add(schedule)
        
        await self.session.flush()
        
        # Publish event
        await publish_event(
            Topics.SCHEDULE_CREATED,
            ScheduleCreatedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "schedule_id": planning_run_id,
                    "order_ids": list(set(op["order_id"] for op in result.operations)),
                    "operations_count": len(result.operations),
                    "planning_horizon_start": horizon_start.isoformat(),
                    "planning_horizon_end": horizon_end.isoformat(),
                    "engine_used": engine.value,
                },
            ),
        )
        
        return {
            "planning_run_id": planning_run_id,
            "status": "completed",
            "engine_used": result.engine_used,
            "rule_used": result.rule_used,
            "operations_scheduled": len(result.operations),
            "kpis": {
                "makespan_hours": result.makespan_hours,
                "total_tardiness_hours": result.total_tardiness_hours,
                "num_late_orders": result.num_late_orders,
                "avg_utilization": result.avg_utilization,
            },
            "operations": result.operations,
            "warnings": result.warnings,
        }
    
    async def get_schedule(
        self,
        planning_run_id: str = None,
        order_id: str = None,
        status: ScheduleStatus = None,
        from_date: date = None,
        to_date: date = None,
    ) -> List[ProductionSchedule]:
        """Get scheduled operations with filtering."""
        query = select(ProductionSchedule).where(
            ProductionSchedule.tenant_id == self.tenant_id
        )
        
        if planning_run_id:
            query = query.where(ProductionSchedule.planning_run_id == planning_run_id)
        if order_id:
            query = query.where(ProductionSchedule.order_id == order_id)
        if status:
            query = query.where(ProductionSchedule.status == status)
        if from_date:
            query = query.where(ProductionSchedule.scheduled_start_date >= from_date)
        if to_date:
            query = query.where(ProductionSchedule.scheduled_start_date <= to_date)
        
        query = query.order_by(
            ProductionSchedule.scheduled_start_date,
            ProductionSchedule.order_id,
            ProductionSchedule.operation_sequence,
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_status(
        self,
        schedule_id: UUID,
        status: ScheduleStatus,
        actual_start: datetime = None,
        actual_end: datetime = None,
        actual_quantity: Decimal = None,
    ) -> Optional[ProductionSchedule]:
        """Update schedule status with actuals."""
        result = await self.session.execute(
            select(ProductionSchedule).where(
                and_(
                    ProductionSchedule.id == schedule_id,
                    ProductionSchedule.tenant_id == self.tenant_id,
                )
            )
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            return None
        
        schedule.status = status
        if actual_start:
            schedule.actual_start = actual_start
        if actual_end:
            schedule.actual_end = actual_end
        if actual_quantity is not None:
            schedule.actual_quantity = actual_quantity
        
        await self.session.flush()
        return schedule










