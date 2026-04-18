"""
Tests for Sprint M.1 (timeline) + M.2 (bulk) + M.4 (modify_payload) +
M.5 (auto-approval) + M.6 (audit timeline).

Strategy: `FakeSession` mock — same pattern as existing `test_service.py`.
No real DB. We drive `GovernanceService` directly to avoid hauling up
governance/api's Header-based dependencies.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import pytest

from src.core.models.tenant_configuration import TenantConfiguration
from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.governance.models import (
    Approval,
    ApprovalAction,
    AutonomyLevel,
    DecisionRun,
    DecisionStatus,
)
from src.governance.service import (
    GovernanceService,
    SoDViolationError,
    _impact_magnitude,
    _risk_at_or_below,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors tests/governance/test_service.py)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


def _run(
    *,
    tenant_id: UUID,
    status: str = DecisionStatus.PENDING_APPROVAL.value,
    decision_type: str = "scenario_publish",
    risk_level: str = "medium",
    proposed_by: str = "alice",
    proposed_at: Optional[datetime] = None,
    expected_impact=None,
    approvals: Optional[List[Approval]] = None,
    action_data=None,
) -> DecisionRun:
    r = DecisionRun(
        id=uuid4(),
        tenant_id=tenant_id,
        decision_type=decision_type,
        title=f"test {decision_type}",
        description=None,
        status=status,
        policy_version="1.0.0",
        autonomy_level=AutonomyLevel.L2.value,
        action_data=action_data or {"foo": "bar"},
        expected_impact=expected_impact,
        risk_level=risk_level,
        scenario_id=None,
        evidence_refs=[],
        input_snapshot_hash="deadbeef",
        prev_hash=None,
        audit_hash="abcd",
        proposed_by=proposed_by,
        proposed_at=proposed_at or datetime.now(timezone.utc),
    )
    r.approvals = list(approvals or [])
    return r


# ---------------------------------------------------------------------------
# _risk_at_or_below / _impact_magnitude
# ---------------------------------------------------------------------------

def test_risk_at_or_below_ordering():
    assert _risk_at_or_below("low", "low") is True
    assert _risk_at_or_below("low", "medium") is True
    assert _risk_at_or_below("medium", "low") is False
    assert _risk_at_or_below("critical", "high") is False
    assert _risk_at_or_below("high", "critical") is True


def test_impact_magnitude_picks_preferred_keys():
    assert _impact_magnitude({"magnitude": 7.5}) == 7.5
    assert _impact_magnitude({"delta": -3.0}) == 3.0
    # falls back to first numeric value
    assert _impact_magnitude({"note": "x", "score": 2.0}) == 2.0
    # no numerics → 0
    assert _impact_magnitude({"note": "x"}) == 0.0
    assert _impact_magnitude(None) == 0.0


# ---------------------------------------------------------------------------
# M.1 — get_timeline
# ---------------------------------------------------------------------------

class TestTimeline:
    @pytest.mark.asyncio
    async def test_rejects_unknown_group_by(self, fake_session, tenant_id):
        svc = GovernanceService(fake_session, tenant_id)
        with pytest.raises(ValueError):
            await svc.get_timeline(group_by="popularity")

    @pytest.mark.asyncio
    async def test_groups_by_risk_level(self, fake_session, tenant_id):
        rows = [
            _run(tenant_id=tenant_id, risk_level="low"),
            _run(tenant_id=tenant_id, risk_level="low"),
            _run(tenant_id=tenant_id, risk_level="high"),
            _run(tenant_id=tenant_id, risk_level="critical"),
        ]
        fake_session.queue_scalars(rows)

        svc = GovernanceService(fake_session, tenant_id)
        out = await svc.get_timeline(group_by="criticality")

        keys = [g["key"] for g in out["groups"]]
        # critical > high > low
        assert keys == ["critical", "high", "low"]
        counts = {g["key"]: g["count"] for g in out["groups"]}
        assert counts == {"critical": 1, "high": 1, "low": 2}
        assert out["aggregated_kpis"]["pending_count"] == 4

    @pytest.mark.asyncio
    async def test_overdue_detection(self, fake_session, tenant_id):
        old = datetime.now(timezone.utc) - timedelta(hours=48)
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        fake_session.queue_scalars([
            _run(tenant_id=tenant_id, proposed_at=old),
            _run(tenant_id=tenant_id, proposed_at=recent),
        ])
        svc = GovernanceService(fake_session, tenant_id)
        out = await svc.get_timeline(group_by="risk_level")
        assert out["aggregated_kpis"]["overdue_count"] == 1

    @pytest.mark.asyncio
    async def test_hide_low_risk_filter(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            _run(tenant_id=tenant_id, risk_level="low"),
            _run(tenant_id=tenant_id, risk_level="high"),
        ])
        svc = GovernanceService(fake_session, tenant_id)
        out = await svc.get_timeline(group_by="risk_level", hide_low_risk=True)
        keys = {g["key"] for g in out["groups"]}
        assert keys == {"high"}
        # aggregated kpis still see both rows (transparency)
        assert out["aggregated_kpis"]["pending_count"] == 2

    @pytest.mark.asyncio
    async def test_min_impact_filter(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            _run(tenant_id=tenant_id, expected_impact={"magnitude": 10.0}),
            _run(tenant_id=tenant_id, expected_impact={"magnitude": 1.0}),
            _run(tenant_id=tenant_id, expected_impact=None),
        ])
        svc = GovernanceService(fake_session, tenant_id)
        out = await svc.get_timeline(group_by="risk_level", min_impact=5.0)
        total_shown = sum(g["count"] for g in out["groups"])
        assert total_shown == 1

    @pytest.mark.asyncio
    async def test_max_per_user_cap(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            _run(tenant_id=tenant_id, risk_level="high", proposed_by="alice"),
            _run(tenant_id=tenant_id, risk_level="high", proposed_by="alice"),
            _run(tenant_id=tenant_id, risk_level="high", proposed_by="alice"),
            _run(tenant_id=tenant_id, risk_level="high", proposed_by="bob"),
        ])
        svc = GovernanceService(fake_session, tenant_id)
        out = await svc.get_timeline(group_by="risk_level", max_per_user_shown=1)
        # 1 alice + 1 bob = 2
        total = sum(g["count"] for g in out["groups"])
        assert total == 2


# ---------------------------------------------------------------------------
# M.2 — bulk_act
# ---------------------------------------------------------------------------

class TestBulk:
    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self, fake_session, tenant_id):
        # One approvable, one SoD-violating (same user as proposer).
        ok_run = _run(tenant_id=tenant_id, proposed_by="alice")
        sod_run = _run(tenant_id=tenant_id, proposed_by="bob")

        # Two approve_decision calls → two _get_decision_run lookups.
        fake_session.queue_scalar(ok_run)
        fake_session.queue_scalar(sod_run)

        svc = GovernanceService(fake_session, tenant_id)
        results = await svc.bulk_act(
            items=[
                {"decision_id": str(ok_run.id), "action": "approve", "reason": "looks fine"},
                {"decision_id": str(sod_run.id), "action": "approve", "reason": "by bob himself"},
            ],
            approved_by="bob",
        )
        assert len(results) == 2
        assert results[0]["status"] == "ok"
        # bob approving their own decision → SoDViolationError
        assert results[1]["status"] == "error"
        assert "Separation of Duties" in results[1]["error"]

    @pytest.mark.asyncio
    async def test_bad_action_reported_per_item(self, fake_session, tenant_id):
        svc = GovernanceService(fake_session, tenant_id)
        results = await svc.bulk_act(
            items=[{"decision_id": "abc", "action": "nonsense", "reason": "x" * 12}],
            approved_by="carol",
        )
        assert results[0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_fields_reported(self, fake_session, tenant_id):
        svc = GovernanceService(fake_session, tenant_id)
        results = await svc.bulk_act(
            items=[
                {"action": "approve", "reason": "no id"},
                {"decision_id": "abc", "reason": "no action"},
            ],
            approved_by="dave",
        )
        assert all(r["status"] == "error" for r in results)


# ---------------------------------------------------------------------------
# M.4 — modify_payload
# ---------------------------------------------------------------------------

class TestModifyPayload:
    @pytest.mark.asyncio
    async def test_rejects_short_reason(self, fake_session, tenant_id):
        svc = GovernanceService(fake_session, tenant_id)
        with pytest.raises(ValueError):
            await svc.modify_payload(
                decision_id=str(uuid4()),
                patch={"edd_gap": 10},
                modified_by="alice",
                reason="too short",  # < 10 chars
            )

    @pytest.mark.asyncio
    async def test_rejects_modification_of_non_pending_decision(self, fake_session, tenant_id):
        run = _run(tenant_id=tenant_id, status=DecisionStatus.EXECUTED.value)
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)
        with pytest.raises(ValueError):
            await svc.modify_payload(
                decision_id=str(run.id),
                patch={"edd_gap": 10},
                modified_by="alice",
                reason="valid reason here",
            )

    @pytest.mark.asyncio
    async def test_merges_patch_and_records_history(self, fake_session, tenant_id):
        run = _run(
            tenant_id=tenant_id,
            action_data={"edd_gap": 5, "buffer_pct": 0.1},
        )
        fake_session.queue_scalar(run)
        svc = GovernanceService(fake_session, tenant_id)
        result = await svc.modify_payload(
            decision_id=str(run.id),
            patch={"edd_gap": 7},
            modified_by="bob",
            reason="safer buffer needed",
        )
        # Merged: edd_gap replaced, buffer_pct preserved
        assert run.action_data["edd_gap"] == 7
        assert run.action_data["buffer_pct"] == 0.1
        history = run.action_data["__modifications__"]
        assert len(history) == 1
        assert history[0]["modified_by"] == "bob"
        assert history[0]["reason"] == "safer buffer needed"
        assert "before_hash" in history[0]
        assert "after_hash" in history[0]
        # Audit hash was re-derived
        assert result["audit_hash"] == run.audit_hash


# ---------------------------------------------------------------------------
# M.5 — auto-approval via TenantConfig
# ---------------------------------------------------------------------------

def _cfg_row(tenant_id: UUID, key: str, value, data_type: str):
    return TenantConfiguration(
        id=uuid4(),
        tenant_id=tenant_id,
        category="governance",
        key=key,
        value=TenantConfiguration.wrap(value),
        data_type=data_type,
        valid_from=datetime.utcnow(),
        created_at=datetime.utcnow(),
        last_modified_at=datetime.utcnow(),
    )


class TestAutoApproval:
    @pytest.mark.asyncio
    async def test_respects_enabled_flag(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            _cfg_row(tenant_id, "auto_approval.scenario_publish.enabled", True, "bool"),
            _cfg_row(tenant_id, "auto_approval.scenario_publish.risk_ceiling", "low", "string"),
        ])
        svc = GovernanceService(fake_session, tenant_id)
        allowed = await svc._auto_approval_allowed(
            decision_type="scenario_publish", risk_level="low",
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_risk_above_ceiling_blocks_auto_approval(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            _cfg_row(tenant_id, "auto_approval.scenario_publish.enabled", True, "bool"),
            _cfg_row(tenant_id, "auto_approval.scenario_publish.risk_ceiling", "low", "string"),
        ])
        svc = GovernanceService(fake_session, tenant_id)
        allowed = await svc._auto_approval_allowed(
            decision_type="scenario_publish", risk_level="high",
        )
        assert allowed is False

    @pytest.mark.asyncio
    async def test_missing_config_defaults_to_no(self, fake_session, tenant_id):
        fake_session.queue_scalars([])  # empty governance category
        svc = GovernanceService(fake_session, tenant_id)
        allowed = await svc._auto_approval_allowed(
            decision_type="scenario_publish", risk_level="low",
        )
        assert allowed is False


# ---------------------------------------------------------------------------
# M.6 — cross-decision audit timeline
# ---------------------------------------------------------------------------

class TestAuditTimeline:
    @pytest.mark.asyncio
    async def test_emits_all_event_types(self, fake_session, tenant_id):
        now = datetime.now(timezone.utc)
        r = _run(
            tenant_id=tenant_id,
            status=DecisionStatus.EXECUTED.value,
            proposed_at=now - timedelta(hours=3),
        )
        r.approved_at = now - timedelta(hours=2)
        r.executed_at = now - timedelta(hours=1)
        r.executed_by = "carol"
        r.approvals = [Approval(
            id=uuid4(),
            tenant_id=tenant_id,
            decision_run_id=r.id,
            action="approve",
            approved_by="bob",
            reason="LGTM",
            approved_at=now - timedelta(hours=2),
        )]
        fake_session.queue_scalars([r])

        svc = GovernanceService(fake_session, tenant_id)
        events = await svc.get_audit_timeline()
        event_names = [e["event"] for e in events]
        assert "proposed" in event_names
        assert "approval_approve" in event_names
        assert "executed" in event_names

    @pytest.mark.asyncio
    async def test_filter_by_actor(self, fake_session, tenant_id):
        r = _run(
            tenant_id=tenant_id,
            status=DecisionStatus.EXECUTED.value,
            proposed_by="alice",
        )
        r.executed_at = datetime.now(timezone.utc)
        r.executed_by = "carol"
        r.approvals = []
        fake_session.queue_scalars([r])
        svc = GovernanceService(fake_session, tenant_id)
        events = await svc.get_audit_timeline(actor="carol")
        # Only the 'executed' event matches actor=carol.
        assert [e["event"] for e in events] == ["executed"]
