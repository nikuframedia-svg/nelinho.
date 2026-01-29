"""
ProdPlan ONE - Outbox Pattern Tests
====================================

Test outbox pattern for exactly-once event delivery:
- UNIQUE constraint prevents duplicate events (idempotency)
- Dispatcher publishes pending events
- Status updated after successful publish
"""

import pytest
from uuid import uuid4
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from src.shared.outbox_models import EventOutbox, EventDLQ
from src.shared.outbox_dispatcher import OutboxDispatcher
from src.shared.kafka_client import EventBase


class TestOutboxIdempotency:
    """Test UNIQUE constraint prevents duplicate events."""
    
    @pytest.mark.asyncio
    async def test_unique_constraint_prevents_duplicates(self, test_session, sample_tenant_id, sample_aggregate_id):
        """
        Test that UNIQUE constraint prevents duplicate events.
        
        Attempting to insert same (tenant_id, aggregate_id, event_type) twice
        should fail with IntegrityError.
        """
        # Create first event
        event1 = EventOutbox(
            id=uuid4(),
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"makespan": 1200},
            status="pending",
        )
        test_session.add(event1)
        await test_session.commit()
        
        # Attempt to create duplicate (same tenant_id, aggregate_id, event_type)
        event2 = EventOutbox(
            id=uuid4(),  # Different ID
            tenant_id=sample_tenant_id,  # Same tenant
            aggregate_id=sample_aggregate_id,  # Same aggregate
            aggregate_type="plan",  # Same type
            event_type="plan.schedule.committed",  # Same event type
            payload={"makespan": 1200},  # Same payload
            status="pending",
        )
        test_session.add(event2)
        
        # Should raise IntegrityError due to UNIQUE constraint
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_different_event_types_allowed(self, test_session, sample_tenant_id, sample_aggregate_id):
        """
        Test that different event types for same aggregate are allowed.
        
        Same (tenant_id, aggregate_id) with different event_type should succeed.
        """
        # Create first event
        event1 = EventOutbox(
            id=uuid4(),
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"makespan": 1200},
            status="pending",
        )
        test_session.add(event1)
        await test_session.commit()
        
        # Create second event with different event_type (should succeed)
        event2 = EventOutbox(
            id=uuid4(),
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.updated",  # Different event type
            payload={"makespan": 1100},
            status="pending",
        )
        test_session.add(event2)
        await test_session.commit()  # Should succeed
        
        # Verify both events exist
        stmt = select(EventOutbox).where(
            EventOutbox.tenant_id == sample_tenant_id,
            EventOutbox.aggregate_id == sample_aggregate_id,
        )
        result = await test_session.execute(stmt)
        events = result.scalars().all()
        assert len(events) == 2


class TestOutboxDispatcher:
    """Test dispatcher publishes pending events and updates status."""
    
    @pytest.mark.asyncio
    async def test_dispatcher_publishes_pending_events(
        self,
        test_session,
        sample_tenant_id,
        sample_aggregate_id,
        sample_event_payload,
    ):
        """
        Test that dispatcher publishes pending events to Kafka.
        
        Creates pending event, runs dispatcher, verifies status updated to 'published'.
        """
        from unittest.mock import AsyncMock, MagicMock
        from src.shared.kafka_client import KafkaProducerClient, EventBase
        
        # Create pending event
        event = EventOutbox(
            id=uuid4(),
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload=sample_event_payload,
            status="pending",
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka producer
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(return_value={"kafka_offset": 123})
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
            batch_size=100,
        )
        
        # Dispatch pending events
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Verify event status updated to 'published'
        await test_session.refresh(event)
        assert event.status == "published"
        assert event.published_at is not None
        
        # Verify Kafka publish was called
        mock_producer.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dispatcher_updates_status_to_published(
        self,
        test_session,
        sample_tenant_id,
        sample_aggregate_id,
    ):
        """
        Test that dispatcher updates event status to 'published'.
        
        Verifies status and published_at timestamp are set correctly.
        """
        from unittest.mock import AsyncMock
        from src.shared.kafka_client import KafkaProducerClient
        
        # Create pending event
        event_id = uuid4()
        event = EventOutbox(
            id=event_id,
            tenant_id=sample_tenant_id,
            aggregate_id=sample_aggregate_id,
            aggregate_type="plan",
            event_type="plan.schedule.committed",
            payload={"test": "data"},
            status="pending",
        )
        test_session.add(event)
        await test_session.commit()
        
        # Mock Kafka producer
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        mock_producer.publish = AsyncMock(return_value={"kafka_offset": 456})
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        # Dispatch
        await dispatcher._dispatch_pending_events(test_session)
        await test_session.commit()
        
        # Refresh and verify
        await test_session.refresh(event)
        assert event.status == "published"
        assert event.published_at is not None
        assert isinstance(event.published_at, datetime)
    
    @pytest.mark.asyncio
    async def test_dispatcher_handles_no_pending_events(self, test_session):
        """
        Test that dispatcher handles no pending events gracefully.
        
        Should not raise exception when no pending events exist.
        """
        from unittest.mock import AsyncMock
        from src.shared.kafka_client import KafkaProducerClient
        
        # Mock Kafka producer
        mock_producer = AsyncMock(spec=KafkaProducerClient)
        
        # Create dispatcher
        async def session_factory():
            return test_session
        
        dispatcher = OutboxDispatcher(
            db_session_factory=session_factory,
            kafka_producer=mock_producer,
        )
        
        # Dispatch (no events should exist)
        await dispatcher._dispatch_pending_events(test_session)
        
        # Should complete without error
        # Kafka publish should not be called
        mock_producer.publish.assert_not_called()

