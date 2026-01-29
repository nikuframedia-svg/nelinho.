"""
ProdPlan ONE - Runbook Engine Tests
====================================

Test RunbookExecutor with branching logic:
- Execute runbook with sequential steps
- Test on_success and on_failure branching
- Verify runbook execution from YAML files
"""

import pytest
import yaml
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.copilot.runbooks import RunbookStep, RunbookExecutor


class TestRunbookStep:
    """Test RunbookStep class."""
    
    def test_runbook_step_creation(self):
        """Test creating a RunbookStep with all fields."""
        step = RunbookStep(
            step_id="step_1",
            name="Check Material Availability",
            action={"type": "check_inventory", "sku": "SKU-001"},
            condition="inventory_available == true",
            next_step="step_2",
            on_success="step_3",
            on_failure="step_4",
        )
        
        assert step.step_id == "step_1"
        assert step.name == "Check Material Availability"
        assert step.action == {"type": "check_inventory", "sku": "SKU-001"}
        assert step.condition == "inventory_available == true"
        assert step.next_step == "step_2"
        assert step.on_success == "step_3"
        assert step.on_failure == "step_4"
    
    def test_runbook_step_from_dict(self):
        """Test creating RunbookStep from dictionary."""
        step_dict = {
            "step_id": "step_1",
            "name": "Test Step",
            "action": {"type": "test_action"},
        }
        
        step = RunbookStep.from_dict(step_dict)
        
        assert step.step_id == "step_1"
        assert step.name == "Test Step"
        assert step.action == {"type": "test_action"}


class TestRunbookExecutor:
    """Test RunbookExecutor execution."""
    
    @pytest.mark.asyncio
    async def test_runbook_executes_sequential_steps(self):
        """Test that runbook executes steps sequentially."""
        steps = [
            RunbookStep(
                step_id="step_1",
                name="Step 1",
                action={"type": "action_1"},
                next_step="step_2",
            ),
            RunbookStep(
                step_id="step_2",
                name="Step 2",
                action={"type": "action_2"},
                next_step=None,  # End
            ),
        ]
        
        executor = RunbookExecutor()
        
        # Mock action handler
        execution_log = []
        
        async def mock_action_handler(step, context):
            execution_log.append(step.step_id)
            return {"status": "success", "result": f"executed_{step.step_id}"}
        
        result = await executor.execute_runbook(steps, action_handler=mock_action_handler)
        
        # Verify steps executed in order
        assert execution_log == ["step_1", "step_2"]
        assert result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_runbook_branches_on_success(self):
        """Test that runbook branches to on_success when step succeeds."""
        steps = [
            RunbookStep(
                step_id="step_1",
                name="Check Condition",
                action={"type": "check"},
                on_success="step_success",
                on_failure="step_failure",
            ),
            RunbookStep(
                step_id="step_success",
                name="Success Path",
                action={"type": "success_action"},
                next_step=None,
            ),
            RunbookStep(
                step_id="step_failure",
                name="Failure Path",
                action={"type": "failure_action"},
                next_step=None,
            ),
        ]
        
        executor = RunbookExecutor()
        
        execution_log = []
        
        async def mock_action_handler(step, context):
            execution_log.append(step.step_id)
            # Return success for step_1
            if step.step_id == "step_1":
                return {"status": "success"}
            return {"status": "success"}
        
        result = await executor.execute_runbook(steps, action_handler=mock_action_handler)
        
        # Should execute step_1, then branch to step_success
        assert "step_1" in execution_log
        assert "step_success" in execution_log
        assert "step_failure" not in execution_log
    
    @pytest.mark.asyncio
    async def test_runbook_branches_on_failure(self):
        """Test that runbook branches to on_failure when step fails."""
        steps = [
            RunbookStep(
                step_id="step_1",
                name="Check Condition",
                action={"type": "check"},
                on_success="step_success",
                on_failure="step_failure",
            ),
            RunbookStep(
                step_id="step_success",
                name="Success Path",
                action={"type": "success_action"},
                next_step=None,
            ),
            RunbookStep(
                step_id="step_failure",
                name="Failure Path",
                action={"type": "failure_action"},
                next_step=None,
            ),
        ]
        
        executor = RunbookExecutor()
        
        execution_log = []
        
        async def mock_action_handler(step, context):
            execution_log.append(step.step_id)
            # Return failure for step_1
            if step.step_id == "step_1":
                return {"status": "failure", "error": "Test error"}
            return {"status": "success"}
        
        result = await executor.execute_runbook(steps, action_handler=mock_action_handler)
        
        # Should execute step_1, then branch to step_failure
        assert "step_1" in execution_log
        assert "step_failure" in execution_log
        assert "step_success" not in execution_log
    
    @pytest.mark.asyncio
    async def test_runbook_uses_next_step_when_no_branching(self):
        """Test that runbook uses next_step when on_success/on_failure not defined."""
        steps = [
            RunbookStep(
                step_id="step_1",
                name="Step 1",
                action={"type": "action_1"},
                next_step="step_2",  # Use next_step
            ),
            RunbookStep(
                step_id="step_2",
                name="Step 2",
                action={"type": "action_2"},
                next_step=None,
            ),
        ]
        
        executor = RunbookExecutor()
        
        execution_log = []
        
        async def mock_action_handler(step, context):
            execution_log.append(step.step_id)
            return {"status": "success"}
        
        result = await executor.execute_runbook(steps, action_handler=mock_action_handler)
        
        # Should execute both steps sequentially
        assert execution_log == ["step_1", "step_2"]


