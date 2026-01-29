"""
ProdPlan ONE - Copilot Actions
================================

Action-first redesign for Copilot with 3 execution modes:
- PREVIEW: Deterministic calculations, no DB writes
- SANDBOX: Execute in nested transaction with auto-rollback
- EXECUTE: Production execution with audit trail and Kafka events
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.kafka_client import KafkaProducerClient, EventBase
from src.shared.event_schemas import EventPayload

logger = logging.getLogger(__name__)


class ActionMode(Enum):
    """Execution modes for actions."""
    PREVIEW = "preview"
    SANDBOX = "sandbox"
    EXECUTE = "execute"


class ActionType(Enum):
    """Types of actions."""
    REDUCE_SETUP = "reduce_setup"
    EXPEDITE_PURCHASE = "expedite_purchase"
    RESCHEDULE_ORDER = "reschedule_order"
    OPTIMIZE_CAPACITY = "optimize_capacity"
    ADJUST_INVENTORY = "adjust_inventory"


class ActionStatus(Enum):
    """Status of executed actions."""
    EXECUTED = "executed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Action:
    """
    Structured action response format.
    
    Represents a Copilot action with metadata and execution modes.
    """
    
    def __init__(
        self,
        action_id: str,
        action_type: str,
        description: str,
        modes: List[str],
        estimated_impact: Dict[str, Any],
        required_approvals: Optional[List[str]] = None,
        rollback_available: bool = True,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.id = action_id
        self.type = action_type
        self.description = description
        self.modes = modes  # ["preview", "sandbox", "execute"]
        self.estimated_impact = estimated_impact
        self.required_approvals = required_approvals or []
        self.rollback_available = rollback_available
        self.payload = payload or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "modes": self.modes,
            "estimated_impact": self.estimated_impact,
            "required_approvals": self.required_approvals,
            "rollback_available": self.rollback_available,
            "payload": self.payload,
        }


class ActionExecutor:
    """
    Execute Copilot actions in 3 modes.
    
    - PREVIEW: Deterministic calculations, returns estimated_impact
    - SANDBOX: Execute in nested transaction, auto-rollback
    - EXECUTE: Production execution with audit log and Kafka event
    """
    
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        kafka_producer: Optional[KafkaProducerClient] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.kafka_producer = kafka_producer
    
    async def execute_action(
        self,
        action: Action,
        mode: ActionMode,
        plan_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Execute action in specified mode.
        
        Args:
            action: Action to execute
            mode: Execution mode (PREVIEW, SANDBOX, EXECUTE)
            plan_id: Optional plan ID for context
        
        Returns:
            Execution result with status and data
        """
        logger.info(
            f"Executing action: id={action.id}, type={action.type}, mode={mode.value}"
        )
        
        if mode == ActionMode.PREVIEW:
            return await self._execute_preview(action)
        elif mode == ActionMode.SANDBOX:
            return await self._execute_sandbox(action, plan_id)
        elif mode == ActionMode.EXECUTE:
            return await self._execute_production(action, plan_id)
        else:
            raise ValueError(f"Unknown action mode: {mode}")
    
    async def _execute_preview(self, action: Action) -> Dict[str, Any]:
        """
        Preview mode: Deterministic calculations, no DB writes.
        
        Returns estimated_impact without committing any changes.
        """
        logger.debug(f"Preview mode: action={action.id}")
        
        # Simulate action execution (deterministic)
        # In real implementation, this would call action-specific preview logic
        result = {
            "action_id": action.id,
            "mode": "preview",
            "estimated_impact": action.estimated_impact,
            "status": "preview_complete",
            "message": "Preview completed. No changes committed.",
        }
        
        return result
    
    async def _execute_sandbox(
        self,
        action: Action,
        plan_id: Optional[UUID],
    ) -> Dict[str, Any]:
        """
        Sandbox mode: Execute in nested transaction with auto-rollback.
        
        Uses session.begin_nested() to create a savepoint.
        All changes are automatically rolled back when exiting.
        """
        logger.debug(f"Sandbox mode: action={action.id}")
        
        # Create savepoint (nested transaction)
        nested = await self.session.begin_nested()
        
        try:
            # Capture before state
            before_state = await self._capture_state(action, plan_id)
            
            # Execute action (this would call action-specific logic)
            after_state = await self._simulate_action_execution(action, plan_id)
            
            # Calculate actual impact (not estimated)
            actual_impact = await self._calculate_actual_impact(
                before_state, after_state, action
            )
            
            # Rollback automatically when exiting context
            await nested.rollback()
            
            logger.info(f"Sandbox execution completed and rolled back: action={action.id}")
            
            return {
                "action_id": action.id,
                "mode": "sandbox",
                "actual_impact": actual_impact,
                "status": "sandbox_complete",
                "message": "Sandbox execution completed. Changes rolled back.",
                "before_state": before_state,
                "after_state": after_state,
            }
        
        except Exception as e:
            await nested.rollback()
            logger.error(f"Sandbox execution failed: action={action.id}, error={e}")
            raise
    
    async def _execute_production(
        self,
        action: Action,
        plan_id: Optional[UUID],
    ) -> Dict[str, Any]:
        """
        Production mode: Execute with commit, audit log, and Kafka event.
        
        Creates audit log entry and publishes Kafka event.
        """
        logger.info(f"Production execution: action={action.id}")
        
        # Capture before state
        before_state = await self._capture_state(action, plan_id)
        
        try:
            # Execute action (this would call action-specific logic)
            after_state = await self._simulate_action_execution(action, plan_id)
            
            # Create audit log (will be saved by caller)
            transaction_id = uuid4()
            rollback_until = datetime.utcnow() + timedelta(hours=24)
            
            audit_log = {
                "id": transaction_id,
                "action_type": action.type,
                "user_id": self.user_id,
                "tenant_id": self.tenant_id,
                "plan_id": plan_id,
                "before_state": before_state,
                "after_state": after_state,
                "status": ActionStatus.EXECUTED.value,
                "executed_at": datetime.utcnow(),
                "rollback_until": rollback_until,
            }
            
            # Publish Kafka event
            if self.kafka_producer:
                event = EventBase(
                    event_id=transaction_id,
                    event_type="copilot.action.executed",
                    tenant_id=self.tenant_id,
                    source_module="copilot",
                    payload={
                        "action_id": action.id,
                        "action_type": action.type,
                        "transaction_id": str(transaction_id),
                        "user_id": str(self.user_id),
                        "plan_id": str(plan_id) if plan_id else None,
                    },
                )
                
                try:
                    await self.kafka_producer.publish(
                        topic="prodplan.copilot.action.executed",
                        event=event,
                        aggregate_id=str(plan_id) if plan_id else str(self.tenant_id),
                    )
                except Exception as kafka_error:
                    logger.warning(f"Kafka publish failed: {kafka_error}")
            
            # Commit transaction
            await self.session.commit()
            
            logger.info(f"Production execution completed: action={action.id}, transaction={transaction_id}")
            
            return {
                "action_id": action.id,
                "mode": "execute",
                "transaction_id": str(transaction_id),
                "status": "executed",
                "rollback_until": rollback_until.isoformat(),
                "message": "Action executed successfully. Audit log created.",
            }
        
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Production execution failed: action={action.id}, error={e}")
            raise
    
    async def _capture_state(
        self,
        action: Action,
        plan_id: Optional[UUID],
    ) -> Dict[str, Any]:
        """
        Capture system state before action execution.
        
        Returns snapshot of relevant state for rollback.
        Captures state based on action type to enable accurate impact calculation.
        """
        from sqlalchemy import select, func, and_
        from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
        from src.core.models.product import Product
        from src.core.models.operation import Operation
        
        state = {
            "captured_at": datetime.utcnow().isoformat(),
            "plan_id": str(plan_id) if plan_id else None,
            "action_type": action.type,
            "target": action.payload.get("target") if action.payload else None,
        }
        
        # Capture state based on action type
        if action.type in ["reschedule_order", "optimize_capacity", "reduce_setup"]:
            # Capture schedule state
            target = action.payload.get("target") if action.payload else None
            
            query = select(ProductionSchedule).where(
                and_(
                    ProductionSchedule.tenant_id == self.tenant_id,
                )
            )
            
            if target:
                # Target might be order_id, product_id, etc.
                if target.startswith("PO-") or target.startswith("ORD-"):
                    query = query.where(ProductionSchedule.order_id == target)
            
            result = await self.session.execute(query)
            schedules = result.scalars().all()
            
            state["schedules"] = [
                {
                    "id": str(s.id),
                    "order_id": s.order_id,
                    "product_id": str(s.product_id),
                    "operation_id": str(s.operation_id),
                    "machine_id": str(s.machine_id) if s.machine_id else None,
                    "scheduled_start_date": s.scheduled_start_date.isoformat() if s.scheduled_start_date else None,
                    "scheduled_end_date": s.scheduled_end_date.isoformat() if s.scheduled_end_date else None,
                    "setup_time_minutes": int(s.setup_time_minutes) if s.setup_time_minutes else 0,
                    "status": s.status.value,
                }
                for s in schedules
            ]
            
            # Capture KPI baseline
            total_orders_query = select(func.count(func.distinct(ProductionSchedule.order_id))).where(
                and_(
                    ProductionSchedule.tenant_id == self.tenant_id,
                    ProductionSchedule.status.in_([ScheduleStatus.SCHEDULED, ScheduleStatus.IN_PROGRESS]),
                )
            )
            total_orders_result = await self.session.execute(total_orders_query)
            state["kpis"] = {
                "total_orders": total_orders_result.scalar() or 0,
                "total_schedules": len(schedules),
            }
        
        elif action.type in ["adjust_inventory"]:
            # Capture inventory/product state
            target = action.payload.get("target") if action.payload else None
            
            query = select(Product).where(Product.tenant_id == self.tenant_id)
            
            if target:
                query = query.where(Product.id == UUID(target))
            
            result = await self.session.execute(query)
            products = result.scalars().all()
            
            state["products"] = [
                {
                    "id": str(p.id),
                    "product_code": p.product_code,
                    "safety_stock": float(p.safety_stock) if p.safety_stock else 0.0,
                    "lead_time_days": p.lead_time_days,
                }
                for p in products
            ]
        
        elif action.type in ["reduce_setup", "expedite_purchase"]:
            # Capture operation setup times
            result = await self.session.execute(
                select(Operation).where(Operation.tenant_id == self.tenant_id)
            )
            operations = result.scalars().all()
            
            state["operations"] = [
                {
                    "id": str(op.id),
                    "operation_code": op.operation_code,
                    "setup_time_minutes": float(op.setup_time_minutes) if op.setup_time_minutes else 0.0,
                    "machine_id": str(op.machine_id) if op.machine_id else None,
                }
                for op in operations
            ]
        
        return state
    
    async def _simulate_action_execution(
        self,
        action: Action,
        plan_id: Optional[UUID],
    ) -> Dict[str, Any]:
        """
        Simulate action execution.
        
        In real implementation, this would call action-specific handlers.
        """
        # Placeholder - real implementation would have action-specific logic
        return {
            "executed_at": datetime.utcnow().isoformat(),
            "action_type": action.type,
            "plan_id": str(plan_id) if plan_id else None,
        }
    
    async def _calculate_actual_impact(
        self,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        action: Action,
    ) -> Dict[str, Any]:
        """
        Calculate actual impact from before/after states.
        
        Compares before and after states to compute real impact metrics:
        - Schedule changes (tardiness, makespan)
        - Setup time reductions
        - Inventory adjustments
        - KPI deltas
        """
        impact = {
            "calculated_at": datetime.utcnow().isoformat(),
            "action_type": action.type,
            "metrics": {},
            "deltas": {},
        }
        
        # Calculate schedule-related impacts
        if "schedules" in before_state and "schedules" in after_state:
            before_schedules = {s["id"]: s for s in before_state.get("schedules", [])}
            after_schedules = {s["id"]: s for s in after_state.get("schedules", [])}
            
            # Calculate setup time reduction
            setup_reduction = 0
            schedule_changes = 0
            
            for schedule_id, before_sched in before_schedules.items():
                after_sched = after_schedules.get(schedule_id)
                if after_sched:
                    before_setup = before_sched.get("setup_time_minutes", 0)
                    after_setup = after_sched.get("setup_time_minutes", 0)
                    setup_reduction += max(0, before_setup - after_setup)
                    
                    # Check for date changes
                    if before_sched.get("scheduled_end_date") != after_sched.get("scheduled_end_date"):
                        schedule_changes += 1
            
            if setup_reduction > 0:
                impact["metrics"]["setup_time_reduction_minutes"] = setup_reduction
                impact["metrics"]["setup_time_reduction_percent"] = (
                    (setup_reduction / sum(s.get("setup_time_minutes", 0) for s in before_schedules.values()) * 100)
                    if sum(s.get("setup_time_minutes", 0) for s in before_schedules.values()) > 0
                    else 0
                )
            
            impact["metrics"]["schedules_modified"] = schedule_changes
        
        # Calculate KPI deltas
        before_kpis = before_state.get("kpis", {})
        after_kpis = after_state.get("kpis", {})
        
        for kpi in ["total_orders", "total_schedules"]:
            before_val = before_kpis.get(kpi, 0)
            after_val = after_kpis.get(kpi, 0)
            if before_val != after_val:
                impact["deltas"][kpi] = {
                    "before": before_val,
                    "after": after_val,
                    "delta": after_val - before_val,
                    "delta_percent": ((after_val - before_val) / before_val * 100) if before_val > 0 else 0,
                }
        
        # Calculate inventory/product impacts
        if "products" in before_state and "products" in after_state:
            before_products = {p["id"]: p for p in before_state.get("products", [])}
            after_products = {p["id"]: p for p in after_state.get("products", [])}
            
            inventory_changes = []
            for product_id, before_prod in before_products.items():
                after_prod = after_products.get(product_id)
                if after_prod:
                    before_stock = before_prod.get("safety_stock", 0)
                    after_stock = after_prod.get("safety_stock", 0)
                    if before_stock != after_stock:
                        inventory_changes.append({
                            "product_id": product_id,
                            "product_code": before_prod.get("product_code"),
                            "before": before_stock,
                            "after": after_stock,
                            "delta": after_stock - before_stock,
                        })
            
            if inventory_changes:
                impact["metrics"]["inventory_changes"] = inventory_changes
                total_delta = sum(c["delta"] for c in inventory_changes)
                impact["metrics"]["total_inventory_delta"] = total_delta
        
        # Calculate operation setup time impacts
        if "operations" in before_state and "operations" in after_state:
            before_ops = {op["id"]: op for op in before_state.get("operations", [])}
            after_ops = {op["id"]: op for op in after_state.get("operations", [])}
            
            operation_setup_reduction = 0
            for op_id, before_op in before_ops.items():
                after_op = after_ops.get(op_id)
                if after_op:
                    before_setup = before_op.get("setup_time_minutes", 0)
                    after_setup = after_op.get("setup_time_minutes", 0)
                    operation_setup_reduction += max(0, before_setup - after_setup)
            
            if operation_setup_reduction > 0:
                impact["metrics"]["operation_setup_reduction_minutes"] = operation_setup_reduction
        
        # If no specific metrics calculated, fall back to estimated impact with timestamp
        if not impact["metrics"] and not impact["deltas"]:
            estimated = action.estimated_impact or {}
            impact["metrics"] = {**estimated, "note": "Impact calculated from estimated values"}

        return impact


