"""
ProdPlan ONE - Event Handlers
==============================

Event handlers for end-to-end integration flow.
"""

import logging
from typing import Any, Dict
from uuid import UUID

from src.shared.kafka_client import EventEnvelope, KafkaConsumerClient, Topics
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)


class OrderReceivedHandler:
    """
    Handler for ORDER_RECEIVED event.
    
    Triggers schedule generation when a new order is received.
    """
    
    async def handle(self, envelope: EventEnvelope) -> None:
        """Process order received event."""
        logger.info(f"OrderReceivedHandler: Processing {envelope.event_id}")
        
        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        
        # In a full implementation, would:
        # 1. Load master data
        # 2. Generate schedule
        # 3. Trigger MRP
        
        logger.info(f"Order {payload.get('order_id')} received for tenant {tenant_id}")


class ScheduleCreatedHandler:
    """
    Handler for SCHEDULE_CREATED event.
    
    Triggers HR allocation when a schedule is created.
    """
    
    async def handle(self, envelope: EventEnvelope) -> None:
        """Process schedule created event."""
        logger.info(f"ScheduleCreatedHandler: Processing {envelope.event_id}")
        
        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        
        schedule_id = payload.get("schedule_id")
        operations_count = payload.get("operations_count", 0)
        
        # In a full implementation, would:
        # 1. Get scheduled operations
        # 2. Determine labor requirements
        # 3. Allocate employees
        
        logger.info(
            f"Schedule {schedule_id} created with {operations_count} operations"
        )


class AllocationCreatedHandler:
    """
    Handler for EMPLOYEE_ALLOCATED event.
    
    Triggers COGS calculation when allocations are created.
    """
    
    async def handle(self, envelope: EventEnvelope) -> None:
        """Process allocation created event."""
        logger.info(f"AllocationCreatedHandler: Processing {envelope.event_id}")
        
        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        
        order_id = payload.get("order_id")
        employee_id = payload.get("employee_id")
        allocated_hours = payload.get("allocated_hours", 0)
        
        # In a full implementation, would:
        # 1. Update labor allocations for COGS
        # 2. Recalculate COGS if needed
        
        logger.info(
            f"Employee {employee_id} allocated {allocated_hours}h to {order_id}"
        )


class LaborCostCommittedHandler:
    """
    Handler for LABOR_COST_COMMITTED event.
    
    Updates COGS with committed labor costs.
    """
    
    async def handle(self, envelope: EventEnvelope) -> None:
        """Process labor cost committed event."""
        logger.info(f"LaborCostCommittedHandler: Processing {envelope.event_id}")
        
        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        
        order_id = payload.get("order_id")
        total_labor_cost = payload.get("total_labor_cost", 0)
        
        # In a full implementation, would:
        # 1. Update COGS labor component
        # 2. Recalculate pricing if needed
        
        logger.info(
            f"Labor cost €{total_labor_cost:.2f} committed for {order_id}"
        )


class COGSCalculatedHandler:
    """
    Handler for COGS_CALCULATED event.
    
    Triggers pricing recommendation.
    """
    
    async def handle(self, envelope: EventEnvelope) -> None:
        """Process COGS calculated event."""
        logger.info(f"COGSCalculatedHandler: Processing {envelope.event_id}")
        
        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        
        order_id = payload.get("order_id")
        total_cogs = payload.get("total_cogs", 0)
        cogs_per_unit = payload.get("cogs_per_unit", 0)
        
        # In a full implementation, would:
        # 1. Generate pricing recommendations
        # 2. Notify sales/ERP
        
        logger.info(
            f"COGS calculated for {order_id}: €{total_cogs:.2f} (€{cogs_per_unit:.4f}/unit)"
        )


def register_handlers(consumer: KafkaConsumerClient) -> None:
    """Register all event handlers."""
    
    # Order flow
    order_handler = OrderReceivedHandler()
    consumer.register_handler("ORDER_RECEIVED", order_handler.handle)
    
    # Schedule flow
    schedule_handler = ScheduleCreatedHandler()
    consumer.register_handler("SCHEDULE_CREATED", schedule_handler.handle)
    
    # Allocation flow
    alloc_handler = AllocationCreatedHandler()
    consumer.register_handler("EMPLOYEE_ALLOCATED", alloc_handler.handle)
    
    labor_handler = LaborCostCommittedHandler()
    consumer.register_handler("LABOR_COST_COMMITTED", labor_handler.handle)
    
    # COGS flow
    cogs_handler = COGSCalculatedHandler()
    consumer.register_handler("COGS_CALCULATED", cogs_handler.handle)
    
    logger.info("All event handlers registered")


async def start_event_consumer() -> KafkaConsumerClient:
    """Start the event consumer with all handlers."""
    
    # Subscribe to all relevant topics
    topics = [
        Topics.SCHEDULE_CREATED,
        Topics.EMPLOYEE_ALLOCATED,
        Topics.LABOR_COST_COMMITTED,
        Topics.COGS_CALCULATED,
        Topics.PRICING_RECOMMENDED,
    ]
    
    consumer = KafkaConsumerClient(topics, group_id="prodplan-one-handlers")
    register_handlers(consumer)
    
    await consumer.start()
    return consumer