class TestRunbookYAMLLoading:
    """Test loading runbooks from YAML files."""
    
    def test_load_runbook_from_yaml(self):
        """Test loading a runbook from YAML file."""
        yaml_content = """
        steps:
          - step_id: step_1
            name: First Step
            action:
              type: test_action
            next_step: step_2
          - step_id: step_2
            name: Second Step
            action:
              type: test_action_2
            next_step: null
        """
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)
        
        try:
            executor = RunbookExecutor()
            steps = executor.load_runbook_from_file(str(yaml_path))
            
            assert len(steps) == 2
            assert steps[0].step_id == "step_1"
            assert steps[1].step_id == "step_2"
        finally:
            yaml_path.unlink()
    
    def test_load_runbook_with_branching(self):
        """Test loading runbook with branching logic from YAML."""
        yaml_content = """
        steps:
          - step_id: check_material
            name: Check Material
            action:
              type: check_inventory
            on_success: expedite_purchase
            on_failure: reschedule_order
          - step_id: expedite_purchase
            name: Expedite Purchase
            action:
              type: expedite
            next_step: null
          - step_id: reschedule_order
            name: Reschedule Order
            action:
              type: reschedule
            next_step: null
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_path = Path(f.name)
        
        try:
            executor = RunbookExecutor()
            steps = executor.load_runbook_from_file(str(yaml_path))
            
            assert len(steps) == 3
            check_step = next(s for s in steps if s.step_id == "check_material")
            assert check_step.on_success == "expedite_purchase"
            assert check_step.on_failure == "reschedule_order"
        finally:
            yaml_path.unlink()


class TestRunbookEdgeCases:
    """Test edge cases in runbook execution."""
    
    @pytest.mark.asyncio
    async def test_runbook_handles_missing_step(self):
        """Test that runbook handles missing step gracefully."""
        steps = [
            RunbookStep(
                step_id="step_1",
                name="Step 1",
                action={"type": "action_1"},
                next_step="step_nonexistent",  # Missing step
            ),
        ]
        
        executor = RunbookExecutor()
        
        async def mock_action_handler(step, context):
            return {"status": "success"}
        
        result = await executor.execute_runbook(steps, action_handler=mock_action_handler)
        
        # Should handle missing step gracefully
        assert result["status"] == "error" or "step_nonexistent" in str(result).lower()
    
    @pytest.mark.asyncio
    async def test_runbook_empty_steps_list(self):
        """Test runbook execution with empty steps list."""
        executor = RunbookExecutor()
        
        async def mock_action_handler(step, context):
            return {"status": "success"}
        
        result = await executor.execute_runbook([], action_handler=mock_action_handler)
        
        # Should handle empty steps
        assert result["status"] == "completed" or "empty" in str(result).lower()
    
    @pytest.mark.asyncio
    async def test_runbook_passes_context_between_steps(self):
        """Test that context is passed between steps."""
        steps = [
            RunbookStep(
                step_id="step_1",
                name="Set Context",
                action={"type": "set_value"},
                next_step="step_2",
            ),
            RunbookStep(
                step_id="step_2",
                name="Read Context",
                action={"type": "read_value"},
                next_step=None,
            ),
        ]
        
        executor = RunbookExecutor()
        context = {}
        
        async def mock_action_handler(step, ctx):
            if step.step_id == "step_1":
                ctx["value"] = "test_value"
            return {"status": "success", "context": ctx}
        
        result = await executor.execute_runbook(steps, action_handler=mock_action_handler, context=context)
        
        # Context should be maintained
        assert context.get("value") == "test_value"










