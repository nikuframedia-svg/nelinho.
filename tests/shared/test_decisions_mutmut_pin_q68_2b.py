"""Q.68.2.B — Mutation-pin tests for src.shared.api.decisions.

Context
=======
Q.68.1.E baseline measured **182 survivors** in `src/shared/api/decisions.py`
(562L, decision ledger: propose / approve / execute / rollback / audit). The
prior Q.61.41 smoke run captured only the survivor IDs (output of
`mutmut results`), not the per-mutant diffs — the live cache currently
holds fitness.py survivors, not decisions.py.

This file pins the **categories** of mutations that mutmut produces on a
FastAPI router of this shape, derived from:

  * The 5 categories documented in `agent_docs/q68_mutmut_baseline_real.md`
    (magic-number tweaks, comparator flips, `or default` removal,
    branch dispatch / None substitution, identifier renames).
  * Manual diff of `decisions.py` against the standard mutmut operator
    catalog (`mutmut.mutate_inline`).

Pin targets — 30 tests across 4 endpoints
-----------------------------------------
* `propose_decision`  (10): savepoint + UoW + status="PROPOSED" + audit
* `approve_decision`  (10): status gate + SoD invocation + find_or_create
* `execute_decision`  (5):  status=APPROVED gate + advisory_mode=True
* `rollback_decision` (5):  status=EXECUTED gate + 24h window boundary

Each test cites the mutmut category it pins. Run:

    .venv\\Scripts\\python.exe -m pytest tests/shared/test_decisions_mutmut_pin_q68_2b.py -v

Q.68.2.B follow-up — once a focused `mutmut run --paths-to-mutate
src/shared/api/decisions.py` completes with a preserved cache, port any
remaining survivors here with explicit mutant IDs in the docstring.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.api.decisions import router as decisions_router
from src.shared.database import get_session
from src.shared.models.governance import (
    ApprovalStatus,
    DecisionApproval,
    DecisionStatus,
    SharedDecisionRun,
)


TENANT = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PROPOSER = UUID("11111111-1111-1111-1111-111111111111")
APPROVER = UUID("22222222-2222-2222-2222-222222222222")


# ---------------------------------------------------------------------------
# FakeSession scaffolding — modelled on Q.61.10 _ProposeSession +
# Q.61.09 _ApproveSession but consolidated for reuse across propose /
# approve / execute / rollback / audit.
# ---------------------------------------------------------------------------


class _NestedTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _DecisionsSession:
    """Reusable FakeSession for decisions.py.

    * `add` captures objects and auto-populates `.id` (mimics flush
      side-effect of real Postgres).
    * `get(Model, id)` returns the configured `decision` (or None).
    * `execute(stmt)` returns a stub `Result` with
      `scalar_one_or_none`, `scalar`, `scalars().all()`.
    * `begin_nested()` is counted (UoW invariant 7 must open exactly 1).
    """

    def __init__(
        self,
        *,
        decision: Optional[Any] = None,
        existing_approval: Optional[Any] = None,
        approvals_list: Optional[List[Any]] = None,
        count_value: int = 0,
    ) -> None:
        self.decision = decision
        self.existing_approval = existing_approval
        self.approvals_list = approvals_list or []
        self.count_value = count_value
        self.added: List[Any] = []
        self.flushes = 0
        self.commits = 0
        self.begin_nested_calls = 0

    def add(self, obj: Any) -> None:
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def get(self, _model, _id):
        return self.decision

    def begin_nested(self) -> _NestedTx:
        self.begin_nested_calls += 1
        return _NestedTx()

    async def execute(self, _stmt):
        approvals = self.approvals_list
        existing = self.existing_approval
        count_value = self.count_value

        class _Scalars:
            def all(self_inner):
                return approvals

        class _Result:
            def scalar_one_or_none(self_inner):
                return existing

            def scalar(self_inner):
                return count_value

            def scalars(self_inner):
                return _Scalars()

        return _Result()


def _client(session: _DecisionsSession) -> TestClient:
    app = FastAPI()
    app.include_router(decisions_router, prefix="/v1")

    async def _fake_session():
        yield session

    app.dependency_overrides[get_session] = _fake_session
    return TestClient(app, raise_server_exceptions=False)


def _hdr(tenant: UUID = TENANT, user: UUID = PROPOSER) -> dict:
    return {"x-tenant-id": str(tenant), "x-user-id": str(user)}


def _make_decision(
    *,
    status_value: str = DecisionStatus.PROPOSED.value,
    proposer: UUID = PROPOSER,
    executed_at: Optional[datetime] = None,
    tenant: UUID = TENANT,
) -> SimpleNamespace:
    """Lightweight decision stand-in that quacks like SharedDecisionRun."""
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant,
        title="pin",
        action_type="GENERIC_ACTION",
        target="t",
        status=status_value,
        sandbox_result={},
        before_state={"qty": 1},
        after_state={"qty": 2},
        proposed_by=proposer,
        proposed_at=datetime.utcnow() - timedelta(hours=1),
        executed_at=executed_at,
        rolled_back_at=None,
    )


# ===========================================================================
# 1) PROPOSE — 10 pin tests
# ===========================================================================


class TestProposePinned:
    """Pins mutations in `propose_decision` (lines 83-152)."""

    def test_propose_returns_201_not_200_q68_2b(self):
        """Mutmut category 1 (magic-number tweak): `status_code=status.HTTP_201_CREATED`
        flipped to 200/204. Pin: response status MUST be exactly 201."""
        session = _DecisionsSession()
        resp = _client(session).post(
            "/v1/decisions/propose",
            headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        assert resp.status_code == 201, resp.text

    def test_propose_status_is_exactly_PROPOSED_string_q68_2b(self):
        """Mutmut category 5 (string rename): `DecisionStatus.PROPOSED.value`
        replaced with `"XXPROPOSEDXX"` or `.name`. Pin: literal "PROPOSED"."""
        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": None, "before_state": {}, "after_state": None},
        )
        runs = [o for o in session.added if isinstance(o, SharedDecisionRun)]
        assert len(runs) == 1
        assert runs[0].status == "PROPOSED"  # literal — not enum, not "proposed"

    def test_propose_opens_exactly_one_savepoint_q68_2b(self):
        """Mutmut category 1 (magic-number tweak) on `begin_nested_calls == 1`:
        savepoint dropped / duplicated. Pin: exactly 1 nested tx (UoW invariant 7)."""
        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        assert session.begin_nested_calls == 1

    def test_propose_writes_decision_run_AND_audit_log_q68_2b(self):
        """Mutmut category 4 (branch dispatch): `audit_change(...)` line replaced
        with `None` or skipped. Pin: BOTH SharedDecisionRun AND AuditLog in
        session.added — invariant 7 (audit in same tx as state change)."""
        from src.core.models.audit import AuditLog

        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        runs = [o for o in session.added if isinstance(o, SharedDecisionRun)]
        audits = [o for o in session.added if isinstance(o, AuditLog)]
        assert len(runs) == 1, "decision_run missing"
        assert len(audits) == 1, "audit_log missing — invariant 7 broken"

    def test_propose_audit_action_is_INSERT_not_UPDATE_q68_2b(self):
        """Mutmut category 5 (string rename): `action="INSERT"` mutated to
        `"UPDATE"`. Pin: propose always writes INSERT audit row."""
        from src.core.models.audit import AuditLog

        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        audits = [o for o in session.added if isinstance(o, AuditLog)]
        assert audits[0].action == "INSERT"

    def test_propose_audit_entity_type_is_decision_run_q68_2b(self):
        """Mutmut category 5: `entity_type="decision_run"` mutated. Pin: literal."""
        from src.core.models.audit import AuditLog

        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        audits = [o for o in session.added if isinstance(o, AuditLog)]
        assert audits[0].entity_type == "decision_run"

    def test_propose_audit_actor_id_is_user_not_tenant_q68_2b(self):
        """Mutmut category 4 (variable-swap): `actor_id=user_id` mutated to
        `actor_id=tenant_id`. Pin: actor_id is the PROPOSER UUID."""
        from src.core.models.audit import AuditLog

        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        audits = [o for o in session.added if isinstance(o, AuditLog)]
        assert audits[0].actor_id == PROPOSER
        assert audits[0].actor_id != TENANT

    def test_propose_does_NOT_create_DecisionApproval_q68_2b(self):
        """Mutmut category 4 (branch dispatch): re-introducing self-approval
        placeholder. Pin (Q.61.09 regression): zero DecisionApproval in added."""
        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        approvals = [o for o in session.added if isinstance(o, DecisionApproval)]
        assert approvals == []

    def test_propose_flush_is_called_inside_savepoint_q68_2b(self):
        """Mutmut category 3 (default removal): `await session.flush()` dropped.
        Pin: flush invoked at least once (needed to populate decision.id)."""
        session = _DecisionsSession()
        _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        assert session.flushes >= 1

    def test_propose_response_body_shape_q68_2b(self):
        """Mutmut category 5 (string rename) on response keys. Pin: exact
        public contract — frontend reads {id, status, message}."""
        session = _DecisionsSession()
        resp = _client(session).post(
            "/v1/decisions/propose", headers=_hdr(),
            json={"title": "x", "action_type": "GENERIC_ACTION", "target": "t",
                  "sandbox_result": {}, "before_state": {}, "after_state": {}},
        )
        body = resp.json()
        assert set(body) == {"id", "status", "message"}
        assert body["status"] == "proposed"


# ===========================================================================
# 2) APPROVE — 10 pin tests
# ===========================================================================


class TestApprovePinned:
    """Pins mutations in `approve_decision` (lines 263-346)."""

    def test_approve_returns_404_when_decision_missing_q68_2b(self):
        """Mutmut category 1 (magic-number): `status.HTTP_404_NOT_FOUND` flipped
        to 400/500. Pin: exact 404 for missing decision."""
        session = _DecisionsSession(decision=None)
        resp = _client(session).post(
            f"/v1/decisions/{uuid4()}/approve", headers=_hdr(user=APPROVER),
            json={"comment": "ok"},
        )
        assert resp.status_code == 404

    def test_approve_returns_404_when_tenant_mismatch_q68_2b(self):
        """Mutmut category 2 (comparator flip): `decision.tenant_id != tenant_id`
        flipped to `==`. Pin: cross-tenant access yields 404, never 200."""
        cross_tenant_decision = _make_decision(tenant=OTHER_TENANT)
        session = _DecisionsSession(decision=cross_tenant_decision)
        resp = _client(session).post(
            f"/v1/decisions/{cross_tenant_decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        assert resp.status_code == 404

    def test_approve_rejects_already_approved_decision_q68_2b(self):
        """Mutmut category 2 (comparator flip):
        `decision.status != DecisionStatus.PROPOSED.value` flipped to `==`.
        Pin: APPROVED decision cannot be re-approved → 400."""
        decision = _make_decision(status_value=DecisionStatus.APPROVED.value)
        session = _DecisionsSession(decision=decision)
        resp = _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        assert resp.status_code == 400
        assert "Current status" in resp.text

    def test_approve_rejects_executed_decision_q68_2b(self):
        """Mutmut category 2 (comparator flip) on status gate. Pin: EXECUTED →
        400 (not 200) — already past the approval phase."""
        decision = _make_decision(status_value=DecisionStatus.EXECUTED.value)
        session = _DecisionsSession(decision=decision)
        resp = _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        assert resp.status_code == 400

    def test_approve_enforces_SoD_proposer_eq_approver_q68_2b(self):
        """Mutmut category 4 (branch dispatch): the `check_sod()` call mutated
        to `None` or to `(True, None)`. Pin: same user proposing + approving →
        403. This is the core SoD invariant."""
        decision = _make_decision(proposer=PROPOSER)
        session = _DecisionsSession(decision=decision)
        # Proposer (=PROPOSER) tries to approve own decision
        resp = _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=PROPOSER), json={"comment": "ok"},
        )
        assert resp.status_code == 403
        assert "Segregation of Duties" in resp.text or "approve own" in resp.text

    def test_approve_creates_approval_when_no_existing_row_q68_2b(self):
        """Mutmut category 4 (branch dispatch): the `else: session.add(approval)`
        branch dropped. Pin: when no existing row, ONE new DecisionApproval added."""
        decision = _make_decision()
        session = _DecisionsSession(decision=decision, existing_approval=None)
        _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        approvals = [o for o in session.added if isinstance(o, DecisionApproval)]
        assert len(approvals) == 1
        assert approvals[0].approver_id == APPROVER

    def test_approve_uses_find_or_create_not_duplicate_q68_2b(self):
        """Mutmut category 4 (branch dispatch): `if existing is not None:` flipped
        to `is None`. Pin (Q.61.09): when row exists, no second row added."""
        decision = _make_decision()
        existing = SimpleNamespace(
            id=uuid4(), decision_id=decision.id, approver_id=APPROVER,
            status=ApprovalStatus.PENDING.value, comment=None, approved_at=None,
        )
        session = _DecisionsSession(decision=decision, existing_approval=existing)
        _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "yep"},
        )
        new_approvals = [o for o in session.added if isinstance(o, DecisionApproval)]
        assert new_approvals == []
        # The existing row was mutated in place.
        assert existing.status == ApprovalStatus.APPROVED.value
        assert existing.comment == "yep"

    def test_approve_sets_decision_status_to_APPROVED_string_q68_2b(self):
        """Mutmut category 5 (string rename) on `DecisionStatus.APPROVED.value`.
        Pin: literal "APPROVED" (not enum, not "approved")."""
        decision = _make_decision()
        session = _DecisionsSession(decision=decision)
        _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        assert decision.status == "APPROVED"

    def test_approve_commits_session_q68_2b(self):
        """Mutmut category 3 (default removal): `await session.commit()` dropped.
        Pin: commit called exactly 1 time on the success path."""
        decision = _make_decision()
        session = _DecisionsSession(decision=decision)
        _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        assert session.commits == 1

    def test_approve_response_status_is_approved_lowercase_q68_2b(self):
        """Mutmut category 5 (string rename) on response. Pin: lowercase
        "approved" (public contract — frontend reads this)."""
        decision = _make_decision()
        session = _DecisionsSession(decision=decision)
        resp = _client(session).post(
            f"/v1/decisions/{decision.id}/approve",
            headers=_hdr(user=APPROVER), json={"comment": "ok"},
        )
        body = resp.json()
        assert body["status"] == "approved"
        assert body["id"] == str(decision.id)


# ===========================================================================
# 3) EXECUTE — 5 pin tests
# ===========================================================================


class TestExecutePinned:
    """Pins mutations in `execute_decision` (lines 349-422)."""

    def test_execute_rejects_non_approved_q68_2b(self):
        """Mutmut category 2 (comparator flip):
        `decision.status != DecisionStatus.APPROVED.value` flipped to `==`.
        Pin: PROPOSED decision cannot be executed → 400."""
        decision = _make_decision(status_value=DecisionStatus.PROPOSED.value)
        session = _DecisionsSession(decision=decision)
        resp = _client(session).post(
            f"/v1/decisions/{decision.id}/execute", headers=_hdr(user=APPROVER),
        )
        assert resp.status_code == 400

    def test_execute_returns_404_for_missing_q68_2b(self):
        """Mutmut category 1 on 404 status code."""
        session = _DecisionsSession(decision=None)
        resp = _client(session).post(
            f"/v1/decisions/{uuid4()}/execute", headers=_hdr(user=APPROVER),
        )
        assert resp.status_code == 404

    def test_execute_sets_status_to_EXECUTED_and_timestamp_q68_2b(self):
        """Mutmut category 5 (string rename) on `DecisionStatus.EXECUTED.value`
        AND category 4 (None substitution) on `decision.executed_at = datetime.utcnow()`.
        Pin: literal "EXECUTED" AND non-null executed_at timestamp."""
        decision = _make_decision(status_value=DecisionStatus.APPROVED.value)
        session = _DecisionsSession(decision=decision)
        before = datetime.utcnow()
        # Patch kafka so the publish branch doesn't trip on missing infra.
        with patch("src.shared.kafka_client.publish_event", return_value=None):
            _client(session).post(
                f"/v1/decisions/{decision.id}/execute", headers=_hdr(user=APPROVER),
            )
        assert decision.status == "EXECUTED"
        assert decision.executed_at is not None
        assert decision.executed_at >= before

    def test_execute_returns_advisory_mode_true_q68_2b(self):
        """Mutmut category 4 (branch dispatch): `advisory_mode=True` flipped to
        `False`/`None`. Pin: Sprint Q.9 contract — execute is advisory until
        Sprint G ERP integration. Frontend reads this flag."""
        decision = _make_decision(status_value=DecisionStatus.APPROVED.value)
        session = _DecisionsSession(decision=decision)
        with patch("src.shared.kafka_client.publish_event", return_value=None):
            resp = _client(session).post(
                f"/v1/decisions/{decision.id}/execute", headers=_hdr(user=APPROVER),
            )
        body = resp.json()
        assert body["advisory_mode"] is True
        assert body["status"] == "executed"

    def test_execute_swallows_kafka_failure_q68_2b(self):
        """Mutmut category 4 (branch dispatch): `try/except Exception:` mutated to
        re-raise. Pin: kafka failure does NOT prevent the 200 — audit trail is
        already committed before the publish (see comments in execute_decision)."""
        decision = _make_decision(status_value=DecisionStatus.APPROVED.value)
        session = _DecisionsSession(decision=decision)
        with patch(
            "src.shared.kafka_client.publish_event",
            side_effect=RuntimeError("kafka down"),
        ):
            resp = _client(session).post(
                f"/v1/decisions/{decision.id}/execute", headers=_hdr(user=APPROVER),
            )
        assert resp.status_code == 200
        assert decision.status == "EXECUTED"


# ===========================================================================
# 4) ROLLBACK — 5 pin tests
# ===========================================================================


class TestRollbackPinned:
    """Pins mutations in `rollback_decision` (lines 425-510)."""

    def test_rollback_rejects_non_executed_q68_2b(self):
        """Mutmut category 2 (comparator flip):
        `decision.status != DecisionStatus.EXECUTED.value` flipped. Pin: PROPOSED
        decision cannot be rolled back → 400."""
        decision = _make_decision(status_value=DecisionStatus.PROPOSED.value)
        session = _DecisionsSession(decision=decision)
        resp = _client(session).post(
            f"/v1/decisions/{decision.id}/rollback", headers=_hdr(user=APPROVER),
        )
        assert resp.status_code == 400

    def test_rollback_inside_24h_window_succeeds_q68_2b(self):
        """Mutmut category 1 (magic-number tweak): `timedelta(hours=24)` mutated
        to 23/25/0. Pin: 23h after execution is INSIDE the 24h window → 200."""
        decision = _make_decision(
            status_value=DecisionStatus.EXECUTED.value,
            executed_at=datetime.utcnow() - timedelta(hours=23),
        )
        session = _DecisionsSession(decision=decision)
        with patch("src.shared.kafka_client.publish_event", return_value=None):
            resp = _client(session).post(
                f"/v1/decisions/{decision.id}/rollback",
                headers=_hdr(user=APPROVER),
            )
        assert resp.status_code == 200

    def test_rollback_after_24h_window_rejected_q68_2b(self):
        """Mutmut category 2 (comparator flip):
        `datetime.utcnow() > rollback_deadline` flipped to `<` or `>=`. Pin:
        25h after execution is OUTSIDE the 24h window → 400. Boundary case."""
        decision = _make_decision(
            status_value=DecisionStatus.EXECUTED.value,
            executed_at=datetime.utcnow() - timedelta(hours=25),
        )
        session = _DecisionsSession(decision=decision)
        with patch("src.shared.kafka_client.publish_event", return_value=None):
            resp = _client(session).post(
                f"/v1/decisions/{decision.id}/rollback",
                headers=_hdr(user=APPROVER),
            )
        assert resp.status_code == 400
        assert "Rollback window expired" in resp.text

    def test_rollback_sets_status_ROLLED_BACK_and_timestamp_q68_2b(self):
        """Mutmut category 5 (string rename) on `DecisionStatus.ROLLED_BACK.value`
        AND category 4 (None substitution) on rolled_back_at. Pin: literal
        "ROLLED_BACK" AND non-null timestamp."""
        decision = _make_decision(
            status_value=DecisionStatus.EXECUTED.value,
            executed_at=datetime.utcnow() - timedelta(hours=1),
        )
        session = _DecisionsSession(decision=decision)
        with patch("src.shared.kafka_client.publish_event", return_value=None):
            _client(session).post(
                f"/v1/decisions/{decision.id}/rollback",
                headers=_hdr(user=APPROVER),
            )
        assert decision.status == "ROLLED_BACK"
        assert decision.rolled_back_at is not None

    def test_rollback_returns_before_state_snapshot_q68_2b(self):
        """Mutmut category 4 (branch dispatch): `before_state_snapshot = ...`
        mutated to `None`. Pin: Sprint Q.9 advisory contract — frontend reads
        before_state to show 'what would have been reverted'."""
        decision = _make_decision(
            status_value=DecisionStatus.EXECUTED.value,
            executed_at=datetime.utcnow() - timedelta(hours=1),
        )
        decision.before_state = {"qty": 42, "sku": "K-mar1"}
        session = _DecisionsSession(decision=decision)
        with patch("src.shared.kafka_client.publish_event", return_value=None):
            resp = _client(session).post(
                f"/v1/decisions/{decision.id}/rollback",
                headers=_hdr(user=APPROVER),
            )
        body = resp.json()
        assert body["before_state"] == {"qty": 42, "sku": "K-mar1"}
        assert body["advisory_mode"] is True
