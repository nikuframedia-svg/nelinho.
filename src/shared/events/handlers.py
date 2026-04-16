"""
ProdPlan ONE - Event Handlers
==============================

Event handlers for end-to-end integration flow.
Each handler bridges modules: Order → Schedule → Allocation → COGS → Pricing.
"""

import logging
from typing import Any, Dict
from uuid import UUID

from src.shared.kafka_client import EventEnvelope, KafkaConsumerClient, Topics, publish_event, EventBase
from src.shared.database import get_session_context

logger = logging.getLogger(__name__)


class OrderReceivedHandler:
    """
    Triggers schedule generation when a new order is received.
    Flow: ORDER_RECEIVED → SchedulingService.generate_schedule() → SCHEDULE_CREATED
    """

    async def handle(self, envelope: EventEnvelope) -> None:
        logger.info(f"OrderReceivedHandler: Processing {envelope.event_id}")

        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        order_id = payload.get("order_id")

        if not order_id:
            logger.warning("OrderReceivedHandler: missing order_id in payload")
            return

        try:
            async with get_session_context() as session:
                from src.plan.services.scheduling_service import SchedulingService
                service = SchedulingService(session, tenant_id)

                result = await service.generate_schedule(
                    order_ids=[order_id],
                    engine="heuristic",
                    rule="edd",
                )

                logger.info(
                    f"Schedule generated for order {order_id}: "
                    f"{len(result.get('operations', []))} operations, "
                    f"engine={result.get('engine_used', 'unknown')}"
                )

                # Publish SCHEDULE_CREATED event
                await publish_event(
                    Topics.SCHEDULE_CREATED,
                    EventBase(
                        event_type="SCHEDULE_CREATED",
                        tenant_id=tenant_id,
                        source_module="plan",
                        correlation_id=UUID(envelope.correlation_id) if envelope.correlation_id else None,
                        payload={
                            "order_id": order_id,
                            "operations_count": len(result.get("operations", [])),
                            "engine_used": result.get("engine_used"),
                            "makespan_hours": result.get("makespan_hours"),
                        },
                    ),
                )

        except Exception as e:
            logger.error(f"OrderReceivedHandler failed for {order_id}: {e}", exc_info=True)


class ScheduleCreatedHandler:
    """
    Triggers HR allocation when a schedule is created.
    Flow: SCHEDULE_CREATED → log allocation needs → EMPLOYEE_ALLOCATED
    """

    async def handle(self, envelope: EventEnvelope) -> None:
        logger.info(f"ScheduleCreatedHandler: Processing {envelope.event_id}")

        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        order_id = payload.get("order_id")
        operations_count = payload.get("operations_count", 0)

        try:
            async with get_session_context() as session:
                from src.hr.services.allocation_service import AllocationService
                service = AllocationService(session, tenant_id)

                # Query scheduled operations and allocate employees
                allocations = await service.auto_allocate_for_schedule(
                    order_id=order_id,
                )

                allocated_count = len(allocations) if allocations else 0
                logger.info(
                    f"Allocated {allocated_count} employees for order {order_id} "
                    f"({operations_count} operations)"
                )

                if allocated_count > 0:
                    total_hours = sum(a.get("allocated_hours", 0) for a in allocations)
                    await publish_event(
                        Topics.EMPLOYEE_ALLOCATED,
                        EventBase(
                            event_type="EMPLOYEE_ALLOCATED",
                            tenant_id=tenant_id,
                            source_module="hr",
                            correlation_id=UUID(envelope.correlation_id) if envelope.correlation_id else None,
                            payload={
                                "order_id": order_id,
                                "allocations_count": allocated_count,
                                "total_hours": total_hours,
                            },
                        ),
                    )

        except ImportError:
            logger.warning("AllocationService not available — skipping auto-allocation")
        except Exception as e:
            logger.error(f"ScheduleCreatedHandler failed: {e}", exc_info=True)


