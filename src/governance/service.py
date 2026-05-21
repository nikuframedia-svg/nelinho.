"""
Governance Service — Decision Lifecycle Façade
================================================

Q.66.D.3 — this file used to be a 1669L god-class. Implementation now
lives in five sub-modules organised by lifecycle stage:

* :mod:`decision_proposer`   — propose + hash-chain seed.
* :mod:`decision_approver`   — approve / reject / bulk / auto-approval gate.
* :mod:`decision_executor`   — execute + ActionExecutor dispatch.
* :mod:`decision_rollbacker` — rollback + kill-switch arm/state.
* :mod:`decision_query`      — read-side: get/list/timeline/audit-pack +
  payload edits + hash-chain verification.

This module keeps:

* the public API surface (``GovernanceService`` class with the same
  method signatures the rest of the codebase imports),
* the cross-cutting exceptions (``SoDViolationError``,
  ``ApprovalRequiredError``, ``KillSwitchActiveError``) so callers
  importing from ``src.governance.service`` keep working,
* a re-export of ``_coerce_actor_uuid`` for the same reason.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .decision_approver import (
    DecisionApprover,
    RISK_ORDER,
    _risk_at_or_below,
)
from .decision_executor import DecisionExecutor
from .decision_proposer import DecisionProposer, _coerce_actor_uuid
from .decision_query import (
    DecisionQuery,
    _aware,
    _group_sort_key,
    _impact_magnitude,
    _isoformat,
)
from .decision_rollbacker import DecisionRollbacker
from .models import DEFAULT_POLICIES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cross-cutting exceptions (kept here so existing imports survive).
# ---------------------------------------------------------------------------


class SoDViolationError(Exception):
    """Separation of Duties violation."""
    pass


class ApprovalRequiredError(Exception):
    """Approval is required before execution."""
    pass


class KillSwitchActiveError(Exception):
    """Sprint Q.12 Onda 2.2 — raised when a propose/execute attempt
    targets a tenant scope with an active kill switch. Carries the
    ``scope`` and ``decision_id`` so the API layer can map to 423
    LOCKED with a useful message."""

    def __init__(self, scope: str, decision_id: UUID, reason: str) -> None:
        self.scope = scope
        self.decision_id = decision_id
        self.reason = reason
        super().__init__(
            f"Kill switch active for scope={scope!r} (decision_id={decision_id}): {reason}"
        )


# ---------------------------------------------------------------------------
# Façade
# ---------------------------------------------------------------------------


class GovernanceService:
    """Façade over the five lifecycle sub-services.

    Implements C5 contract requirements:
      * Immutable decision ledger.
      * Approval workflow with SoD.
      * Hash chain for audit.
      * Kill switch.

    Each sub-service is instantiated with a shared ``db`` + ``tenant_id``
    so they all see the same SQLAlchemy session and tenant scope. The
    façade wires cross-cutting collaborators (auto-approval gate,
    kill-switch query) onto the proposer so the chain-of-responsibility
    behaviour is preserved without circular imports.
    """

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        """
        Args:
            db: AsyncSession for database operations.
            tenant_id: Tenant ID for multi-tenancy.
        """
        self.db = db
        self.tenant_id = tenant_id
        self._policies: Dict[str, Dict] = {
            p["decision_type"]: p for p in DEFAULT_POLICIES
        }

        # Sub-services (lazy-init: cheap to construct, share session).
        self._proposer = DecisionProposer(db, tenant_id, self._policies)
        self._approver = DecisionApprover(db, tenant_id, self._policies)
        self._executor = DecisionExecutor(db, tenant_id, self._policies)
        self._rollbacker = DecisionRollbacker(db, tenant_id)
        self._query = DecisionQuery(db, tenant_id)

        # Wire cross-cutting collaborators.
        # Proposer needs the auto-approval gate (lives on approver) and
        # the kill-switch query (lives on rollbacker) — bind through
        # the façade so monkey-patches on the façade keep working.
        self._proposer._auto_approval_allowed = self._auto_approval_allowed
        self._proposer._is_kill_switch_active = self.is_kill_switch_active
        # Approver re-enters the façade for bulk_act so test patches
        # on `svc.approve_decision` take effect.
        self._approver._approve_decision_via_facade = self.approve_decision
        # Executor reads facade.action_executor (DI hook).
        self._executor._facade_ref = self
        # Rollbacker re-enters the façade for propose + get_decision
        # so the kill-switch path uses whichever patched version the
        # test installed.
        self._rollbacker._propose_decision_via_facade = self.propose_decision
        self._rollbacker._get_decision_via_facade = self.get_decision
        # Tests monkey-patch `svc._get_decision_run` AFTER construction
        # — store a reference to the façade itself so each call walks
        # through whatever attribute is bound right now.
        self._rollbacker._facade_ref = self

    # ======================================================================
    # Policy Management
    # ======================================================================

    def get_policy(self, decision_type: str) -> Optional[Dict[str, Any]]:
        """Get policy for a decision type."""
        return self._policies.get(decision_type)

    def list_policies(self) -> List[Dict[str, Any]]:
        """List all policies."""
        return list(self._policies.values())

    # ======================================================================
    # Propose (delegates to DecisionProposer)
    # ======================================================================

    async def propose_decision(
        self,
        decision_type: str,
        title: str,
        action_data: Dict[str, Any],
        proposed_by: str,
        description: Optional[str] = None,
        expected_impact: Optional[Dict[str, Any]] = None,
        risk_level: str = "medium",
        scenario_id: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._proposer.propose_decision(
            decision_type=decision_type,
            title=title,
            action_data=action_data,
            proposed_by=proposed_by,
            description=description,
            expected_impact=expected_impact,
            risk_level=risk_level,
            scenario_id=scenario_id,
            evidence_refs=evidence_refs,
        )

    async def propose_decision_with_deferred_kafka(
        self, **kwargs,
    ) -> tuple[Dict[str, Any], Optional[Any]]:
        return await self._proposer.propose_decision_with_deferred_kafka(**kwargs)

    # ======================================================================
    # Approve / reject / bulk / auto-approval (delegates to DecisionApprover)
    # ======================================================================

    async def approve_decision(self, **kwargs) -> Dict[str, Any]:
        return await self._approver.approve_decision(**kwargs)

    async def get_pending_approvals(self, user: str) -> List[Dict[str, Any]]:
        return await self._approver.get_pending_approvals(user)

    async def bulk_act(
        self, *, items: List[Dict[str, Any]], approved_by: str,
    ) -> List[Dict[str, Any]]:
        return await self._approver.bulk_act(items=items, approved_by=approved_by)

    async def _auto_approval_allowed(
        self,
        *,
        decision_type: str,
        risk_level: str,
        trust_index: Optional[float] = None,
    ) -> bool:
        return await self._approver._auto_approval_allowed(
            decision_type=decision_type,
            risk_level=risk_level,
            trust_index=trust_index,
        )

    # ======================================================================
    # Execute (delegates to DecisionExecutor)
    # ======================================================================

    async def execute_decision(
        self, decision_id: str, executed_by: str,
    ) -> Dict[str, Any]:
        return await self._executor.execute_decision(decision_id, executed_by)

    # ======================================================================
    # Rollback + kill switch (delegates to DecisionRollbacker)
    # ======================================================================

    async def rollback_decision(
        self, decision_id: str, rolled_back_by: str, reason: str,
    ) -> Dict[str, Any]:
        return await self._rollbacker.rollback_decision(
            decision_id, rolled_back_by, reason,
        )

    async def activate_kill_switch(
        self, scope: str, activated_by: str, reason: str,
    ) -> Dict[str, Any]:
        return await self._rollbacker.activate_kill_switch(
            scope, activated_by, reason,
        )

    async def is_kill_switch_active(
        self, *, decision_type: Optional[str] = None,
    ):
        return await self._rollbacker.is_kill_switch_active(
            decision_type=decision_type,
        )

    # ======================================================================
    # Read-side + payload edits (delegates to DecisionQuery)
    # ======================================================================

    async def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        # Use _get_decision_run on `self` (not on _query) so test
        # monkey-patches of `svc._get_decision_run` are honoured.
        run = await self._get_decision_run(decision_id)
        return DecisionQuery._run_to_dict(run) if run else None

    async def list_decisions(
        self,
        status: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return await self._query.list_decisions(
            status=status, decision_type=decision_type,
            limit=limit, offset=offset,
        )

    async def get_timeline(self, **kwargs) -> Dict[str, Any]:
        return await self._query.get_timeline(**kwargs)

    async def get_audit_timeline(self, **kwargs) -> List[Dict[str, Any]]:
        return await self._query.get_audit_timeline(**kwargs)

    async def modify_payload(self, **kwargs) -> Dict[str, Any]:
        return await self._query.modify_payload(**kwargs)

    async def get_audit_pack(self, decision_id: str) -> Dict[str, Any]:
        return await self._query.get_audit_pack(decision_id)

    # ======================================================================
    # Shared internals — exposed at the façade because tests monkey-patch
    # them and other modules import them directly.
    # ======================================================================

    async def _get_decision_run(self, decision_id: str):
        """Tenant-scoped DecisionRun lookup. Shared with sub-services."""
        return await self._query._get_decision_run(decision_id)

    @staticmethod
    def _run_to_dict(run) -> Dict[str, Any]:
        """DecisionRun -> dict — re-exported so callers that did
        ``GovernanceService._run_to_dict(run)`` directly still work.
        """
        return DecisionQuery._run_to_dict(run)

    async def _get_last_decision_hash(self) -> Optional[str]:
        """Chain head read — delegates to the proposer's helper."""
        return await self._proposer._get_last_decision_hash()
