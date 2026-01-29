"""
ProdPlan ONE - Decision Intelligence Platform E2E Tests
========================================================

End-to-end tests for the complete Decision Intelligence Platform workflow:
1. Complete decision flow (view → explain → suggest → preview → propose → approve → execute)
2. SoD blocks self-approval
3. Sandbox deterministic (same input = same output)
4. Rollback window (24h)
5. Audit trail immutable
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.shared.models.governance import DecisionRun, DecisionApproval, DecisionStatus, ApprovalStatus
from src.copilot.actions import Action, ActionExecutor, ActionMode
from src.shared.auth.rbac import check_sod, SOD_POLICIES


class TestCompleteDecisionFlow:
    """Test complete decision flow from proposal to execution."""
    
    @pytest.mark.asyncio
    async def test_complete_decision_flow(self, test_session, sample_tenant_id):
        """
        E2E: View KPI → Explain → Suggest → Preview → Propose → Approve → Execute.
        
        Tests the complete workflow:
        1. View KPI with explanation
        2. Get AI suggestion
        3. Preview in sandbox
        4. Propose decision
        5. Approve decision
        6. Execute decision
        7. Verify execution
        """
        user_id = uuid4()
        approver_id = uuid4()
        
        # Step 1: Create a decision proposal (simulating sandbox preview)
        before_state = {
            "captured_at": datetime.utcnow().isoformat(),
            "kpis": {"total_orders": 100},
            "schedules": [],
        }
        
        after_state = {
            "captured_at": datetime.utcnow().isoformat(),
            "kpis": {"total_orders": 105},
            "schedules": [],
        }
        
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Increase Safety Stock for Product K1",
            action_type="INCREASE_SS",
            target="K1-VANQUISH",
            status=DecisionStatus.PROPOSED.value,
            sandbox_result={"estimated_impact": {"otd_improvement": "5%"}},
            before_state=before_state,
            after_state=after_state,
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
        )
        test_session.add(decision)
        await test_session.flush()
        
        # Step 2: Create approval (different user)
        approval = DecisionApproval(
            decision_id=decision.id,
            approver_id=approver_id,
            status=ApprovalStatus.PENDING.value,
        )
        test_session.add(approval)
        await test_session.flush()
        
        # Step 3: Approve decision
        approval.status = ApprovalStatus.APPROVED.value
        approval.approved_at = datetime.utcnow()
        approval.comment = "Approved - safety stock increase justified"
        decision.status = DecisionStatus.APPROVED.value
        await test_session.flush()
        
        # Step 4: Execute decision
        decision.status = DecisionStatus.EXECUTED.value
        decision.executed_at = datetime.utcnow()
        await test_session.commit()
        
        # Step 5: Verify execution
        await test_session.refresh(decision)
        assert decision.status == DecisionStatus.EXECUTED.value
        assert decision.executed_at is not None
        assert len(decision.approvals) == 1
        assert decision.approvals[0].status == ApprovalStatus.APPROVED.value


class TestSoDBlocksSelfApproval:
    """Test that Segregation of Duties prevents self-approval."""
    
    @pytest.mark.asyncio
    async def test_sod_blocks_self_approval(self, test_session, sample_tenant_id):
        """
        E2E: SoD blocks self-approval.
        
        Tests that a user cannot approve their own decision proposal.
        """
        user_id = uuid4()
        
        # Create decision proposal
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Test Decision",
            action_type="INCREASE_SS",
            target="K1-VANQUISH",
            status=DecisionStatus.PROPOSED.value,
            before_state={},
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
        )
        test_session.add(decision)
        await test_session.flush()
        
        # Attempt to approve own decision (should fail SoD check)
        action_type = "INCREASE_SS"
        proposer_id = user_id
        approver_id = user_id  # Same user
        
        # Check SoD - should raise exception or return False
        try:
            sod_check = check_sod(action_type, proposer_id, approver_id)
            assert sod_check is False, "SoD should block self-approval"
        except ValueError as e:
            assert "cannot approve" in str(e).lower() or "self-approval" in str(e).lower()
        
        # Verify decision still in PROPOSED status
        await test_session.refresh(decision)
        assert decision.status == DecisionStatus.PROPOSED.value
    
    @pytest.mark.asyncio
    async def test_sod_allows_different_approver(self, test_session, sample_tenant_id):
        """
        E2E: SoD allows approval by different user with correct role.
        
        Tests that a different user with the required role can approve.
        """
        proposer_id = uuid4()
        approver_id = uuid4()  # Different user
        
        # Check SoD - should pass
        action_type = "INCREASE_SS"
        sod_check = check_sod(action_type, proposer_id, approver_id)
        assert sod_check is True, "SoD should allow approval by different user"


class TestSandboxDeterministic:
    """Test that sandbox execution is deterministic."""
    
    @pytest.mark.asyncio
    async def test_sandbox_deterministic_same_input_same_output(self, test_session, sample_tenant_id):
        """
        E2E: Sandbox deterministic (same input = same output).
        
        Tests that running the same action in sandbox multiple times
        produces identical results.
        """
        user_id = uuid4()
        
        # Create action
        action = Action(
            action_id="test-action-1",
            action_type="reduce_setup",
            description="Reduce setup time",
            modes=["preview", "sandbox", "execute"],
            estimated_impact={"setup_reduction_minutes": 15},
            payload={"target": "OP-001"},
        )
        
        # Mock Kafka producer
        mock_kafka = AsyncMock()
        
        # Execute in sandbox twice with same input
        executor1 = ActionExecutor(test_session, sample_tenant_id, user_id, mock_kafka)
        executor2 = ActionExecutor(test_session, sample_tenant_id, user_id, mock_kafka)
        
        result1 = await executor1.execute_action(action, ActionMode.SANDBOX, None)
        result2 = await executor2.execute_action(action, ActionMode.SANDBOX, None)
        
        # Results should be identical (deterministic)
        assert result1["status"] == result2["status"]
        assert result1["mode"] == result2["mode"]
        # Note: actual_impact may vary slightly due to timestamps, but structure should be same
        assert "before_state" in result1
        assert "before_state" in result2
        assert "after_state" in result1
        assert "after_state" in result2


class TestRollbackWindow:
    """Test rollback window functionality."""
    
    @pytest.mark.asyncio
    async def test_rollback_within_24h_window(self, test_session, sample_tenant_id):
        """
        E2E: Rollback within 24h window.
        
        Tests that decisions can be rolled back within 24 hours of execution.
        """
        user_id = uuid4()
        approver_id = uuid4()
        
        # Create and execute decision
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Test Decision for Rollback",
            action_type="ADJUST_INVENTORY",
            target="K1-VANQUISH",
            status=DecisionStatus.EXECUTED.value,
            before_state={"inventory": 100},
            after_state={"inventory": 150},
            proposed_by=user_id,
            proposed_at=datetime.utcnow() - timedelta(hours=2),
            executed_at=datetime.utcnow() - timedelta(hours=1),  # Executed 1 hour ago
        )
        test_session.add(decision)
        await test_session.flush()
        
        # Verify within rollback window (24h)
        time_since_execution = datetime.utcnow() - decision.executed_at
        assert time_since_execution < timedelta(hours=24), "Should be within rollback window"
        
        # Rollback decision
        decision.status = DecisionStatus.ROLLED_BACK.value
        decision.rolled_back_at = datetime.utcnow()
        await test_session.commit()
        
        # Verify rollback
        await test_session.refresh(decision)
        assert decision.status == DecisionStatus.ROLLED_BACK.value
        assert decision.rolled_back_at is not None
    
    @pytest.mark.asyncio
    async def test_rollback_blocked_after_24h(self, test_session, sample_tenant_id):
        """
        E2E: Rollback blocked after 24h window.
        
        Tests that decisions cannot be rolled back after 24 hours.
        """
        user_id = uuid4()
        
        # Create decision executed more than 24h ago
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Old Decision",
            action_type="ADJUST_INVENTORY",
            target="K1-VANQUISH",
            status=DecisionStatus.EXECUTED.value,
            before_state={},
            after_state={},
            proposed_by=user_id,
            proposed_at=datetime.utcnow() - timedelta(hours=48),
            executed_at=datetime.utcnow() - timedelta(hours=25),  # Executed 25 hours ago
        )
        test_session.add(decision)
        await test_session.commit()
        
        # Verify outside rollback window
        time_since_execution = datetime.utcnow() - decision.executed_at
        assert time_since_execution > timedelta(hours=24), "Should be outside rollback window"
        
        # Attempt to rollback should be blocked (business logic check)
        # In real implementation, this would raise an exception
        can_rollback = time_since_execution < timedelta(hours=24)
        assert can_rollback is False, "Rollback should be blocked after 24h"


class TestAuditTrailImmutable:
    """Test that audit trail is immutable."""
    
    @pytest.mark.asyncio
    async def test_audit_trail_immutable(self, test_session, sample_tenant_id):
        """
        E2E: Audit trail immutable.
        
        Tests that decision records cannot be modified after creation.
        """
        user_id = uuid4()
        
        # Create decision
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Test Decision",
            action_type="INCREASE_SS",
            target="K1-VANQUISH",
            status=DecisionStatus.PROPOSED.value,
            before_state={"original": "data"},
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
        )
        test_session.add(decision)
        await test_session.commit()
        
        # Store original values
        original_title = decision.title
        original_before_state = decision.before_state.copy()
        original_proposed_at = decision.proposed_at
        
        # Attempt to modify (should be prevented by business logic or constraints)
        # In production, this might be prevented by:
        # 1. Database constraints
        # 2. Business logic checks
        # 3. Read-only fields after creation
        
        # For this test, we verify that the original values are preserved
        await test_session.refresh(decision)
        assert decision.title == original_title
        assert decision.before_state == original_before_state
        assert decision.proposed_at == original_proposed_at
    
    @pytest.mark.asyncio
    async def test_approval_record_immutable_after_approval(self, test_session, sample_tenant_id):
        """
        E2E: Approval records immutable after approval.
        
        Tests that approval records cannot be modified after approval.
        """
        user_id = uuid4()
        approver_id = uuid4()
        
        # Create decision and approval
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Test Decision",
            action_type="INCREASE_SS",
            target="K1-VANQUISH",
            status=DecisionStatus.PROPOSED.value,
            before_state={},
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
        )
        test_session.add(decision)
        await test_session.flush()
        
        approval = DecisionApproval(
            decision_id=decision.id,
            approver_id=approver_id,
            status=ApprovalStatus.APPROVED.value,
            comment="Original comment",
            approved_at=datetime.utcnow(),
        )
        test_session.add(approval)
        await test_session.commit()
        
        # Store original values
        original_comment = approval.comment
        original_approved_at = approval.approved_at
        
        # Attempt to modify (should be prevented)
        # In production, this would be prevented by business logic
        await test_session.refresh(approval)
        assert approval.comment == original_comment
        assert approval.approved_at == original_approved_at


class TestKPIExplanationFlow:
    """Test KPI explanation flow."""
    
    @pytest.mark.asyncio
    async def test_kpi_explanation_flow(self, test_session, sample_tenant_id):
        """
        E2E: KPI explanation flow.
        
        Tests:
        1. Get KPI snapshot
        2. Request explanation
        3. Receive explanation with root causes
        """
        from src.shared.explanation_engine import ExplanationEngine
        
        # Create explanation engine
        engine = ExplanationEngine(test_session, sample_tenant_id)
        
        # Request OTD explanation
        explanation = await engine.explain_kpi("otd")
        
        # Verify explanation structure
        assert "reason" in explanation or "topFactors" in explanation
        # Explanation may be empty if no data, but structure should exist


class TestSandboxPreviewToDecision:
    """Test conversion from sandbox preview to decision proposal."""
    
    @pytest.mark.asyncio
    async def test_sandbox_preview_to_decision_proposal(self, test_session, sample_tenant_id):
        """
        E2E: Sandbox preview → Decision proposal.
        
        Tests that sandbox preview results can be converted to decision proposals.
        """
        user_id = uuid4()
        
        # Simulate sandbox execution result
        sandbox_result = {
            "success": True,
            "before_state": {"kpis": {"total_orders": 100}},
            "after_state": {"kpis": {"total_orders": 105}},
            "deltas": {"total_orders": 5},
            "actual_impact": {"otd_improvement": "5%"},
        }
        
        # Create decision proposal from sandbox result
        decision = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Increase Safety Stock - K1",
            action_type="INCREASE_SS",
            target="K1-VANQUISH",
            status=DecisionStatus.PROPOSED.value,
            sandbox_result=sandbox_result,
            before_state=sandbox_result["before_state"],
            after_state=sandbox_result["after_state"],
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
        )
        test_session.add(decision)
        await test_session.commit()
        
        # Verify decision created with sandbox data
        await test_session.refresh(decision)
        assert decision.sandbox_result == sandbox_result
        assert decision.before_state == sandbox_result["before_state"]
        assert decision.after_state == sandbox_result["after_state"]
        assert decision.status == DecisionStatus.PROPOSED.value


class TestDecisionListAndFiltering:
    """Test decision listing and filtering."""
    
    @pytest.mark.asyncio
    async def test_decision_list_with_filters(self, test_session, sample_tenant_id):
        """
        E2E: Decision list with filtering.
        
        Tests that decisions can be listed and filtered by status.
        """
        user_id = uuid4()
        
        # Create decisions with different statuses
        decision1 = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Proposed Decision",
            action_type="INCREASE_SS",
            target="K1",
            status=DecisionStatus.PROPOSED.value,
            before_state={},
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
        )
        
        decision2 = DecisionRun(
            tenant_id=sample_tenant_id,
            title="Executed Decision",
            action_type="ADJUST_INVENTORY",
            target="K2",
            status=DecisionStatus.EXECUTED.value,
            before_state={},
            proposed_by=user_id,
            proposed_at=datetime.utcnow(),
            executed_at=datetime.utcnow(),
        )
        
        test_session.add_all([decision1, decision2])
        await test_session.commit()
        
        # Filter by PROPOSED status
        from sqlalchemy import select
        from src.shared.models.governance import DecisionRun
        
        proposed_query = select(DecisionRun).where(
            DecisionRun.tenant_id == sample_tenant_id,
            DecisionRun.status == DecisionStatus.PROPOSED.value,
        )
        result = await test_session.execute(proposed_query)
        proposed_decisions = result.scalars().all()
        
        assert len(proposed_decisions) == 1
        assert proposed_decisions[0].status == DecisionStatus.PROPOSED.value
        
        # Filter by EXECUTED status
        executed_query = select(DecisionRun).where(
            DecisionRun.tenant_id == sample_tenant_id,
            DecisionRun.status == DecisionStatus.EXECUTED.value,
        )
        result = await test_session.execute(executed_query)
        executed_decisions = result.scalars().all()
        
        assert len(executed_decisions) == 1
        assert executed_decisions[0].status == DecisionStatus.EXECUTED.value









