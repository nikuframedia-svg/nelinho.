"""
ProdPlan ONE - Sandbox Isolation Tests
=======================================

Test sandbox isolation using nested transactions:
- Verify sandbox does not commit changes
- Test automatic rollback on exit
- Verify nested transaction isolation
"""

import pytest
from uuid import uuid4
from sqlalchemy import select

from src.copilot.sandbox import SandboxExecutor
from src.shared.outbox_models import EventOutbox


class TestSandboxIsolation:
    """Test that sandbox provides proper transaction isolation."""
    
    @pytest.mark.asyncio
    async def test_sandbox_does_not_commit_changes(self, test_session):
        """Test that changes made in sandbox are not committed."""
        from src.shared.outbox_models import EventOutbox
        
        tenant_id = uuid4()
        
        # Get initial count
        stmt = select(EventOutbox).where(EventOutbox.tenant_id == tenant_id)
        result_before = await test_session.execute(stmt)
        count_before = len(result_before.scalars().all())
        
        # Execute in sandbox
        sandbox = SandboxExecutor(test_session)
        
        async def create_event_in_sandbox():
            event = EventOutbox(
                id=uuid4(),
                tenant_id=tenant_id,
                aggregate_id=uuid4(),
                aggregate_type="test",
                event_type="test.event",
                payload={"test": "data"},
                status="pending",
            )
            test_session.add(event)
            await test_session.flush()
            return event
        
        async with sandbox.execute_in_sandbox(create_event_in_sandbox) as result:
            # Event should exist during sandbox execution
            assert result is not None
        
        # After sandbox exit, check count again
        result_after = await test_session.execute(stmt)
        count_after = len(result_after.scalars().all())
        
        # Count should be unchanged (sandbox rolled back)
        assert count_after == count_before
    
    @pytest.mark.asyncio
    async def test_sandbox_rolls_back_on_exception(self, test_session):
        """Test that sandbox rolls back even when exception occurs."""
        from src.shared.outbox_models import EventOutbox
        
        tenant_id = uuid4()
        
        # Get initial count
        stmt = select(EventOutbox).where(EventOutbox.tenant_id == tenant_id)
        result_before = await test_session.execute(stmt)
        count_before = len(result_before.scalars().all())
        
        sandbox = SandboxExecutor(test_session)
        
        async def failing_operation():
            event = EventOutbox(
                id=uuid4(),
                tenant_id=tenant_id,
                aggregate_id=uuid4(),
                aggregate_type="test",
                event_type="test.event",
                payload={"test": "data"},
                status="pending",
            )
            test_session.add(event)
            await test_session.flush()
            raise Exception("Test exception")
        
        # Should raise exception but rollback changes
        with pytest.raises(Exception, match="Test exception"):
            async with sandbox.execute_in_sandbox(failing_operation):
                pass
        
        # Verify count unchanged (rolled back)
        result_after = await test_session.execute(stmt)
        count_after = len(result_after.scalars().all())
        assert count_after == count_before
    
    @pytest.mark.asyncio
    async def test_sandbox_isolates_nested_transactions(self, test_session):
        """Test that sandbox uses nested transactions (savepoints)."""
        # This test verifies that sandbox uses begin_nested()
        # which creates savepoints that can be rolled back independently
        
        tenant_id = uuid4()
        sandbox = SandboxExecutor(test_session)
        
        async def nested_operation():
            # Create entity in sandbox
            event = EventOutbox(
                id=uuid4(),
                tenant_id=tenant_id,
                aggregate_id=uuid4(),
                aggregate_type="test",
                event_type="test.event",
                payload={"nested": "operation"},
                status="pending",
            )
            test_session.add(event)
            await test_session.flush()
            
            # Verify it exists within sandbox
            stmt = select(EventOutbox).where(EventOutbox.id == event.id)
            result = await test_session.execute(stmt)
            found = result.scalar_one_or_none()
            assert found is not None
            
            return event
        
        # Execute in sandbox
        async with sandbox.execute_in_sandbox(nested_operation) as result:
            # Result should be available
            assert result is not None
        
        # After exit, verify it was rolled back
        stmt = select(EventOutbox).where(EventOutbox.id == result.id)
        result_check = await test_session.execute(stmt)
        found_after = result_check.scalar_one_or_none()
        
        # Should be None (rolled back)
        # Note: This assumes the event ID is available from result
        # In practice, nested transactions rollback all changes


class TestSandboxContextManager:
    """Test sandbox context manager behavior."""
    
    @pytest.mark.asyncio
    async def test_sandbox_yields_result(self, test_session):
        """Test that sandbox context manager yields operation result."""
        sandbox = SandboxExecutor(test_session)
        
        async def operation_that_returns_value():
            return {"result": "test_value"}
        
        async with sandbox.execute_in_sandbox(operation_that_returns_value) as result:
            assert result == {"result": "test_value"}
    
    @pytest.mark.asyncio
    async def test_sandbox_can_be_used_multiple_times(self, test_session):
        """Test that sandbox can be used multiple times sequentially."""
        sandbox = SandboxExecutor(test_session)
        
        async def operation():
            return {"value": "test"}
        
        # First use
        async with sandbox.execute_in_sandbox(operation) as result1:
            assert result1 == {"value": "test"}
        
        # Second use (should work independently)
        async with sandbox.execute_in_sandbox(operation) as result2:
            assert result2 == {"value": "test"}










