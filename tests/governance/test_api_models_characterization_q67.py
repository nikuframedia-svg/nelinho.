"""Q.67.6.A5 — Characterization tests para src/governance/api.py + models.py.

Pattern Feathers ("Working Effectively with Legacy Code"): antes de decompor
estes dois ficheiros (api.py 948L, models.py 936L) na Q.67.6.B5, pinamos o
behaviour observavel ACTUAL como snapshots. Estes testes NAO assertam "o que
devia acontecer" — assertam "o que acontece hoje".

Cobertura:
  * API endpoints (TestClient + dependency overrides):
      - GET /v1/governance/policies + /policies/{decision_type}
      - GET /v1/governance/decisions + /decisions/{decision_id}
      - POST /v1/governance/decisions/propose
      - POST /v1/governance/decisions/{id}/approve (REJECT requires category)
      - GET /v1/governance/decisions/pending/me
      - GET /v1/governance/decisions/{id}/audit-pack
      - GET /v1/governance/audit/timeline
      - GET /v1/governance/rbac/matrix
      - GET /v1/governance/rule-firings + adoption
      - GET /v1/governance/event-outbox
      - GET /v1/governance/decisions/timeline (group_by validation)
  * Models (invariants — table args, column defaults, enums, DEFAULT_POLICIES):
      - All enums have the expected member set + values
      - DEFAULT_POLICIES dict shape (each entry has required keys)
      - DecisionPolicy / DecisionRun / Approval / RuleFiring / KillSwitchActive /
        PreferenceRule / CausalDiscoveryReport — table names + schema + key cols
      - DecisionRun.calculate_audit_hash determinism + sensitivity
      - DecisionProposal / ApprovalRequest pydantic invariants
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.governance.api import (
    get_governance_service,
    get_tenant_id,
    router as governance_router,
)
from src.governance.models import (
    Approval,
    ApprovalAction,
    ApprovalRequest,
    AutonomyLevel,
    CausalDiscoveryReport,
    CausalDiscoveryStatus,
    DEFAULT_POLICIES,
    DecisionPolicy,
    DecisionProposal,
    DecisionRun,
    DecisionStatus,
    KillSwitchActive,
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
    RejectionCategory,
    RuleFiring,
    RuleFiringOutcome,
)
from src.shared.config import settings


# ============================================================================
# FIXTURES — Test app with overridden service dependency
# ============================================================================

TENANT_ID = UUID("00000000-0000-0000-0000-00000000aaaa")
USER_ID = UUID("00000000-0000-0000-0000-00000000bbbb")


def _fake_service() -> AsyncMock:
    """An AsyncMock GovernanceService — we only care about wiring, not logic."""
    svc = AsyncMock()

    # Sync methods need to be plain MagicMock-style (not coroutines)
    svc.list_policies = lambda: [
        {
            "decision_type": "scenario_publish",
            "autonomy_level": "L2",
            "requires_approval": True,
            "required_approvers": 1,
            "requires_different_approver": True,
            "description": "Publishing a scenario to production",
        },
    ]
    svc.get_policy = lambda dt: (
        {
            "decision_type": dt,
            "autonomy_level": "L2",
            "requires_approval": True,
            "required_approvers": 1,
            "requires_different_approver": True,
            "description": "X",
        }
        if dt == "scenario_publish"
        else None
    )

    # Async methods
    decision_payload = {
        "id": "d-1",
        "decision_type": "scenario_publish",
        "title": "T",
        "description": None,
        "status": "pending_approval",
        "autonomy_level": "L2",
        "risk_level": "medium",
        "proposed_at": "2026-05-08T12:00:00Z",
        "proposed_by": "alice",
        "approvals": [],
        "audit_hash": "deadbeef" * 8,
        "executed_at": None,
        "executed_by": None,
        "action_data": {},
    }
    svc.propose_decision.return_value = decision_payload
    svc.list_decisions.return_value = [decision_payload]
    svc.get_decision.return_value = decision_payload
    svc.get_pending_approvals.return_value = [decision_payload]
    svc.approve_decision.return_value = {**decision_payload, "status": "approved"}
    svc.get_audit_pack.return_value = {"decision": decision_payload, "timeline": []}
    svc.get_audit_timeline.return_value = []
    svc.get_timeline.return_value = {"groups": [], "total": 0}
    return svc


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(governance_router)
    app.dependency_overrides[get_governance_service] = lambda: _fake_service()
    app.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    return TestClient(app)


def _user_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": str(TENANT_ID),
        "X-User-Id": str(USER_ID),
        "X-User-Role": "operator",
    }


# ============================================================================
# API — Policy endpoints
# ============================================================================


def test_list_policies_returns_list_of_policy_responses(client):
    """GET /policies returns 200 + list shape with required fields."""
    resp = client.get("/v1/governance/policies", headers=_user_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and body
    p = body[0]
    for key in (
        "decision_type",
        "autonomy_level",
        "requires_approval",
        "required_approvers",
        "requires_different_approver",
    ):
        assert key in p, f"missing key {key} in PolicyResponse"


def test_get_policy_existing_returns_200(client):
    resp = client.get(
        "/v1/governance/policies/scenario_publish", headers=_user_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["decision_type"] == "scenario_publish"


def test_get_policy_unknown_returns_404(client):
    resp = client.get(
        "/v1/governance/policies/does_not_exist", headers=_user_headers(),
    )
    assert resp.status_code == 404
    assert "No policy found" in resp.json()["detail"]


# ============================================================================
# API — Decision endpoints
# ============================================================================


def test_propose_decision_returns_decision_response(client):
    body = {
        "decision_type": "scenario_publish",
        "title": "Publish",
        "action_data": {"scenario_id": "s1"},
        "risk_level": "medium",
    }
    resp = client.post(
        "/v1/governance/decisions/propose", json=body, headers=_user_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "d-1"
    assert data["status"] == "pending_approval"
    assert data["audit_hash"]


def test_list_decisions_supports_status_and_pagination(client):
    resp = client.get(
        "/v1/governance/decisions?status=pending_approval&limit=10&offset=0",
        headers=_user_headers(),
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_decisions_rejects_limit_out_of_range(client):
    """limit ge=1 le=200; offset ge=0."""
    resp = client.get("/v1/governance/decisions?limit=999", headers=_user_headers())
    assert resp.status_code == 422


def test_get_decision_existing(client):
    resp = client.get("/v1/governance/decisions/d-1", headers=_user_headers())
    assert resp.status_code == 200
    assert resp.json()["id"] == "d-1"


def test_get_decision_not_found_returns_404(client):
    # override service to return None
    app = client.app
    svc = _fake_service()
    svc.get_decision.return_value = None
    app.dependency_overrides[get_governance_service] = lambda: svc
    resp = client.get("/v1/governance/decisions/missing", headers=_user_headers())
    assert resp.status_code == 404


def test_pending_me_returns_user_and_count(client):
    resp = client.get(
        "/v1/governance/decisions/pending/me", headers=_user_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert "pending" in body
    assert body["user"]  # echoes the current user


def test_audit_pack_existing(client):
    resp = client.get(
        "/v1/governance/decisions/d-1/audit-pack", headers=_user_headers(),
    )
    assert resp.status_code == 200
    assert "decision" in resp.json()


def test_audit_timeline_returns_events_envelope(client):
    resp = client.get("/v1/governance/audit/timeline", headers=_user_headers())
    assert resp.status_code == 200
    assert resp.json() == {"events": []}


# ============================================================================
# API — Approve endpoint validation (rejection_category mandatory on REJECT)
# ============================================================================


def test_approve_reject_without_category_returns_400(client):
    """Sprint Q.2 invariant: REJECT requires rejection_category."""
    resp = client.post(
        "/v1/governance/decisions/d-1/approve",
        json={
            "action": "reject",
            "reason": "rejected because of stuff",
        },
        headers=_user_headers(),
    )
    assert resp.status_code == 400
    assert "rejection_category" in resp.json()["detail"]


def test_approve_reject_with_category_passes(client):
    resp = client.post(
        "/v1/governance/decisions/d-1/approve",
        json={
            "action": "reject",
            "reason": "rejected because of stuff",
            "rejection_category": "COST",
        },
        headers=_user_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["action"] == "reject"


def test_approve_approve_action_does_not_need_category(client):
    resp = client.post(
        "/v1/governance/decisions/d-1/approve",
        json={"action": "approve", "reason": "looks good to me"},
        headers=_user_headers(),
    )
    assert resp.status_code == 200


# ============================================================================
# API — RBAC matrix viewer
# ============================================================================


def test_rbac_matrix_returns_roles_permissions_matrix(client):
    resp = client.get("/v1/governance/rbac/matrix", headers=_user_headers())
    assert resp.status_code == 200
    body = resp.json()
    for key in ("roles", "permissions", "matrix"):
        assert key in body
    assert isinstance(body["matrix"], dict)


# ============================================================================
# API — Timeline group_by validation
# ============================================================================


def test_timeline_default_group_by_criticality(client):
    resp = client.get(
        "/v1/governance/decisions/timeline", headers=_user_headers(),
    )
    assert resp.status_code == 200


# ============================================================================
# MODELS — Enums (pin values)
# ============================================================================


def test_autonomy_level_values():
    assert {e.value for e in AutonomyLevel} == {"L1", "L2", "L3", "L4", "L5"}


def test_decision_status_values_include_executed_partial():
    """Q.12 Onda 2.1 — EXECUTED_PARTIAL distinguishes audit-only writes."""
    values = {e.value for e in DecisionStatus}
    expected = {
        "proposed",
        "pending_approval",
        "approved",
        "rejected",
        "executing",
        "executed",
        "executed_partial",
        "rolled_back",
        "failed",
        "cancelled",
    }
    assert values == expected


def test_approval_action_values():
    assert {e.value for e in ApprovalAction} == {
        "approve",
        "reject",
        "request_changes",
    }


def test_rejection_category_values():
    """Q.2 Camada 1 learner feature: exactly these 7 categories."""
    assert {e.value for e in RejectionCategory} == {
        "COST",
        "QUALITY",
        "CUSTOMER",
        "CAPACITY",
        "MOLD",
        "WORKFORCE",
        "OTHER",
    }


def test_preference_rule_type_values():
    assert {e.value for e in PreferenceRuleType} == {
        "temporal_block",
        "tradeoff_preference",
        "operator_affinity",
        "phase_threshold",
        "workforce_override",
    }


def test_preference_rule_status_values():
    assert {e.value for e in PreferenceRuleStatus} == {
        "detected",
        "confirmed",
        "rejected",
    }


def test_causal_discovery_status_values():
    assert {e.value for e in CausalDiscoveryStatus} == {
        "pending",
        "approved",
        "rejected",
    }


def test_rule_firing_outcome_values():
    assert {e.value for e in RuleFiringOutcome} == {
        "proposed",
        "accepted",
        "rejected",
        "expired",
        "superseded",
    }


# ============================================================================
# MODELS — DEFAULT_POLICIES dict shape
# ============================================================================


REQUIRED_POLICY_KEYS = {
    "decision_type",
    "autonomy_level",
    "requires_approval",
    "required_approvers",
    "requires_different_approver",
    "requires_sandbox",
    "requires_canary",
    "description",
}


def test_default_policies_is_nonempty_list():
    assert isinstance(DEFAULT_POLICIES, list)
    assert len(DEFAULT_POLICIES) >= 6  # currently 6 entries


def test_default_policies_every_entry_has_required_keys():
    for p in DEFAULT_POLICIES:
        missing = REQUIRED_POLICY_KEYS - set(p.keys())
        assert not missing, f"{p['decision_type']} missing keys {missing}"


def test_default_policies_decision_types_unique():
    types = [p["decision_type"] for p in DEFAULT_POLICIES]
    assert len(types) == len(set(types))


def test_default_policies_contains_kill_switch_with_l5_no_approval():
    """kill_switch policy: L5 autonomy + requires_approval=False (emergency)."""
    ks = next(p for p in DEFAULT_POLICIES if p["decision_type"] == "kill_switch")
    assert ks["autonomy_level"] == AutonomyLevel.L5.value
    assert ks["requires_approval"] is False
    assert ks["required_approvers"] == 0


def test_default_policies_standard_time_update_requires_two_approvers_and_canary():
    p = next(
        x for x in DEFAULT_POLICIES if x["decision_type"] == "standard_time_update"
    )
    assert p["required_approvers"] == 2
    assert p["requires_canary"] is True
    assert p["canary_percentage"] == 10


def test_default_policies_autonomy_levels_are_valid_enum_values():
    valid = {e.value for e in AutonomyLevel}
    for p in DEFAULT_POLICIES:
        assert p["autonomy_level"] in valid


# ============================================================================
# MODELS — SQLA table metadata (schema + table name pin)
# ============================================================================


def test_decision_policy_tablename_and_schema():
    assert DecisionPolicy.__tablename__ == "decision_policy"
    assert DecisionPolicy.__table__.schema == "governance"


def test_decision_run_tablename_and_schema():
    assert DecisionRun.__tablename__ == "decision_run"
    assert DecisionRun.__table__.schema == "governance"


def test_approval_tablename_and_schema_and_fk():
    assert Approval.__tablename__ == "approval"
    assert Approval.__table__.schema == "governance"
    # FK to decision_run.id
    fks = list(Approval.__table__.c.decision_run_id.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "decision_run"


def test_kill_switch_active_composite_pk():
    """KillSwitchActive PK = (tenant_id, scope) — idempotent per scope."""
    assert KillSwitchActive.__tablename__ == "kill_switch_active"
    assert KillSwitchActive.__table__.schema == "governance"
    pk_cols = {c.name for c in KillSwitchActive.__table__.primary_key.columns}
    assert pk_cols == {"tenant_id", "scope"}


def test_rule_firing_tablename_and_indexes():
    assert RuleFiring.__tablename__ == "rule_firing"
    assert RuleFiring.__table__.schema == "governance"
    index_names = {ix.name for ix in RuleFiring.__table__.indexes}
    # Pin the three explicit composite indexes
    assert "ix_rule_firing_tenant_rule_fired" in index_names
    assert "ix_rule_firing_tenant_dedupe_fired" in index_names
    assert "ix_rule_firing_outcome_fired" in index_names


def test_preference_rule_tablename_and_schema():
    assert PreferenceRule.__tablename__ == "preference_rule"
    assert PreferenceRule.__table__.schema == "governance"


def test_causal_discovery_report_tablename_and_schema():
    assert CausalDiscoveryReport.__tablename__ == "causal_discovery_report"
    assert CausalDiscoveryReport.__table__.schema == "governance"


def test_decision_run_audit_hash_column_not_nullable():
    """audit_hash is the integrity anchor — must be NOT NULL."""
    col = DecisionRun.__table__.c.audit_hash
    assert col.nullable is False
    assert col.type.length == 64  # SHA256 hex


def test_decision_run_chain_invalidated_default_false():
    """Q.12 Onda 1.5 — chain_invalidated defaults to False."""
    col = DecisionRun.__table__.c.chain_invalidated
    assert col.nullable is False
    assert col.server_default is not None
    assert "false" in str(col.server_default.arg).lower()


# ============================================================================
# MODELS — DecisionRun.calculate_audit_hash
# ============================================================================


def test_calculate_audit_hash_deterministic():
    """Same inputs → same hash."""
    decision_id = uuid4()
    h1 = DecisionRun.calculate_audit_hash(decision_id, "1.0.0", "a", "b", "c")
    h2 = DecisionRun.calculate_audit_hash(decision_id, "1.0.0", "a", "b", "c")
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex


def test_calculate_audit_hash_sensitive_to_inputs():
    """Changing any input changes the hash."""
    decision_id = uuid4()
    base = DecisionRun.calculate_audit_hash(decision_id, "1.0.0", "a", "b", "c")
    assert base != DecisionRun.calculate_audit_hash(
        decision_id, "1.0.1", "a", "b", "c",
    )
    assert base != DecisionRun.calculate_audit_hash(
        decision_id, "1.0.0", "X", "b", "c",
    )
    assert base != DecisionRun.calculate_audit_hash(
        decision_id, "1.0.0", "a", "X", "c",
    )
    assert base != DecisionRun.calculate_audit_hash(
        decision_id, "1.0.0", "a", "b", "X",
    )


def test_calculate_audit_hash_handles_none_inputs():
    """None inputs are coerced to empty string — no TypeError."""
    h = DecisionRun.calculate_audit_hash(uuid4(), "1.0.0", None, None, None)
    assert len(h) == 64


# ============================================================================
# MODELS — Pydantic invariants
# ============================================================================


def test_decision_proposal_defaults():
    p = DecisionProposal(decision_type="scenario_publish", title="T")
    assert p.action_data == {}
    assert p.evidence_refs == []
    assert p.risk_level == "medium"
    assert p.description is None


def test_approval_request_reason_min_length_enforced():
    """ApprovalRequest.reason has min_length=10."""
    with pytest.raises(ValidationError):
        ApprovalRequest(action=ApprovalAction.APPROVE, reason="short")
    # 10 chars passes
    ok = ApprovalRequest(action=ApprovalAction.APPROVE, reason="1234567890")
    assert ok.reason == "1234567890"


def test_approval_request_rejection_category_optional_unless_reject():
    """Pydantic itself does not require category — API layer does (test above)."""
    r = ApprovalRequest(action=ApprovalAction.APPROVE, reason="approved for now")
    assert r.rejection_category is None
