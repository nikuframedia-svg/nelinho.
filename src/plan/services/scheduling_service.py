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

from src.governance.audit_service import audit_change
from src.plan.models.schedule import ProductionSchedule, ScheduleStatus
from src.plan.engines.scheduling_adapter import (
    SchedulingAdapter,
    SchedulingOperation,
    SchedulingMachine,
    SchedulerEngine,
    DispatchRule,
)
import logging

from src.shared.kafka_client import EventBase, publish_event, Topics
from src.shared.events import ScheduleCreatedEvent
from src.shared.time import local_now_naive, utc_now_naive

logger = logging.getLogger(__name__)


class InvalidScheduleTransition(ValueError):
    """Raised by ``SchedulingService.update_status`` when the requested
    status is not reachable from the current row's status (FASE 3.5 /
    HIGH-41). API callers should map this to HTTP 409 Conflict.
    """


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
        horizon_start = horizon_start or local_now_naive()
        horizon_end = horizon_start + timedelta(weeks=planning_weeks)
        planning_run_id = f"plan-{uuid4().hex[:8]}"

        # Sprint Q.13.A — close CRIT-27. Quantity per order is now
        # propagated to ProductionSchedule.quantity (was hardcoded
        # Decimal("1") which broke margin calculation for any qty>1
        # order). Caller hands `orders` with `{order_id, qty, due_date}`;
        # we build a lookup once and read it inside the per-op loop.
        order_quantities: Dict[str, Decimal] = {}
        for o in orders:
            oid = str(o.get("order_id") or o.get("id") or "")
            qty = o.get("qty") or o.get("quantity") or 1
            try:
                order_quantities[oid] = Decimal(str(qty))
            except (ValueError, TypeError):
                order_quantities[oid] = Decimal("1")

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
        
        # FASE 1B.4 (CRIT-23) — set of op IDs flagged infeasible by the
        # decoder, so we can attach a reason field on each row.
        infeasible_ids = set(getattr(result, "infeasible_op_ids", []) or [])

        # Save to database
        for op_data in result.operations:
            qrisk = op_data.get("quality_risk")
            quality_risk_score = (
                Decimal(str(qrisk)).quantize(Decimal("0.0001"))
                if qrisk is not None else None
            )
            op_id_str = str(op_data.get("operation_id", ""))

            # FASE 1B.5 (CRIT-16) — best-effort machine_id resolution.
            # The CPO decoder may emit either a UUID-string (when callers
            # pass real machine IDs) or a synthetic code like "MANUAL" /
            # "LAM-01". The DB column is a UUID FK to core.machines, so
            # we accept the value only when it parses as UUID. Synthetic
            # codes are dropped with a WARN — better than a crashing FK.
            machine_id_resolved: Optional[UUID] = None
            raw_machine = op_data.get("machine_id")
            if raw_machine:
                try:
                    machine_id_resolved = UUID(str(raw_machine))
                except (ValueError, TypeError):
                    logger.warning(
                        "scheduling_service: op %s machine_id=%r is not a UUID — "
                        "leaving FK NULL. Provide UUID-keyed machines in the "
                        "request to populate this field.",
                        op_id_str, raw_machine,
                    )

            # Sprint Q.13.A — CRIT-27 fixed. Quantity propagates from the
            # caller's orders list via the lookup built at the top of
            # generate_schedule. Defensive fallback Decimal("1") covers
            # the partial-input case where an order is missing from the
            # input dict (legacy callers); WARN logged so it doesn't go
            # silent.
            order_id_str = str(op_data["order_id"])
            row_quantity = order_quantities.get(order_id_str)
            if row_quantity is None:
                logger.warning(
                    "scheduling_service: order_id=%s missing in input orders dict — "
                    "falling back to qty=1. Margin calculations may be wrong.",
                    order_id_str,
                )
                row_quantity = Decimal("1")

            schedule = ProductionSchedule(
                id=uuid4(),
                tenant_id=self.tenant_id,
                order_id=op_data["order_id"],
                product_id=UUID(op_data["product_id"]) if op_data.get("product_id") else None,
                operation_id=UUID(op_id_str) if op_id_str else None,
                operation_sequence=int(op_data.get("sequence", 0)),
                machine_id=machine_id_resolved,
                quantity=row_quantity,
                scheduled_start_date=datetime.fromisoformat(op_data["start_time"]).date(),
                scheduled_end_date=datetime.fromisoformat(op_data["end_time"]).date(),
                scheduled_duration_hours=Decimal(str(op_data["duration_minutes"] / 60)),
                status=ScheduleStatus.SCHEDULED,
                planning_run_id=planning_run_id,
                engine_used=result.engine_used or engine.value,
                # FASE 1B.4 (CRIT-23) — surface CPO decoder output to DB
                rule_used=result.rule_used,
                mold_batch_id=op_data.get("mold_batch_id"),
                infeasible_reason=(
                    "infeasible_per_decoder" if op_id_str in infeasible_ids else None
                ),
                quality_risk_score=quality_risk_score,
                quality_risk_scored_at=(
                    utc_now_naive() if quality_risk_score is not None else None
                ),
            )
            self.session.add(schedule)
            await audit_change(
                self.session,
                tenant_id=self.tenant_id,
                entity_type="production_schedule",
                entity_id=schedule.id,
                action="INSERT",
                old_values=None,
                new_values={
                    "order_id": str(schedule.order_id),
                    "operation_sequence": schedule.operation_sequence,
                    "planning_run_id": planning_run_id,
                    "status": ScheduleStatus.SCHEDULED.value,
                    "scheduled_start_date": schedule.scheduled_start_date.isoformat(),
                    "scheduled_end_date": schedule.scheduled_end_date.isoformat(),
                    "engine_used": schedule.engine_used,
                },
                reason="Q.66.B.3 — operacao calendarizada",
            )

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
    
    async def update_dates(
        self,
        schedule_id: UUID,
        *,
        new_start: Optional[datetime] = None,
        new_end: Optional[datetime] = None,
    ) -> Optional[ProductionSchedule]:
        """Reschedule an existing ProductionSchedule row to new dates.

        Sprint Q.9 Onda 2.3 — replaces the audit-only stub in
        `ActionExecutor._handle_reschedule_order`. Caller (the action
        executor) has already validated that the decision was approved;
        this method just performs the write + emits SCHEDULE_UPDATED.

        Returns the row with the new dates applied, or None when the
        id doesn't match a row in the current tenant. Either side
        (start, end) can be None to leave that bound unchanged.
        """
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

        if new_start is not None:
            schedule.scheduled_start_date = new_start
        if new_end is not None:
            schedule.scheduled_end_date = new_end

        await self.session.flush()

        try:
            await publish_event(
                Topics.SCHEDULE_UPDATED,
                EventBase(
                    event_type="SCHEDULE_RESCHEDULED",
                    tenant_id=self.tenant_id,
                    source_module="plan",
                    payload={
                        "schedule_id": str(schedule.id),
                        "order_id": str(schedule.order_id) if schedule.order_id else None,
                        "scheduled_start_date": (
                            schedule.scheduled_start_date.isoformat()
                            if schedule.scheduled_start_date else None
                        ),
                        "scheduled_end_date": (
                            schedule.scheduled_end_date.isoformat()
                            if schedule.scheduled_end_date else None
                        ),
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — bus outage non-fatal
            logger.warning("SCHEDULE_RESCHEDULED publish failed for %s: %s", schedule.id, exc)

        return schedule

    # FASE 3.5 (HIGH-41) — schedule status state machine. Allowed
    # transitions per the NELO domain: a row starts at SCHEDULED
    # (created via generate_schedule), can be CANCELLED at any non-final
    # state, and progresses linearly through IN_PROGRESS → COMPLETED.
    # DRAFT is reserved for legacy/manual creations that haven't been
    # scheduled yet. Without this, an operator could mark an op
    # COMPLETED without ever having had IN_PROGRESS, and the historical
    # actuals would be inconsistent.
    _STATUS_TRANSITIONS: Dict[ScheduleStatus, set] = {
        ScheduleStatus.DRAFT: {ScheduleStatus.SCHEDULED, ScheduleStatus.CANCELLED},
        ScheduleStatus.SCHEDULED: {
            ScheduleStatus.IN_PROGRESS,
            ScheduleStatus.CANCELLED,
            ScheduleStatus.SCHEDULED,  # idempotent re-schedule
        },
        ScheduleStatus.IN_PROGRESS: {
            ScheduleStatus.COMPLETED,
            ScheduleStatus.CANCELLED,
            ScheduleStatus.IN_PROGRESS,  # idempotent updates of actuals
        },
        ScheduleStatus.COMPLETED: set(),  # terminal
        ScheduleStatus.CANCELLED: set(),  # terminal
    }

    async def update_status(
        self,
        schedule_id: UUID,
        status: ScheduleStatus,
        actual_start: datetime = None,
        actual_end: datetime = None,
        actual_quantity: Decimal = None,
    ) -> Optional[ProductionSchedule]:
        """Update schedule status with actuals.

        Raises ``InvalidScheduleTransition`` (subclass of ``ValueError``)
        when ``status`` is not reachable from the current row's status.
        Callers in API layers should map this to HTTP 409 Conflict.
        """
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

        # FASE 3.5 (HIGH-41) — gate the transition.
        current = schedule.status
        if not isinstance(current, ScheduleStatus):
            # Some legacy rows have status stored as plain string.
            try:
                current = ScheduleStatus(current)
            except ValueError:
                current = ScheduleStatus.SCHEDULED  # safe default
        allowed = self._STATUS_TRANSITIONS.get(current, set())
        if status != current and status not in allowed:
            raise InvalidScheduleTransition(
                f"Cannot transition schedule {schedule.id} from {current.value} "
                f"to {status.value if hasattr(status, 'value') else status}; "
                f"allowed: {sorted(s.value for s in allowed)}"
            )

        schedule.status = status
        if actual_start:
            schedule.actual_start = actual_start
        if actual_end:
            schedule.actual_end = actual_end
        if actual_quantity is not None:
            schedule.actual_quantity = actual_quantity

        await self.session.flush()

        try:
            await publish_event(
                Topics.SCHEDULE_UPDATED,
                EventBase(
                    event_type="SCHEDULE_UPDATED",
                    tenant_id=self.tenant_id,
                    source_module="plan",
                    payload={
                        "schedule_id": str(schedule.id),
                        "order_id": str(schedule.order_id) if schedule.order_id else None,
                        "status": status.value if hasattr(status, "value") else str(status),
                        "actual_start": schedule.actual_start.isoformat() if schedule.actual_start else None,
                        "actual_end": schedule.actual_end.isoformat() if schedule.actual_end else None,
                        "actual_quantity": float(schedule.actual_quantity) if schedule.actual_quantity is not None else None,
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — bus outage is non-fatal
            logger.warning("SCHEDULE_UPDATED publish failed for %s: %s", schedule.id, exc)

        return schedule










