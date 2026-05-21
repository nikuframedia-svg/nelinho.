"""
ProdPlan ONE - Outbox Dispatcher
=================================

Dispatches pending events from outbox table to Kafka.

Job that runs every 5 seconds (or configurable interval):
1. Fetch pending events from event_outbox
2. Publish to Kafka via producer
3. Mark as published or failed
4. Move to DLQ after 5 retry attempts
"""

import asyncio
import logging
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .outbox_models import EventOutbox, EventDLQ
from .kafka_client import KafkaProducerClient, EventBase
from .event_schemas import validate_event_payload
from .event_contracts import resolve_topic

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """
    Dispatch pending events from outbox to Kafka.
    
    Usage:
        dispatcher = OutboxDispatcher(
            db_session_factory=async_session_factory,
            kafka_producer=producer,
        )
        await dispatcher.run()  # Run once (call in a loop for periodic execution)
    """
    
    def __init__(
        self,
        db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        kafka_producer: KafkaProducerClient,
        batch_size: int = 100,
    ):
        self.db_session_factory = db_session_factory
        self.kafka_producer = kafka_producer
        self.batch_size = batch_size
    
    async def run(self):
        """
        Run dispatcher job (meant to run every 5 seconds).
        
        Fetches pending events and publishes to Kafka.
        """
        async with self.db_session_factory() as session:
            await self._dispatch_pending_events(session)
    
    async def _dispatch_pending_events(self, session: AsyncSession):
        """
        Fetch pending events and publish to Kafka.
        
        Args:
            session: Database session
        """
        # Sprint S5 / Π5: row-level lock (FOR UPDATE SKIP LOCKED) so multiple
        # dispatcher instances can run in parallel without publishing the same
        # event twice. Postgres-only; the test suite uses fakes that ignore
        # `with_for_update`, so this is a no-op there.
        #
        # Q.66.E.1: respeitar `next_retry_at`. Events sem next_retry_at (novos
        # ou pre-Q.66.E.1) sao sempre elegiveis. Events com next_retry_at no
        # futuro ficam fora deste batch — o proximo ciclo apanha-os quando o
        # backoff expirar. Isto trava o busy-loop quando Kafka oscila.
        stmt = (
            select(EventOutbox)
            .where(EventOutbox.status == "pending")
            .where(
                or_(
                    EventOutbox.next_retry_at.is_(None),
                    EventOutbox.next_retry_at <= func.now(),
                )
            )
            .order_by(EventOutbox.created_at.asc())
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
        )
        
        result = await session.execute(stmt)
        pending_events = result.scalars().all()
        
        if not pending_events:
            return
        
        logger.info(f"Outbox dispatch start: {len(pending_events)} pending events")
        
        for event in pending_events:
            try:
                # Validate payload
                try:
                    validated_payload = validate_event_payload(event.event_type, event.payload)
                except Exception as e:
                    logger.warning(f"Invalid payload for event {event.id}: {e}")
                    # Move directly to DLQ if payload invalid
                    event.status = "failed"
                    event.error_message = f"Invalid payload: {e!s}"
                    dlq_entry = EventDLQ(
                        event_outbox_id=event.id,
                        error_message=f"Invalid payload: {e!s}",
                        retry_attempt=event.retry_count,
                    )
                    session.add(dlq_entry)
                    continue
                
                # Create EventBase from outbox event
                # Use outbox ID as event_id for traceability
                from uuid import UUID as PyUUID
                payload_dict = validated_payload.model_dump() if hasattr(validated_payload, 'model_dump') else event.payload
                event_base = EventBase(
                    event_id=PyUUID(event.id),  # Use outbox ID for traceability
                    event_type=event.event_type,
                    tenant_id=event.tenant_id,
                    source_module=event.aggregate_type,
                    payload=payload_dict,
                )
                
                # Sprint S4 / Φ1: route via the canonical event_type→topic
                # mapping. The previous ad-hoc concatenation produced topics
                # consumers never subscribed to — events went into the void.
                topic = resolve_topic(event.event_type)
                
                # Publish to Kafka
                pub_result = await self.kafka_producer.publish(
                    topic=topic,
                    event=event_base,
                    aggregate_id=str(event.aggregate_id),
                    idempotency_key=str(event.id),  # Use outbox ID as idempotency key
                )
                
                # Mark as published
                event.status = "published"
                event.published_at = datetime.utcnow()
                
                logger.info(
                    f"Event dispatched: id={event.id}, type={event.event_type}, "
                    f"kafka_offset={pub_result.get('kafka_offset')}"
                )
            
            except Exception as e:
                # Q.66.E.1: backoff exponencial. Calcular ANTES de incrementar
                # retry_count para que:
                #   retry_count=0 (1a falha) -> 2^0 = 1s
                #   retry_count=1 (2a falha) -> 2^1 = 2s
                #   retry_count=2            -> 4s
                #   retry_count=4            -> 16s
                #   retry_count=8            -> 256s
                #   retry_count>=9           -> capped a 300s (5min)
                # Sem isto, Kafka instavel = dispatcher loop 5x em ~25s e
                # event vai para DLQ sem dar tempo a Kafka recuperar.
                delay_seconds = min(2 ** event.retry_count, 300)
                event.next_retry_at = datetime.now(tz=timezone.utc) + timedelta(
                    seconds=delay_seconds
                )

                # Mark as failed, increment retry
                event.retry_count += 1
                event.error_message = str(e)

                if event.retry_count >= 5:
                    # Move to DLQ
                    event.status = "failed"
                    dlq_entry = EventDLQ(
                        event_outbox_id=event.id,
                        error_message=str(e),
                        retry_attempt=event.retry_count,
                    )
                    session.add(dlq_entry)
                    
                    logger.error(
                        f"Event moved to DLQ: id={event.id}, type={event.event_type}, "
                        f"retry_count={event.retry_count}, error={e!s}"
                    )
                else:
                    logger.warning(
                        f"Event dispatch failed: id={event.id}, type={event.event_type}, "
                        f"retry_count={event.retry_count}, error={e!s}"
                    )
        
        # Commit all changes
        try:
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to commit outbox dispatch changes: {e}")
            await session.rollback()
            raise


async def run_outbox_dispatcher_loop(
    dispatcher: OutboxDispatcher,
    interval_seconds: int = 5,
    stop_event: Optional[asyncio.Event] = None,
):
    """
    Run outbox dispatcher in a loop.
    
    Args:
        dispatcher: OutboxDispatcher instance
        interval_seconds: Interval between dispatches (default: 5)
        stop_event: Optional asyncio.Event to stop the loop
    """
    logger.info(f"Outbox dispatcher loop started (interval: {interval_seconds}s)")
    
    while True:
        if stop_event and stop_event.is_set():
            logger.info("Outbox dispatcher loop stopped")
            break
        
        try:
            await dispatcher.run()
        except Exception as e:
            logger.error(f"Outbox dispatcher error: {e}", exc_info=True)
        
        await asyncio.sleep(interval_seconds)

