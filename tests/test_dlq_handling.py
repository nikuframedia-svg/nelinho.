"""
ProdPlan ONE - DLQ Handling Tests
==================================

Test Dead Letter Queue handling:
- Events moved to DLQ after 5 retry attempts
- Retry count increments on failure
- Status updated to 'failed' after max retries
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from src.shared.outbox_models import EventOutbox, EventDLQ
from src.shared.outbox_dispatcher import OutboxDispatcher
from src.shared.kafka_client import KafkaProducerClient


class TestDLQHandling:
    """Test Dead Letter Queue handling after max retries."""
    
    @pytest.mark.asyncio
    async def test_event_moved_to_dlq_after_5_retries(
        self,
        test_session,
        sample_tenant_id,
        sample_aggregate_id,
    ):
        """
        Test that event is moved to DLQ after 5 retry attempts.
        
        Creates event with retry_count=4, dispatcher should increment to 5
        and move to DLQ.
        """
        # Create event with retry_count = 4 (one below threshold)
        event_id = uuid4()
        event = EventOutbox(
            id=event_id,
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"test": "data"},
            status="pending",
            retry_count=4,  # One below threshold
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka producer to raise exception (simulate failure)
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(side_effect=Exception("Kafka connection failed"))
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
            batch_size=100,
        )
        
        # Dispatch (should fail and increment retry_count)
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Refresh event
        await test_session.refresh(event)
        
        # Retry count should be 5
        assert event.retry_count == 5
        
        # Status should be 'failed'
        assert event.status == "failed"
        
        # DLQ entry should be created
        from sqlalchemy import select
        stmt = select(EventDLQ).where(EventDLQ.event_outbox_id == event_id)
        result = await test_session.execute(stmt)
        dlq_entry = result.scalar_one_or_none()
        
        assert dlq_entry is not None
        assert dlq_entry.event_outbox_id == event_id
        assert dlq_entry.retry_attempt == 5
        assert dlq_entry.error_message is not None
    
    @pytest.mark.asyncio
    async def test_retry_count_increments_on_failure(
        self,
        test_session,
        sample_tenant_id,
        sample_aggregate_id,
    ):
        """Test that retry_count increments on each failure."""
        # Create event with retry_count = 0
        event = EventOutbox(
            id=uuid4(),
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"test": "data"},
            status="pending",
            retry_count=0,
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka producer to raise exception
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(side_effect=Exception("Kafka error"))
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        # Dispatch multiple times (simulating retries)
        for attempt in range(3):
            await dispatcher._dispatch_pending_events(test_session)
            await test_session.commit()
            await test_session.refresh(event)
        
        # Retry count should be 3
        assert event.retry_count == 3
    
    @pytest.mark.asyncio
    async def test_dlq_entry_contains_error_message(
        self,
        test_session,
        sample_tenant_id,
        sample_aggregate_id,
    ):
        """Test that DLQ entry contains error message."""
        # Create event with retry_count = 4
        event_id = uuid4()
        event = EventOutbox(
            id=event_id,
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"test": "data"},
            status="pending",
            retry_count=4,
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka producer with specific error message
        error_msg = "Kafka connection timeout"
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(side_effect=Exception(error_msg))
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        # Dispatch (should fail and create DLQ entry)
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Check DLQ entry
        from sqlalchemy import select
        stmt = select(EventDLQ).where(EventDLQ.event_outbox_id == event_id)
        result = await test_session.execute(stmt)
        dlq_entry = result.scalar_one_or_none()
        
        assert dlq_entry is not None
        assert dlq_entry.error_message is not None
        assert len(dlq_entry.error_message) > 0
    
    @pytest.mark.asyncio
    async def test_event_not_moved_to_dlq_before_5_retries(
        self,
        test_session,
        sample_tenant_id,
        sample_aggregate_id,
    ):
        """Test that event is NOT moved to DLQ before 5 retries."""
        # Create event with retry_count = 3 (below threshold)
        event_id = uuid4()
        event = EventOutbox(
            id=event_id,
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"test": "data"},
            status="pending",
            retry_count=3,
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka producer to raise exception
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(side_effect=Exception("Kafka error"))
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        # Dispatch (should fail but NOT move to DLQ yet)
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Refresh event
        await test_session.refresh(event)
        
        # Retry count should be 4 (incremented but not at threshold)
        assert event.retry_count == 4
        
        # Status should still be 'pending' (not 'failed')
        assert event.status == "pending"
        
        # DLQ entry should NOT exist yet
        from sqlalchemy import select
        stmt = select(EventDLQ).where(EventDLQ.event_outbox_id == event_id)
        result = await test_session.execute(stmt)
        dlq_entry = result.scalar_one_or_none()
        
        assert dlq_entry is None










