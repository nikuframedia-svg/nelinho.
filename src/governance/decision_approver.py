"""Q.66.D.3 — approver sub-service.

Lifecycle stage **approve**. Extracted from ``service.py`` during
Q.66.D.3 Fase 7. Owns:

* ``approve_decision`` (handles APPROVE / REJECT / REQUEST_CHANGES)
* ``get_pending_approvals``
* ``bulk_act``
* ``_auto_approval_allowed`` (trust-gate + TenantConfig)

SoD enforcement (``proposer != approver``) lives here. Re-uses the
``DecisionQuery._run_to_dict`` / ``_get_decision_run`` helpers via the
shared façade.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change

from .decision_proposer import _coerce_actor_uuid
from .models import (
    Approval,
    ApprovalAction,
    DecisionRun,
    DecisionStatus,
)

logger = logging.getLogger(__name__)


# Risk severity ordering (used by auto-approval + timeline grouping).
RISK_ORDER: Dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _risk_at_or_below(actual: str, ceiling: str) -> bool:
    a = RISK_ORDER.get((actual or "medium").lower(), 1)
    c = RISK_ORDER.get((ceiling or "low").lower(), 0)
    return a <= c


class DecisionApprover:
    """Approve lifecycle stage — vote handling, SoD enforcement, status
    flips, bulk approve/reject, auto-approval gate.
    """

    # Trust gate threshold (Blueprint v2.0 §4.5). Decisions with a
    # trust index below this never auto-approve; missing trust = treat
    # as below threshold so silence isn't consent.
    _TRUST_GATE_THRESHOLD: float = 0.75

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        policies: Dict[str, Dict[str, Any]],
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self._policies = policies
        # Late-bound by the façade: lets bulk_act re-enter through the
        # public surface (so monkey-patches in tests still apply).
        self._approve_decision_via_facade = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def approve_decision(
        self,
        decision_id: str,
        action: ApprovalAction,
        approved_by: str,
        reason: str,
        approver_role: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        rejection_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve or reject a decision with SoD enforcement.

        Sprint Q.2 — `rejection_category` is required when
        `action == REJECT`. The API layer raises 400 before reaching
        here if it's missing, but we keep the parameter optional at the
        service level so internal callers (auto-rejection by gates) can
        supply their own categorical signal.
        """
        from .service import SoDViolationError
        from .decision_query import DecisionQuery

        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status != DecisionStatus.PENDING_APPROVAL.value:
            raise ValueError(
                f"Decision {decision_id} is not pending approval "
                f"(status: {decision_run.status})"
            )

        # SoD check — get policy to check requires_different_approver.
        policy = self._policies.get(decision_run.decision_type)
        requires_different = (
            policy.get("requires_different_approver", True) if policy else True
        )
        if requires_different and approved_by == decision_run.proposed_by:
            raise SoDViolationError(
                f"Separation of Duties violation: {approved_by} cannot approve "
                f"their own decision."
            )

        # Check duplicate vote.
        existing = [a for a in decision_run.approvals if a.approved_by == approved_by]
        if existing:
            raise ValueError(f"User {approved_by} has already voted on this decision")

        # Create approval record.
        approval_id = uuid4()
        approval = Approval(
            id=approval_id,
            tenant_id=self.tenant_id,
            decision_run_id=decision_run.id,
            action=action.value,
            approved_by=approved_by,
            reason=reason,
            approver_role=approver_role,
            conditions=conditions,
            rejection_category=(
                rejection_category if action == ApprovalAction.REJECT else None
            ),
        )
        self.db.add(approval)
        await audit_change(
            self.db,
            tenant_id=self.tenant_id,
            entity_type="approval",
            entity_id=approval_id,
            action="INSERT",
            new_values={
                "decision_run_id": str(decision_run.id),
                "action": action.value,
                "approver_role": approver_role,
                "rejection_category": (
                    rejection_category if action == ApprovalAction.REJECT else None
                ),
            },
            actor_id=_coerce_actor_uuid(approved_by),
            actor_role=approver_role,
            reason=f"aprovação: {action.value}",
        )

        # Update status.
        if action == ApprovalAction.REJECT:
            decision_run.status = DecisionStatus.REJECTED.value
        elif action == ApprovalAction.REQUEST_CHANGES:
            decision_run.status = DecisionStatus.PROPOSED.value
        elif action == ApprovalAction.APPROVE:
            required = policy.get("required_approvers", 1) if policy else 1
            approve_count = len(
                [a for a in decision_run.approvals
                 if a.action == ApprovalAction.APPROVE.value]
            ) + 1
            if approve_count >= required:
                decision_run.status = DecisionStatus.APPROVED.value
                decision_run.approved_at = datetime.now(timezone.utc)

        await self.db.flush()
        logger.info(f"Decision {decision_id} — {action.value} by {approved_by}")

        # Publish a lifecycle event on every approval action so the
        # Timeline UI can animate votes in real time. `status` tells the
        # consumer whether the decision crossed the approval threshold,
        # was rejected, or is still pending more votes.
        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            await publish_event(
                Topics.DECISION_APPROVED,
                EventBase(
                    event_type="DECISION_APPROVED",
                    tenant_id=self.tenant_id,
                    source_module="governance",
                    payload={
                        "decision_id": str(decision_run.id),
                        "decision_type": decision_run.decision_type,
                        "status": decision_run.status,
                        "action": action.value,
                        "approved_by": approved_by,
                        "approver_role": approver_role,
                        "reason": reason,
                        "conditions": conditions,
                        "rejection_category": (
                            rejection_category
                            if action == ApprovalAction.REJECT else None
                        ),
                        "approvals_total": len(decision_run.approvals),
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "DECISION_APPROVED publish failed for %s: %s", decision_run.id, exc,
            )

        return DecisionQuery._run_to_dict(decision_run)

    async def get_pending_approvals(self, user: str) -> List[Dict[str, Any]]:
        """Get decisions pending approval that user can approve."""
        from .decision_query import DecisionQuery

        stmt = select(DecisionRun).where(
            and_(
                DecisionRun.tenant_id == self.tenant_id,
                DecisionRun.status == DecisionStatus.PENDING_APPROVAL.value,
                DecisionRun.proposed_by != user,
            )
        ).order_by(DecisionRun.proposed_at.desc())

        result = await self.db.execute(stmt)
        runs = result.scalars().all()

        # Filter out decisions where user already voted.
        pending = []
        for run in runs:
            already_voted = any(a.approved_by == user for a in run.approvals)
            if not already_voted:
                pending.append(DecisionQuery._run_to_dict(run))

        return pending

    # ------------------------------------------------------------------
    # Sprint M.2 — Bulk Approve/Reject (per-item, anti-fatigue)
    # ------------------------------------------------------------------

    async def bulk_act(
        self,
        *,
        items: List[Dict[str, Any]],
        approved_by: str,
    ) -> List[Dict[str, Any]]:
        """Apply a batch of approve/reject/request_changes actions.

        Per-item independent: one failure does NOT abort the batch (the
        caller shouldn't have to re-inspect the other N-1 items). Each
        result is `{decision_id, status, error?}` — `error` is the
        exception message on failure, absent on success.
        """
        from .service import SoDViolationError

        results: List[Dict[str, Any]] = []
        for item in items:
            decision_id = item.get("decision_id")
            action_raw = item.get("action")
            reason = item.get("reason", "")
            try:
                if not decision_id:
                    raise ValueError("decision_id is required")
                if action_raw is None:
                    raise ValueError("action is required")
                action = (
                    action_raw
                    if isinstance(action_raw, ApprovalAction)
                    else ApprovalAction(str(action_raw).lower())
                )
                # Route through the façade so external monkey-patches /
                # subclasses still take effect.
                decision = await self._approve_decision_via_facade(
                    decision_id=str(decision_id),
                    action=action,
                    approved_by=approved_by,
                    reason=reason,
                )
                results.append({
                    "decision_id": str(decision_id),
                    "status": "ok",
                    "new_status": decision["status"],
                    "action": action.value,
                })
            except (SoDViolationError, ValueError) as exc:
                results.append({
                    "decision_id": str(decision_id) if decision_id else None,
                    "status": "error",
                    "error": str(exc),
                })
        return results

    # ------------------------------------------------------------------
    # Sprint M.5 — Auto-approval rules configuráveis (TenantConfig)
    # ------------------------------------------------------------------

    async def _auto_approval_allowed(
        self,
        *,
        decision_type: str,
        risk_level: str,
        trust_index: Optional[float] = None,
    ) -> bool:
        """Check TenantConfig for `governance.auto_approval.{decision_type}.*`.

        Returns True iff ALL of:
          * `auto_approval.{decision_type}.enabled=True`
          * decision's risk level ≤ `auto_approval.{decision_type}.risk_ceiling`
          * caller-provided ``trust_index`` ≥ ``_TRUST_GATE_THRESHOLD``

        Q.66.A.3 — removed the ``scenario_id`` auto-resolution path. The
        previous ``_resolve_trust_index`` called ``CommitsService.
        get_by_scenario_id`` which never existed; the ``try/except``
        masked the ``AttributeError`` and always returned ``None``, so
        the resolution was dead code from day one. The deeper reason:
        ``SandboxScenario`` (the only caller passing scenario_id) does
        not run CPO (sandbox/service.py:128 — "Doesn't run the CPO"),
        so there is no commit to resolve to. Connecting them would be a
        product change, not a refactor. The caller must now pass
        ``trust_index`` explicitly when it has one.

        Falls back to False on any error — auto-approval is a
        power-user feature, never the default.
        """
        if trust_index is None:
            logger.info(
                "Trust gate blocked auto-approval: tenant=%s type=%s "
                "trust_index unavailable (no scenario / commit)",
                self.tenant_id, decision_type,
            )
            return False

        if trust_index < self._TRUST_GATE_THRESHOLD:
            logger.info(
                "Trust gate blocked auto-approval: tenant=%s type=%s "
                "TI=%.3f < %.2f",
                self.tenant_id, decision_type, trust_index,
                self._TRUST_GATE_THRESHOLD,
            )
            return False

        try:
            from src.core.services.tenant_config_service import TenantConfigService

            cfg = TenantConfigService(self.db, self.tenant_id)
            enabled_key = f"auto_approval.{decision_type}.enabled"
            ceiling_key = f"auto_approval.{decision_type}.risk_ceiling"
            enabled = await cfg.get("governance", enabled_key, default=False)
            if not bool(enabled):
                return False
            ceiling = await cfg.get("governance", ceiling_key, default="LOW")
            return _risk_at_or_below(risk_level, str(ceiling))
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("auto-approval check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Shared lookup helper (mirror of the query module — kept here so
    # approve_decision can route through the same code path under tests
    # that monkey-patch _get_decision_run on the façade).
    # ------------------------------------------------------------------

    async def _get_decision_run(self, decision_id: str) -> Optional[DecisionRun]:
        """Fetch a DecisionRun by ID, tenant-scoped."""
        try:
            uid = UUID(decision_id) if isinstance(decision_id, str) else decision_id
        except ValueError:
            return None
        stmt = select(DecisionRun).where(
            and_(DecisionRun.id == uid, DecisionRun.tenant_id == self.tenant_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
