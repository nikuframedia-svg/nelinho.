"""Tests for ``RuleProposalService`` lifecycle transitions + audit revisions.

Uses an in-memory FakeSession because the production models depend on
PostgreSQL features (JSONB, schemas) that don't translate to SQLite.
The tests focus on:

- 5 valid transitions (propose → approve, propose → reject, active →
  suspend, active/suspended → rollback).
- Illegal transitions raise ``RuleProposalError``.
- Each transition creates exactly one revision row with the right action.
- Audit fields (proposed_at/approved_at/activated_at) are populated.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.governance.yaml_policy.models import (
    RuleLifecycleStatus,
    RuleRevisionAction,
    TenantRule,
    TenantRuleRevision,
)
from src.governance.yaml_policy.rule_schema import (
    ActionType,
    EventType,
    Rule,
)
from src.governance.yaml_policy.service import (
    RuleProposalError,
    RuleProposalService,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, value: Any):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return list(self._value) if isinstance(self._value, list) else []

    def scalar_one_or_none(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value


class FakeSession:
    """Minimal AsyncSession stand-in.

    Only implements the methods RuleProposalService uses:
    ``add``, ``flush``, ``execute``. Stores objects in two lists by type
    so we can assert what landed without needing real SQL.
    """

    def __init__(self):
        self.rules: list[TenantRule] = []
        self.revisions: list[TenantRuleRevision] = []
        self.flush_count = 0

    def add(self, obj: Any) -> None:
        if isinstance(obj, TenantRule):
            if obj.id is None:
                obj.id = uuid4()
            self.rules.append(obj)
        elif isinstance(obj, TenantRuleRevision):
            if obj.id is None:
                obj.id = uuid4()
            self.revisions.append(obj)

    async def flush(self) -> None:
        # Mimic real flush: assign UUIDs to anything missing one
        for r in self.rules:
            if r.id is None:
                r.id = uuid4()
        self.flush_count += 1

    async def execute(self, stmt) -> _FakeResult:
        # We don't parse the statement — for these tests, the service
        # only does a couple of select shapes. We respond with current
        # in-memory state in matching form. Keep it simple: list_rules
        # returns all rules; get_rule returns first match by rule_id;
        # get_revisions returns by rule_db_id. The caller's filtering
        # logic (status filter, etc.) is exercised by inspecting the
        # service-side post-conditions, not this fixture.
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        if "FROM governance.yaml_policy_rule" in compiled and "rule_id =" in compiled:
            # get_rule(rule_id) — find by rule_id
            return _FakeResult(list(self.rules))
        if "FROM governance.yaml_policy_rule" in compiled:
            # list_rules
            return _FakeResult(list(self.rules))
        if "FROM governance.yaml_policy_rule_revision" in compiled:
            return _FakeResult(list(self.revisions))
        return _FakeResult([])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


TENANT = UUID("11111111-1111-1111-1111-111111111111")
USER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_rule(rid: str = "test-rule-001") -> Rule:
    return Rule.model_validate({
        "id": rid,
        "description": "Test rule",
        "when": {
            "event": EventType.MOLD_USAGE_THRESHOLD.value,
            "conditions": [
                {"field": "uses_count", "op": "gte", "value": 800},
            ],
        },
        "then": [
            {
                "action": ActionType.ALERT.value,
                "params": {
                    "severity": "high",
                    "title": "x",
                    "message_pt": "y",
                    "entity_refs": [],
                },
            },
        ],
    })


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_persists_rule_and_revision():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    rule = _make_rule()

    row = await svc.propose(rule=rule, proposed_by_user_id=USER_A, nl_source="quero alertar")

    assert row.tenant_id == TENANT
    assert row.rule_id == "test-rule-001"
    assert row.status is RuleLifecycleStatus.PROPOSED
    assert row.proposed_by_user_id == USER_A
    assert row.proposed_at is not None
    assert row.event_type == EventType.MOLD_USAGE_THRESHOLD.value
    assert row.payload["id"] == "test-rule-001"

    assert len(session.rules) == 1
    assert len(session.revisions) == 1
    rev = session.revisions[0]
    assert rev.action is RuleRevisionAction.PROPOSED
    assert rev.actor_user_id == USER_A
    assert rev.payload_before is None
    assert rev.payload_after["id"] == "test-rule-001"
    assert rev.nl_source == "quero alertar"


@pytest.mark.asyncio
async def test_propose_duplicate_id_rejects():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    rule = _make_rule()

    await svc.propose(rule=rule, proposed_by_user_id=USER_A)
    with pytest.raises(RuleProposalError, match="already exists"):
        await svc.propose(rule=rule, proposed_by_user_id=USER_A)


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_transitions_to_active_and_logs_revision():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)

    row = await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B, reason="ok")

    assert row.status is RuleLifecycleStatus.ACTIVE
    assert row.approved_by_user_id == USER_B
    assert row.approved_at is not None
    assert row.activated_at is not None
    # 2 revisions: proposed + approved
    assert len(session.revisions) == 2
    assert session.revisions[1].action is RuleRevisionAction.APPROVED
    assert session.revisions[1].reason == "ok"


@pytest.mark.asyncio
async def test_approve_rejects_already_active():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)

    with pytest.raises(RuleProposalError, match="cannot approve"):
        await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)


@pytest.mark.asyncio
async def test_approve_rejects_unknown_rule():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    with pytest.raises(RuleProposalError, match="not found"):
        await svc.approve(rule_id="ghost", approver_user_id=USER_B)


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_transitions_to_rejected():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)

    row = await svc.reject(rule_id="test-rule-001", actor_user_id=USER_B, reason="duplicate")

    assert row.status is RuleLifecycleStatus.REJECTED
    assert session.revisions[1].action is RuleRevisionAction.REJECTED
    assert session.revisions[1].reason == "duplicate"


@pytest.mark.asyncio
async def test_reject_requires_reason():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    with pytest.raises(RuleProposalError, match="non-empty reason"):
        await svc.reject(rule_id="test-rule-001", actor_user_id=USER_B, reason="")


@pytest.mark.asyncio
async def test_reject_rejects_active_rule():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)
    with pytest.raises(RuleProposalError, match="cannot reject"):
        await svc.reject(rule_id="test-rule-001", actor_user_id=USER_B, reason="late")


# ---------------------------------------------------------------------------
# suspend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspend_active_rule():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)

    row = await svc.suspend(rule_id="test-rule-001", actor_user_id=USER_B, reason="pause")
    assert row.status is RuleLifecycleStatus.SUSPENDED
    assert row.suspended_at is not None
    assert session.revisions[2].action is RuleRevisionAction.SUSPENDED


@pytest.mark.asyncio
async def test_suspend_proposed_rule_rejects():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    with pytest.raises(RuleProposalError, match="cannot suspend"):
        await svc.suspend(rule_id="test-rule-001", actor_user_id=USER_B)


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_active_rule():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)

    row = await svc.rollback(rule_id="test-rule-001", actor_user_id=USER_B, reason="bad effect")
    assert row.status is RuleLifecycleStatus.ROLLED_BACK
    assert session.revisions[2].action is RuleRevisionAction.ROLLED_BACK
    assert session.revisions[2].reason == "bad effect"


@pytest.mark.asyncio
async def test_rollback_suspended_rule():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)
    await svc.suspend(rule_id="test-rule-001", actor_user_id=USER_B)

    row = await svc.rollback(rule_id="test-rule-001", actor_user_id=USER_B, reason="enough")
    assert row.status is RuleLifecycleStatus.ROLLED_BACK


@pytest.mark.asyncio
async def test_rollback_requires_reason():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B)
    with pytest.raises(RuleProposalError, match="non-empty reason"):
        await svc.rollback(rule_id="test-rule-001", actor_user_id=USER_B, reason="")


@pytest.mark.asyncio
async def test_rollback_rejects_proposed_rule():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A)
    with pytest.raises(RuleProposalError, match="cannot rollback"):
        await svc.rollback(rule_id="test-rule-001", actor_user_id=USER_B, reason="x")


# ---------------------------------------------------------------------------
# Audit chain integrity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_blocked_by_safety_check_q17e():
    """Q.17.E — approve raises RuleSafetyError when axiom check fails."""
    from src.governance.yaml_policy.safety_checks import RuleSafetyError

    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    bad_rule = Rule.model_validate({
        "id": "bad-capacity-rule",
        "description": "Tries to set negative truck capacity.",
        "when": {
            "event": EventType.SCHEDULE_PROPOSE.value,
            "conditions": [],
        },
        "then": [
            {
                "action": "set_config",
                "params": {
                    "category": "transporte", "key": "truck.capacity",
                    "value": -50, "reason_pt": "broken",
                },
            },
        ],
        "constraints": {"axioms_required": ["capacity_non_negative"]},
    })
    await svc.propose(rule=bad_rule, proposed_by_user_id=USER_A)
    with pytest.raises(RuleSafetyError) as exc_info:
        await svc.approve(rule_id="bad-capacity-rule", approver_user_id=USER_B)
    assert any("capacity_non_negative" in v.code for v in exc_info.value.violations)


@pytest.mark.asyncio
async def test_approve_skip_safety_checks_flag_q17e():
    """Admin escape hatch: skip_safety_checks=True bypasses gate."""
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)
    bad_rule = Rule.model_validate({
        "id": "bad-capacity-rule",
        "description": "Tries to set negative truck capacity.",
        "when": {"event": EventType.SCHEDULE_PROPOSE.value, "conditions": []},
        "then": [
            {
                "action": "set_config",
                "params": {
                    "category": "transporte", "key": "truck.capacity",
                    "value": -50, "reason_pt": "broken",
                },
            },
        ],
        "constraints": {"axioms_required": ["capacity_non_negative"]},
    })
    await svc.propose(rule=bad_rule, proposed_by_user_id=USER_A)
    row = await svc.approve(
        rule_id="bad-capacity-rule",
        approver_user_id=USER_B,
        skip_safety_checks=True,
    )
    assert row.status is RuleLifecycleStatus.ACTIVE


@pytest.mark.asyncio
async def test_full_lifecycle_produces_4_revisions_in_order():
    session = FakeSession()
    svc = RuleProposalService(session, TENANT)

    await svc.propose(rule=_make_rule(), proposed_by_user_id=USER_A, nl_source="x")
    await svc.approve(rule_id="test-rule-001", approver_user_id=USER_B, reason="ok")
    await svc.suspend(rule_id="test-rule-001", actor_user_id=USER_B, reason="brief pause")
    await svc.rollback(rule_id="test-rule-001", actor_user_id=USER_B, reason="bad outcome")

    actions = [r.action for r in session.revisions]
    assert actions == [
        RuleRevisionAction.PROPOSED,
        RuleRevisionAction.APPROVED,
        RuleRevisionAction.SUSPENDED,
        RuleRevisionAction.ROLLED_BACK,
    ]
