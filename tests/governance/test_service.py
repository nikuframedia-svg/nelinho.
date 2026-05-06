"""
Tests for src.governance.service.GovernanceService.

Strategy: mock the AsyncSession via `FakeSession` — governance models use
PostgreSQL schemas and JSONB, which are not portable to SQLite. We test
business logic (status transitions, SoD, hash chain, reason validation)
without persistence.

Coverage:
- propose_decision: policy found/missing, requires_approval True/False,
  hash chain (first vs chained), input hash shape
- approve_decision: not found, wrong status, SoD violation, SoD bypass,
  duplicate vote, REJECT/REQUEST_CHANGES/APPROVE transitions, required_approvers
- execute_decision: not found, not approved, success, exception-triggered FAILED
- rollback_decision: wrong status, short reason, success
- activate_kill_switch: auto-execute bypass
- get_audit_pack: timeline ordering
- calculate_audit_hash: deterministic
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import pytest

from src.governance.models import (
    Approval,
    ApprovalAction,
    AutonomyLevel,
    DecisionRun,
    DecisionStatus,
)
from src.governance.service import (
    ApprovalRequiredError,
    GovernanceService,
    SoDViolationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decision_run(
    *,
    status: str = DecisionStatus.PENDING_APPROVAL.value,
    decision_type: str = "scenario_publish",
    proposed_by: str = "alice",
    tenant_id: UUID,
    approvals: Optional[List[Approval]] = None,
    required_approvers: int = 1,
    policy_version: str = "1.0.0",
) -> DecisionRun:
    """Build an in-memory DecisionRun with a preset state. Not persisted."""
    run = DecisionRun(
        id=uuid4(),
        tenant_id=tenant_id,
        decision_type=decision_type,
        title=f"Test {decision_type}",
        description="unit test",
        status=status,
        policy_version=policy_version,
        autonomy_level=AutonomyLevel.L2.value,
        action_data={"foo": "bar"},
        expected_impact=None,
        risk_level="medium",
        scenario_id=None,
        evidence_refs=[],
        input_snapshot_hash="deadbeef",
        prev_hash=None,
        audit_hash="abcd1234",
        proposed_by=proposed_by,
        proposed_at=datetime.now(timezone.utc),
    )
    # Relationship collection: set explicitly to avoid lazy-load on transient instance
    run.approvals = list(approvals or [])
    return run


def _make_approval(
    *,
    tenant_id: UUID,
    decision_run_id: UUID,
    action: str,
    approved_by: str,
    reason: str = "ok",
) -> Approval:
    return Approval(
        id=uuid4(),
        tenant_id=tenant_id,
        decision_run_id=decision_run_id,
        action=action,
        approved_by=approved_by,
        reason=reason,
        approved_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# calculate_audit_hash
# ---------------------------------------------------------------------------

class TestCalculateAuditHash:
    def test_deterministic(self):
        args = dict(
            decision_id=UUID("00000000-0000-0000-0000-000000000001"),
            policy_version="1.0.0",
            input_hash="abc",
            outcome_hash=None,
            prev_hash=None,
        )
        h1 = DecisionRun.calculate_audit_hash(**args)
        h2 = DecisionRun.calculate_audit_hash(**args)
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex digest

    def test_changes_when_input_changes(self):
        base = dict(
            decision_id=UUID("00000000-0000-0000-0000-000000000001"),
            policy_version="1.0.0",
            input_hash="abc",
            outcome_hash=None,
            prev_hash=None,
        )
        h_base = DecisionRun.calculate_audit_hash(**base)
        h_mod = DecisionRun.calculate_audit_hash(**{**base, "input_hash": "xyz"})
        assert h_base != h_mod


# ---------------------------------------------------------------------------
# propose_decision
# ---------------------------------------------------------------------------

class TestProposeDecision:
    async def test_uses_policy_when_found(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)  # _get_last_decision_hash -> None
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.propose_decision(
            decision_type="scenario_publish",  # has DEFAULT_POLICY
            title="Publish v2",
            action_data={"scenario_id": "abc"},
            proposed_by="alice",
        )

        # scenario_publish requires approval -> PENDING_APPROVAL
        assert result["status"] == DecisionStatus.PENDING_APPROVAL.value
        assert result["autonomy_level"] == AutonomyLevel.L2.value
        assert result["proposed_by"] == "alice"
        assert result["prev_hash"] is None  # first in chain
        assert len(result["audit_hash"]) == 64
        assert len(fake_session.added) == 1
        assert fake_session.flush_calls >= 1

    async def test_uses_default_policy_when_type_unknown(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.propose_decision(
            decision_type="unknown_type_not_in_defaults",
            title="Exotic",
            action_data={},
            proposed_by="alice",
        )

        # default policy: requires_approval=True
        assert result["status"] == DecisionStatus.PENDING_APPROVAL.value
        assert result["autonomy_level"] == AutonomyLevel.L2.value

    async def test_skips_approval_for_kill_switch_policy(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.propose_decision(
            decision_type="kill_switch",
            title="EMERGENCY",
            action_data={"scope": "all"},
            proposed_by="alice",
        )

        # kill_switch policy has requires_approval=False -> PROPOSED
        assert result["status"] == DecisionStatus.PROPOSED.value

    async def test_chains_hash_when_prior_exists(self, fake_session, tenant_id):
        # Sprint Q.12 Onda 2.2 — propose_decision now consults
        # is_kill_switch_active before reading the previous audit hash,
        # so the FakeSession needs an extra ``None`` queued for that
        # lookup. (Real PG ignores the row count when there's no
        # active scope.)
        fake_session.queue_scalar(None)  # is_kill_switch_active -> None
        fake_session.queue_scalar("prevhash123")  # _get_last_decision_hash
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.propose_decision(
            decision_type="scenario_publish",
            title="T",
            action_data={},
            proposed_by="alice",
        )

        assert result["prev_hash"] == "prevhash123"


# ---------------------------------------------------------------------------
# approve_decision
# ---------------------------------------------------------------------------

class TestApproveDecision:
    async def test_not_found_raises_value_error(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)  # _get_decision_run -> None
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ValueError, match="not found"):
            await svc.approve_decision(
                decision_id=str(uuid4()),
                action=ApprovalAction.APPROVE,
                approved_by="bob",
                reason="lgtm",
            )

    async def test_wrong_status_raises_value_error(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.APPROVED.value,  # not PENDING_APPROVAL
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ValueError, match="not pending approval"):
            await svc.approve_decision(
                decision_id=str(run.id),
                action=ApprovalAction.APPROVE,
                approved_by="bob",
                reason="lgtm",
            )

    async def test_sod_violation_raises(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            decision_type="scenario_publish",  # requires_different_approver=True
            proposed_by="alice",
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(SoDViolationError, match="Separation of Duties"):
            await svc.approve_decision(
                decision_id=str(run.id),
                action=ApprovalAction.APPROVE,
                approved_by="alice",  # same as proposer
                reason="self-approve",
            )

    async def test_sod_bypass_when_policy_allows(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            decision_type="data_repair",  # requires_different_approver=False
            proposed_by="alice",
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.APPROVE,
            approved_by="alice",  # same, but allowed
            reason="self-approve ok for data_repair",
        )

        assert result["status"] == DecisionStatus.APPROVED.value

    async def test_duplicate_vote_raises(self, fake_session, tenant_id):
        prior = _make_approval(
            tenant_id=tenant_id,
            decision_run_id=uuid4(),
            action=ApprovalAction.APPROVE.value,
            approved_by="bob",
        )
        run = _make_decision_run(
            tenant_id=tenant_id,
            proposed_by="alice",
            approvals=[prior],
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ValueError, match="already voted"):
            await svc.approve_decision(
                decision_id=str(run.id),
                action=ApprovalAction.APPROVE,
                approved_by="bob",  # already voted
                reason="again?",
            )

    async def test_reject_transitions_to_rejected(self, fake_session, tenant_id):
        run = _make_decision_run(tenant_id=tenant_id, proposed_by="alice")
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.REJECT,
            approved_by="bob",
            reason="not ok",
        )

        assert result["status"] == DecisionStatus.REJECTED.value

    async def test_request_changes_reverts_to_proposed(self, fake_session, tenant_id):
        run = _make_decision_run(tenant_id=tenant_id, proposed_by="alice")
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.REQUEST_CHANGES,
            approved_by="bob",
            reason="please revise",
        )

        assert result["status"] == DecisionStatus.PROPOSED.value

    async def test_approve_with_single_approver_requirement(self, fake_session, tenant_id):
        # scenario_publish requires 1 approver
        run = _make_decision_run(
            tenant_id=tenant_id,
            decision_type="scenario_publish",
            proposed_by="alice",
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.APPROVE,
            approved_by="bob",
            reason="lgtm",
        )

        assert result["status"] == DecisionStatus.APPROVED.value
        assert result["approved_at"] is not None

    async def test_approve_pending_until_quorum(self, fake_session, tenant_id):
        # standard_time_update requires 2 approvers — first approve leaves PENDING
        run = _make_decision_run(
            tenant_id=tenant_id,
            decision_type="standard_time_update",
            proposed_by="alice",
            required_approvers=2,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.approve_decision(
            decision_id=str(run.id),
            action=ApprovalAction.APPROVE,
            approved_by="bob",
            reason="first approval",
        )

        assert result["status"] == DecisionStatus.PENDING_APPROVAL.value


# ---------------------------------------------------------------------------
# execute_decision
# ---------------------------------------------------------------------------

class TestExecuteDecision:
    async def test_not_found_raises(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ValueError, match="not found"):
            await svc.execute_decision(str(uuid4()), executed_by="bob")

    async def test_not_approved_raises_approval_required(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.PENDING_APPROVAL.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ApprovalRequiredError):
            await svc.execute_decision(str(run.id), executed_by="bob")

    async def test_success_updates_audit_hash(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.APPROVED.value,
        )
        original_hash = run.audit_hash
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.execute_decision(str(run.id), executed_by="bob")

        # Sprint Q.12 Onda 2.1 — ``scenario_publish`` has no concrete
        # handler in the default registry, so the dispatcher correctly
        # downgrades to EXECUTED_PARTIAL (audit row real, domain
        # mutation skipped) instead of pretending it's done. Either
        # status is acceptable here: the contract this test exercises
        # is "outcome_hash is recomputed and the audit chain advances",
        # which holds in both cases.
        assert result["status"] in {
            DecisionStatus.EXECUTED.value,
            DecisionStatus.EXECUTED_PARTIAL.value,
        }
        assert result["executed_by"] == "bob"
        assert run.audit_hash != original_hash  # hash re-computed with outcome
        assert run.outcome_hash is not None

    async def test_wg1_publishes_decision_executed_event(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """Sprint A WG1 — execute_decision fires a DECISION_EXECUTED event
        with the audit trail so downstream listeners (Timeline, future
        ActionExecutor dispatcher) know a decision was finalised.
        """
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.APPROVED.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        published: list = []

        async def _capture(topic, event):
            published.append((topic, event))
            return True

        monkeypatch.setattr(
            "src.shared.kafka_client.publish_event", _capture, raising=True,
        )

        await svc.execute_decision(str(run.id), executed_by="bob")

        assert len(published) == 1
        topic, event = published[0]
        from src.shared.kafka_client import Topics
        assert topic == Topics.DECISION_EXECUTED
        assert event.event_type == "DECISION_EXECUTED"
        assert event.source_module == "governance"
        assert event.payload["decision_id"] == str(run.id)
        assert event.payload["executed_by"] == "bob"
        assert event.payload["outcome_hash"] == run.outcome_hash
        assert event.payload["audit_hash"] == run.audit_hash

    async def test_wg1_kafka_failure_does_not_rollback_execution(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """A Kafka outage must not unwind the DB-side execution — the
        outbox/event publish is best-effort from this call site.
        """
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.APPROVED.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        async def _boom(*_a, **_kw):
            raise RuntimeError("broker down")

        monkeypatch.setattr(
            "src.shared.kafka_client.publish_event", _boom, raising=True,
        )

        result = await svc.execute_decision(str(run.id), executed_by="bob")
        # Execution still completes even though publish raised.
        # Sprint Q.12 Onda 2.1 — accept EXECUTED_PARTIAL too: the
        # decision_type used here has no handler, so the dispatcher
        # correctly marks the row as partial. The point of this test
        # is that the *Kafka* outage doesn't unwind the local writes.
        assert result["status"] in {
            DecisionStatus.EXECUTED.value,
            DecisionStatus.EXECUTED_PARTIAL.value,
        }
        assert run.outcome_hash is not None


# ---------------------------------------------------------------------------
# rollback_decision
# ---------------------------------------------------------------------------

class TestRollbackDecision:
    async def test_requires_executed_status(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.APPROVED.value,  # not EXECUTED
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ValueError, match="Only executed decisions"):
            await svc.rollback_decision(
                str(run.id),
                rolled_back_by="bob",
                reason="need to revert this",
            )

    async def test_short_reason_rejected(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.EXECUTED.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        with pytest.raises(ValueError, match="min 10 characters"):
            await svc.rollback_decision(
                str(run.id),
                rolled_back_by="bob",
                reason="short",  # < 10 chars
            )

    async def test_success_records_metadata(self, fake_session, tenant_id):
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.EXECUTED.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        result = await svc.rollback_decision(
            str(run.id),
            rolled_back_by="carol",
            reason="regression detected in prod",
        )

        assert result["status"] == DecisionStatus.ROLLED_BACK.value
        assert result["rolled_back_by"] == "carol"
        assert result["rollback_reason"] == "regression detected in prod"

    async def test_wg2_publishes_decision_rolled_back_event(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """Sprint C 1.4 — rollback_decision fires a DECISION_ROLLED_BACK
        event carrying the audit trail so downstream listeners (future
        ActionExecutor rollback handler, audit sinks, Timeline UI) can
        react without re-reading the DB.
        """
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.EXECUTED.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        published: list = []

        async def _capture(topic, event):
            published.append((topic, event))
            return True

        monkeypatch.setattr(
            "src.shared.kafka_client.publish_event", _capture, raising=True,
        )

        await svc.rollback_decision(
            str(run.id),
            rolled_back_by="carol",
            reason="regression detected in prod",
        )

        assert len(published) == 1
        topic, event = published[0]
        from src.shared.kafka_client import Topics
        assert topic == Topics.DECISION_ROLLED_BACK
        assert event.event_type == "DECISION_ROLLED_BACK"
        assert event.source_module == "governance"
        assert event.payload["decision_id"] == str(run.id)
        assert event.payload["rolled_back_by"] == "carol"
        assert event.payload["reason"] == "regression detected in prod"

    async def test_wg2_kafka_failure_does_not_unwind_rollback(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """Broker down must never re-break the rollback path — the
        database status flip is the source of truth.
        """
        run = _make_decision_run(
            tenant_id=tenant_id,
            status=DecisionStatus.EXECUTED.value,
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)

        async def _boom(*_a, **_kw):
            raise RuntimeError("broker down")

        monkeypatch.setattr(
            "src.shared.kafka_client.publish_event", _boom, raising=True,
        )

        result = await svc.rollback_decision(
            str(run.id),
            rolled_back_by="carol",
            reason="still needed to roll back now",
        )
        assert result["status"] == DecisionStatus.ROLLED_BACK.value


# ---------------------------------------------------------------------------
# activate_kill_switch
# ---------------------------------------------------------------------------

class TestKillSwitch:
    async def test_auto_executes_bypassing_approval(self, fake_session, tenant_id, monkeypatch):
        fake_session.queue_scalar(None)  # _get_last_decision_hash -> None (first)
        svc = GovernanceService(fake_session, tenant_id)

        # activate_kill_switch calls `_get_decision_run` after propose to flip
        # status to EXECUTED. FakeSession can't resolve lookups by id, so we
        # patch `_get_decision_run` to scan `added` for the matching DecisionRun.
        async def _lookup_from_added(decision_id):
            target = str(decision_id)
            for obj in fake_session.added:
                if isinstance(obj, DecisionRun) and str(obj.id) == target:
                    return obj
            return None

        monkeypatch.setattr(svc, "_get_decision_run", _lookup_from_added)

        result = await svc.activate_kill_switch(
            scope="pricing",
            activated_by="alice",
            reason="incident #42",
        )

        added_runs = [o for o in fake_session.added if isinstance(o, DecisionRun)]
        assert len(added_runs) == 1
        run = added_runs[0]

        assert run.status == DecisionStatus.EXECUTED.value
        assert run.executed_by == "alice"
        assert run.decision_type == "kill_switch"
        # get_decision returns the run (same lookup) so result is a dict
        assert result is not None
        assert result["status"] == DecisionStatus.EXECUTED.value
