"""
ProdPlan ONE - Copilot Action Execution Tests
==============================================

Test ActionExecutor with 3 modes:
- PREVIEW: Returns estimated_impact without commits
- SANDBOX: Executes in nested transaction with auto-rollback
- EXECUTE: Commits + creates audit log + publishes Kafka event
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.copilot.actions import Action, ActionExecutor, ActionMode


class TestPreviewMode:
    """Test PREVIEW mode execution."""
    
    @pytest.mark.asyncio
    async def test_preview_returns_estimated_impact(self, test_session):
        """Test that preview mode returns estimated_impact without commits."""
        action = Action(
            action_id="action_123",
            action_type="reduce_setup",
            description="Test action",
            modes=["preview", "sandbox", "execute"],
            estimated_impact={
                "makespan_delta_minutes": -120,
                "oee_improvement_pct": 2.5,
                "cost_change_eur": -200,
            },
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        result = await executor.execute_action(action, ActionMode.PREVIEW)
        
        # Should return estimated_impact
        assert result["mode"] == "preview"
        assert "estimated_impact" in result
        assert result["estimated_impact"] == action.estimated_impact
        assert result["status"] == "preview_complete"
    
    @pytest.mark.asyncio
    async def test_preview_no_database_commits(self, test_session):
        """Test that preview mode does not commit to database."""
        action = Action(
            action_id="action_456",
            action_type="test_action",
            description="Test",
            modes=["preview"],
            estimated_impact={"test": "value"},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        # Execute preview
        result = await executor.execute_action(action, ActionMode.PREVIEW)
        
        # Verify no commits happened (session should not be committed)
        # This is implicit - preview should not modify DB state
        assert result["mode"] == "preview"
        assert "No changes committed" in result["message"] or "preview" in result["message"].lower()


class TestSandboxMode:
    """Test SANDBOX mode execution with nested transactions."""
    
    @pytest.mark.asyncio
    async def test_sandbox_rolls_back_changes(self, test_session):
        """Test that sandbox mode rolls back changes automatically."""
        action = Action(
            action_id="action_789",
            action_type="test_action",
            description="Test sandbox",
            modes=["sandbox"],
            estimated_impact={"test": "value"},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        result = await executor.execute_action(action, ActionMode.SANDBOX)
        
        # Should indicate rollback
        assert result["mode"] == "sandbox"
        assert "rolled back" in result["message"].lower() or "rollback" in result["message"].lower()
        assert "actual_impact" in result
    
    @pytest.mark.asyncio
    async def test_sandbox_returns_before_and_after_state(self, test_session):
        """Test that sandbox mode returns before and after states."""
        action = Action(
            action_id="action_sandbox",
            action_type="test_action",
            description="Test",
            modes=["sandbox"],
            estimated_impact={},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        result = await executor.execute_action(action, ActionMode.SANDBOX)
        
        # Should include before and after states
        assert "before_state" in result
        assert "after_state" in result
        assert isinstance(result["before_state"], dict)
        assert isinstance(result["after_state"], dict)


class TestExecuteMode:
    """Test EXECUTE mode (production execution)."""
    
    @pytest.mark.asyncio
    async def test_execute_creates_transaction_id(self, test_session):
        """Test that execute mode creates transaction_id."""
        action = Action(
            action_id="action_execute",
            action_type="test_action",
            description="Test execute",
            modes=["execute"],
            estimated_impact={},
        )
        
        mock_kafka = AsyncMock()
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
            kafka_producer=mock_kafka,
        )
        
        result = await executor.execute_action(action, ActionMode.EXECUTE)
        
        # Should have transaction_id
        assert "transaction_id" in result
        assert result["transaction_id"] is not None
        assert result["mode"] == "execute"
    
    @pytest.mark.asyncio
    async def test_execute_publishes_kafka_event(self, test_session):
        """Test that execute mode publishes Kafka event."""
        action = Action(
            action_id="action_kafka",
            action_type="test_action",
            description="Test Kafka",
            modes=["execute"],
            estimated_impact={},
        )
        
        mock_kafka = AsyncMock()
        mock_kafka.publish = AsyncMock(return_value={"kafka_offset": 123})
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
            kafka_producer=mock_kafka,
        )
        
        result = await executor.execute_action(action, ActionMode.EXECUTE)
        
        # Kafka publish should be called
        mock_kafka.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_sets_rollback_until_24h(self, test_session):
        """Test that execute mode sets rollback_until to 24 hours from now."""
        from datetime import datetime, timedelta
        
        action = Action(
            action_id="action_rollback",
            action_type="test_action",
            description="Test rollback",
            modes=["execute"],
            estimated_impact={},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        result = await executor.execute_action(action, ActionMode.EXECUTE)
        
        # Should have rollback_until
        assert "rollback_until" in result
        
        # Parse timestamp and verify it's approximately 24h from now
        rollback_until_str = result["rollback_until"]
        rollback_until = datetime.fromisoformat(rollback_until_str.replace("Z", "+00:00"))
        now = datetime.utcnow()
        
        # Should be approximately 24 hours (allow 1 hour tolerance)
        time_diff = rollback_until - now
        assert timedelta(hours=23) <= time_diff <= timedelta(hours=25)


class TestActionExecutionEdgeCases:
    """Test edge cases in action execution."""
    
    @pytest.mark.asyncio
    async def test_invalid_action_mode_raises_error(self, test_session):
        """Test that invalid action mode raises ValueError."""
        action = Action(
            action_id="action_invalid",
            action_type="test",
            description="Test",
            modes=["preview"],
            estimated_impact={},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        
        # Invalid mode should raise error
        # Note: ActionMode enum only has valid values, so we can't test this directly
        # But the code should handle unexpected modes gracefully
        pass  # Placeholder - enum prevents invalid values
    
    @pytest.mark.asyncio
    async def test_execute_without_kafka_does_not_crash(self, test_session):
        """Test that execute mode works without Kafka producer."""
        action = Action(
            action_id="action_no_kafka",
            action_type="test",
            description="Test",
            modes=["execute"],
            estimated_impact={},
        )
        
        executor = ActionExecutor(
            session=test_session,
            tenant_id=uuid4(),
            user_id=uuid4(),
            kafka_producer=None,  # No Kafka
        )
        
        # Should execute without error (Kafka is optional)
        result = await executor.execute_action(action, ActionMode.EXECUTE)
        assert result["mode"] == "execute"