class AllocationCreatedHandler:
    """
    Triggers COGS labor component update when allocations are created.
    Flow: EMPLOYEE_ALLOCATED → COGSCalculator.calculate() → COGS_CALCULATED
    """

    async def handle(self, envelope: EventEnvelope) -> None:
        logger.info(f"AllocationCreatedHandler: Processing {envelope.event_id}")

        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        order_id = payload.get("order_id")
        total_hours = payload.get("total_hours", 0)

        try:
            async with get_session_context() as session:
                from src.profit.services.cost_service import CostService
                service = CostService(session, tenant_id)

                result = await service.calculate_cogs(order_id=order_id)

                total_cogs = result.get("total_cost", 0)
                cogs_per_unit = result.get("cost_per_unit", 0)

                logger.info(
                    f"COGS calculated for {order_id}: "
                    f"total=€{total_cogs:.2f}, per_unit=€{cogs_per_unit:.4f}, "
                    f"labor_hours={total_hours}"
                )

                await publish_event(
                    Topics.COGS_CALCULATED,
                    EventBase(
                        event_type="COGS_CALCULATED",
                        tenant_id=tenant_id,
                        source_module="profit",
                        correlation_id=UUID(envelope.correlation_id) if envelope.correlation_id else None,
                        payload={
                            "order_id": order_id,
                            "total_cogs": total_cogs,
                            "cogs_per_unit": cogs_per_unit,
                        },
                    ),
                )

        except ImportError:
            logger.warning("CostService not available — skipping COGS calculation")
        except Exception as e:
            logger.error(f"AllocationCreatedHandler failed: {e}", exc_info=True)


class LaborCostCommittedHandler:
    """Updates COGS with committed labor costs (reconciliation)."""

    async def handle(self, envelope: EventEnvelope) -> None:
        logger.info(f"LaborCostCommittedHandler: Processing {envelope.event_id}")

        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        order_id = payload.get("order_id")
        total_labor_cost = payload.get("total_labor_cost", 0)

        logger.info(f"Labor cost €{total_labor_cost:.2f} committed for {order_id}")
        # COGS reconciliation happens via the CostService on next calculation


class COGSCalculatedHandler:
    """
    Triggers pricing recommendation when COGS is calculated.
    Flow: COGS_CALCULATED → PricingService.recommend() → PRICING_RECOMMENDED
    """

    async def handle(self, envelope: EventEnvelope) -> None:
        logger.info(f"COGSCalculatedHandler: Processing {envelope.event_id}")

        tenant_id = UUID(envelope.tenant_id)
        payload = envelope.payload
        order_id = payload.get("order_id")
        total_cogs = payload.get("total_cogs", 0)

        try:
            async with get_session_context() as session:
                from src.profit.services.pricing_service import PricingService
                service = PricingService(session, tenant_id)

                result = await service.recommend_pricing(order_id=order_id)

                options_count = len(result.get("options", []))
                logger.info(
                    f"Pricing generated for {order_id}: "
                    f"{options_count} options, base COGS=€{total_cogs:.2f}"
                )

                await publish_event(
                    Topics.PRICING_RECOMMENDED,
                    EventBase(
                        event_type="PRICING_RECOMMENDED",
                        tenant_id=tenant_id,
                        source_module="profit",
                        correlation_id=UUID(envelope.correlation_id) if envelope.correlation_id else None,
                        payload={
                            "order_id": order_id,
                            "options_count": options_count,
                            "base_cogs": total_cogs,
                        },
                    ),
                )

        except ImportError:
            logger.warning("PricingService not available — skipping pricing recommendation")
        except Exception as e:
            logger.error(f"COGSCalculatedHandler failed: {e}", exc_info=True)


def register_handlers(consumer: KafkaConsumerClient) -> None:
    """Register all event handlers."""

    consumer.register_handler("ORDER_RECEIVED", OrderReceivedHandler().handle)
    consumer.register_handler("SCHEDULE_CREATED", ScheduleCreatedHandler().handle)
    consumer.register_handler("EMPLOYEE_ALLOCATED", AllocationCreatedHandler().handle)
    consumer.register_handler("LABOR_COST_COMMITTED", LaborCostCommittedHandler().handle)
    consumer.register_handler("COGS_CALCULATED", COGSCalculatedHandler().handle)

    logger.info("All event handlers registered")


async def start_event_consumer() -> KafkaConsumerClient:
    """Start the event consumer with all handlers."""

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
