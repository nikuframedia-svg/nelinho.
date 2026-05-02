"""
Governance Service — Decision Lifecycle Management
====================================================

Handles:
- Decision proposal and approval workflow
- SoD (Separation of Duties) enforcement
- Audit hash chain integrity
- Canary rollout
- Kill switch
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    DecisionRun,
    Approval,
    DecisionPolicy,
    AutonomyLevel,
    DecisionStatus,
    ApprovalAction,
    DEFAULT_POLICIES,
)


# Risk severity ordering (used by auto-approval + timeline grouping).
RISK_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _risk_at_or_below(actual: str, ceiling: str) -> bool:
    a = RISK_ORDER.get((actual or "medium").lower(), 1)
    c = RISK_ORDER.get((ceiling or "low").lower(), 0)
    return a <= c


def _aware(dt: Optional[datetime]) -> datetime:
    """Coerce naive datetimes to UTC so subtraction works across both kinds."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _isoformat(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _impact_magnitude(expected_impact: Optional[Dict[str, Any]]) -> float:
    """Reduce an `expected_impact` dict to a single float so `min_impact` can
    filter against it. Picks the first numeric value (or the `magnitude` /
    `delta` / `abs_euro` key when present); returns 0.0 when nothing is numeric."""
    if not expected_impact:
        return 0.0
    for key in ("magnitude", "delta", "abs_euro", "impact", "score"):
        if key in expected_impact and isinstance(expected_impact[key], (int, float)):
            return abs(float(expected_impact[key]))
    for value in expected_impact.values():
        if isinstance(value, (int, float)):
            return abs(float(value))
    return 0.0


def _group_sort_key(key: str, group_by: str) -> tuple:
    """Deterministic ordering of group buckets. Risk levels sort high→low so
    the worst fires float to the top."""
    if group_by == "risk_level":
        # We flip the sign so higher risk comes first.
        return (-RISK_ORDER.get(key, -1),)
    return (key,)

logger = logging.getLogger(__name__)


class SoDViolationError(Exception):
    """Separation of Duties violation."""
    pass


class ApprovalRequiredError(Exception):
    """Approval is required before execution."""
    pass


class GovernanceService:
    """
    Service for managing decision governance.
    
    Implements C5 contract requirements:
    - Immutable decision ledger
    - Approval workflow with SoD
    - Hash chain for audit
    - Kill switch
    """
    
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        """
        Initialize service.

        Args:
            db: AsyncSession for database operations
            tenant_id: Tenant ID for multi-tenancy
        """
        self.db = db
        self.tenant_id = tenant_id
        self._policies: Dict[str, Dict] = {
            p["decision_type"]: p for p in DEFAULT_POLICIES
        }
    
    # =========================================================================
    # Policy Management
    # =========================================================================
    
    def get_policy(self, decision_type: str) -> Optional[Dict[str, Any]]:
        """Get policy for a decision type."""
        return self._policies.get(decision_type)
    
    def list_policies(self) -> List[Dict[str, Any]]:
        """List all policies."""
        return list(self._policies.values())
    
    # =========================================================================
    # Decision Lifecycle
    # =========================================================================
    
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
        """
        Propose a new decision.
        
        Args:
            decision_type: Type of decision (must match a policy)
            title: Decision title
            action_data: Data for the action
            proposed_by: User proposing
            description: Optional description
            expected_impact: Expected impact on KPIs
            risk_level: Risk level (low, medium, high, critical)
            scenario_id: Optional scenario reference
            evidence_refs: Optional evidence references
            
        Returns:
            Created decision record
        """
        # Get policy
        policy = self.get_policy(decision_type)
        if not policy:
            # Use default policy
            policy = {
                "decision_type": decision_type,
                "autonomy_level": AutonomyLevel.L2.value,
                "requires_approval": True,
                "required_approvers": 1,
                "requires_different_approver": True,
            }
        
        decision_id = str(uuid4())
        
        # Calculate input hash
        input_data = {
            "decision_type": decision_type,
            "action_data": action_data,
            "expected_impact": expected_impact,
            "scenario_id": scenario_id,
        }
        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        
        # Get last decision hash for chain integrity
        last_hash = await self._get_last_decision_hash()

        decision_id_uuid = uuid4()
        policy_version = policy.get("version", "1.0.0")

        # Calculate audit hash
        audit_hash = DecisionRun.calculate_audit_hash(
            decision_id=decision_id_uuid,
            policy_version=policy_version,
            input_hash=input_hash,
            outcome_hash=None,
            prev_hash=last_hash,
        )

        # Determine initial status. Sprint M.5: if the tenant has enabled
        # auto-approval for this decision_type AND the risk level is at/below
        # the configured ceiling, the decision skips the human queue.
        initial_status = DecisionStatus.PROPOSED.value
        if policy.get("requires_approval", True):
            initial_status = DecisionStatus.PENDING_APPROVAL.value
            if await self._auto_approval_allowed(
                decision_type=decision_type,
                risk_level=risk_level,
            ):
                initial_status = DecisionStatus.APPROVED.value
                logger.info(
                    "auto-approved decision (tenant=%s type=%s risk=%s)",
                    self.tenant_id, decision_type, risk_level,
                )

        # Persist to DB
        scenario_uuid = UUID(scenario_id) if scenario_id else None
        decision_run = DecisionRun(
            id=decision_id_uuid,
            tenant_id=self.tenant_id,
            decision_type=decision_type,
            title=title,
            description=description,
            status=initial_status,
            policy_version=policy_version,
            autonomy_level=policy.get("autonomy_level", AutonomyLevel.L2.value),
            action_data=action_data,
            expected_impact=expected_impact,
            risk_level=risk_level,
            scenario_id=scenario_uuid,
            evidence_refs=evidence_refs or [],
            input_snapshot_hash=input_hash,
            prev_hash=last_hash,
            audit_hash=audit_hash,
            proposed_by=proposed_by,
        )

        self.db.add(decision_run)
        await self.db.flush()

        logger.info(f"Decision proposed: {decision_id_uuid} ({decision_type})")

        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            await publish_event(
                Topics.DECISION_PROPOSED,
                EventBase(
                    event_type="DECISION_PROPOSED",
                    tenant_id=self.tenant_id,
                    source_module="governance",
                    payload={
                        "decision_id": str(decision_run.id),
                        "decision_type": decision_type,
                        "title": title,
                        "proposed_by": proposed_by,
                        "risk_level": risk_level,
                        "status": decision_run.status,
                        "autonomy_level": decision_run.autonomy_level,
                        "action_data": action_data,
                        "expected_impact": expected_impact,
                        "scenario_id": scenario_id,
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning(
                "DECISION_PROPOSED publish failed for %s: %s", decision_run.id, exc,
            )

        return self._run_to_dict(decision_run)
    
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
        `action == REJECT`. The API layer raises 400 before reaching here
        if it's missing, but we keep the parameter optional at the service
        level so internal callers (auto-rejection by gates) can supply
        their own categorical signal.
        """
        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status != DecisionStatus.PENDING_APPROVAL.value:
            raise ValueError(
                f"Decision {decision_id} is not pending approval "
                f"(status: {decision_run.status})"
            )

        # SoD check — get policy to check requires_different_approver
        policy = self.get_policy(decision_run.decision_type)
        requires_different = policy.get("requires_different_approver", True) if policy else True
        if requires_different and approved_by == decision_run.proposed_by:
            raise SoDViolationError(
                f"Separation of Duties violation: {approved_by} cannot approve "
                f"their own decision."
            )

        # Check duplicate vote
        existing = [a for a in decision_run.approvals if a.approved_by == approved_by]
        if existing:
            raise ValueError(f"User {approved_by} has already voted on this decision")

        # Create approval record
        approval = Approval(
            id=uuid4(),
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

        # Update status
        if action == ApprovalAction.REJECT:
            decision_run.status = DecisionStatus.REJECTED.value
        elif action == ApprovalAction.REQUEST_CHANGES:
            decision_run.status = DecisionStatus.PROPOSED.value
        elif action == ApprovalAction.APPROVE:
            required = policy.get("required_approvers", 1) if policy else 1
            approve_count = len([a for a in decision_run.approvals if a.action == ApprovalAction.APPROVE.value]) + 1
            if approve_count >= required:
                decision_run.status = DecisionStatus.APPROVED.value
                decision_run.approved_at = datetime.now(timezone.utc)

        await self.db.flush()
        logger.info(f"Decision {decision_id} — {action.value} by {approved_by}")

        # Publish a lifecycle event on every approval action so the Timeline
        # UI can animate votes in real time. `status` tells the consumer
        # whether the decision crossed the approval threshold, was rejected,
        # or is still pending more votes.
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

        return self._run_to_dict(decision_run)

    async def execute_decision(
        self,
        decision_id: str,
        executed_by: str,
    ) -> Dict[str, Any]:
        """Execute an approved decision.

        Sprint A WG1: in addition to the existing status/audit updates,
        this method now publishes a `DECISION_EXECUTED` Kafka event. The
        event carries the full audit trail (decision_id, input/outcome
        hashes, action_data) so downstream consumers — the ActionExecutor
        dispatcher, the frontend Timeline and the audit log — can react
        without re-reading the DB.

        The full action dispatch (actually applying `action_data` to the
        FactoryState) is out of scope here — it belongs to the Sprint B
        CO1 work alongside `rejected_alternatives`. What WG1 guarantees
        today is that *the decision is announced* and the audit hash
        chain is refreshed; the listener fan-out is the implementation
        boundary for a proper ActionExecutor in the next sprint.
        """
        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status != DecisionStatus.APPROVED.value:
            raise ApprovalRequiredError(
                f"Decision {decision_id} must be approved before execution "
                f"(current status: {decision_run.status})"
            )

        decision_run.status = DecisionStatus.EXECUTING.value

        try:
            outcome_data = {
                "action_data": decision_run.action_data,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "executed_by": executed_by,
            }
            outcome_hash = hashlib.sha256(
                json.dumps(outcome_data, sort_keys=True, default=str).encode()
            ).hexdigest()

            decision_run.status = DecisionStatus.EXECUTED.value
            decision_run.executed_at = datetime.now(timezone.utc)
            decision_run.executed_by = executed_by
            decision_run.outcome_hash = outcome_hash
            decision_run.audit_hash = DecisionRun.calculate_audit_hash(
                decision_id=decision_run.id,
                policy_version=decision_run.policy_version,
                input_hash=decision_run.input_snapshot_hash,
                outcome_hash=outcome_hash,
                prev_hash=decision_run.prev_hash,
            )

            await self.db.flush()
            logger.info(f"Decision {decision_id} executed by {executed_by}")

            # WG1 — announce the executed decision on the event bus. We
            # best-effort this: the DB update is the source of truth, so
            # a Kafka publish failure should not unwind the execution.
            await self._publish_decision_executed(decision_run, executed_by)

            # Sprint C 4.1 — dispatch to the ActionExecutor registry. A
            # handler that's registered for this decision_type applies
            # the action to domain state; unknown types stay "announced
            # only" (advisory mode, §4.3 blueprint). Handler failures
            # bubble up → we catch below and flip the status to FAILED.
            await self._dispatch_action(decision_run, executed_by)

        except Exception as e:
            decision_run.status = DecisionStatus.FAILED.value
            await self.db.flush()
            logger.error(f"Decision {decision_id} execution failed: {e}")
            raise

        return self._run_to_dict(decision_run)

    async def _dispatch_action(
        self,
        decision_run: "DecisionRun",
        executed_by: str,
    ) -> None:
        """Route the decision's `action_data` to its registered handler.

        Uses the module-level `default_executor` unless the caller
        overrides via `self.action_executor` (dependency-injected for
        tests). A handler failure propagates — the calling
        `execute_decision` turns that into status=FAILED.
        """
        from src.governance.action_executor import (
            ActionContext,
            default_executor,
        )

        executor = getattr(self, "action_executor", None) or default_executor
        ctx = ActionContext(
            decision_id=decision_run.id,
            decision_type=decision_run.decision_type,
            tenant_id=decision_run.tenant_id,
            action_data=decision_run.action_data or {},
            executed_by=executed_by,
            session=self.db,
        )
        # dispatch is best-effort for "no_handler" (advisory mode) but
        # strict for handler failures — they propagate.
        await executor.dispatch(ctx)

    async def _publish_decision_executed(
        self,
        decision_run: "DecisionRun",
        executed_by: str,
    ) -> None:
        """Publish a DECISION_EXECUTED event. Best-effort: logs + swallows
        on Kafka failure so an outage of the message bus doesn't break
        the decision execution path itself.
        """
        try:
            from src.shared.kafka_client import Topics, publish_event
            from src.shared.kafka_client import EventBase

            event = EventBase(
                event_type="DECISION_EXECUTED",
                tenant_id=decision_run.tenant_id,
                source_module="governance",
                payload={
                    "decision_id": str(decision_run.id),
                    "decision_type": decision_run.decision_type,
                    "risk_level": decision_run.risk_level,
                    "executed_by": executed_by,
                    "action_data": decision_run.action_data,
                    "outcome_hash": decision_run.outcome_hash,
                    "audit_hash": decision_run.audit_hash,
                },
            )
            await publish_event(Topics.DECISION_EXECUTED, event)
        except Exception as exc:  # pragma: no cover — bus outage is non-fatal
            logger.warning(
                "DECISION_EXECUTED publish failed for %s: %s",
                decision_run.id, exc,
            )

    async def rollback_decision(
        self,
        decision_id: str,
        rolled_back_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Rollback an executed decision.

        Sprint C 1.4 (WG2) — in addition to the status flip + audit
        bookkeeping, this now emits a `DECISION_ROLLED_BACK` Kafka event
        carrying the parent commit chain so downstream listeners (the
        future ActionExecutor rollback handler, the Timeline UI, audit
        sinks) can act on the reversal without re-reading the DB.

        The actual state revert (applying `before_state` to the
        FactoryState / DB) lives in the ActionExecutor — Sprint C 4.1
        wires that dispatcher. Right now the contract is "announce the
        rollback; database status is source of truth".
        """
        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status != DecisionStatus.EXECUTED.value:
            raise ValueError(f"Only executed decisions can be rolled back (current: {decision_run.status})")

        if not reason or len(reason) < 10:
            raise ValueError("Rollback reason is required (min 10 characters)")

        decision_run.status = DecisionStatus.ROLLED_BACK.value
        decision_run.rolled_back_at = datetime.now(timezone.utc)
        decision_run.rolled_back_by = rolled_back_by
        decision_run.rollback_reason = reason

        await self.db.flush()
        logger.info(f"Decision {decision_id} rolled back by {rolled_back_by}: {reason}")

        # WG2 — announce on the event bus. Best-effort as with execute_decision.
        await self._publish_decision_rolled_back(decision_run, rolled_back_by, reason)

        return self._run_to_dict(decision_run)

    async def _publish_decision_rolled_back(
        self,
        decision_run: "DecisionRun",
        rolled_back_by: str,
        reason: str,
    ) -> None:
        """Publish a DECISION_ROLLED_BACK event. Best-effort — swallows
        Kafka failures so a broker outage doesn't re-break the rollback
        path the operator just used to recover.
        """
        try:
            from src.shared.kafka_client import EventBase, Topics, publish_event

            event = EventBase(
                event_type="DECISION_ROLLED_BACK",
                tenant_id=decision_run.tenant_id,
                source_module="governance",
                payload={
                    "decision_id": str(decision_run.id),
                    "decision_type": decision_run.decision_type,
                    "rolled_back_by": rolled_back_by,
                    "reason": reason,
                    "action_data": decision_run.action_data,
                    "outcome_hash": decision_run.outcome_hash,
                    "audit_hash": decision_run.audit_hash,
                },
            )
            await publish_event(Topics.DECISION_ROLLED_BACK, event)
        except Exception as exc:  # pragma: no cover — bus outage is non-fatal
            logger.warning(
                "DECISION_ROLLED_BACK publish failed for %s: %s",
                decision_run.id, exc,
            )

    # =========================================================================
    # Query Methods (DB-backed)
    # =========================================================================

    async def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a decision by ID."""
        run = await self._get_decision_run(decision_id)
        return self._run_to_dict(run) if run else None

    async def list_decisions(
        self,
        status: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List decisions with optional filters."""
        stmt = select(DecisionRun).where(DecisionRun.tenant_id == self.tenant_id)

        if status:
            stmt = stmt.where(DecisionRun.status == status)
        if decision_type:
            stmt = stmt.where(DecisionRun.decision_type == decision_type)

        stmt = stmt.order_by(DecisionRun.proposed_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        runs = result.scalars().all()
        return [self._run_to_dict(r) for r in runs]

    # =========================================================================
    # Sprint M.1 — Timeline (grouped by criticality / risk / type / status)
    # =========================================================================

    async def get_timeline(
        self,
        *,
        group_by: str = "criticality",
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        actor_id: Optional[str] = None,
        autonomy_level: Optional[str] = None,
        min_impact: Optional[float] = None,
        hide_low_risk: bool = False,
        max_per_user_shown: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Return pending decisions bucketed by the requested dimension.

        `group_by` ∈ {"criticality", "risk_level", "decision_type", "status"}.
        "criticality" is an alias for risk_level (kept for Blueprint wording).

        Anti-fatigue knobs (`min_impact`, `hide_low_risk`, `max_per_user_shown`)
        thin the returned list without mutating the backing data — the aggregated
        KPIs `pending_count`/`overdue_count`/`avg_waiting_h` are computed over
        the unfiltered population so the admin can see what's *hidden*.
        """
        group_by = "risk_level" if group_by == "criticality" else group_by
        if group_by not in {"risk_level", "decision_type", "status"}:
            raise ValueError(
                f"Unsupported group_by '{group_by}'. "
                "Allowed: criticality|risk_level|decision_type|status"
            )

        # Select ALL decisions in the window that are still waiting for a human
        # (PROPOSED + PENDING_APPROVAL). APPROVED-but-not-yet-EXECUTED decisions
        # aren't user-blocking so we exclude them from the Timeline.
        conditions = [
            DecisionRun.tenant_id == self.tenant_id,
            DecisionRun.status.in_(
                [
                    DecisionStatus.PROPOSED.value,
                    DecisionStatus.PENDING_APPROVAL.value,
                ]
            ),
        ]
        if since:
            conditions.append(DecisionRun.proposed_at >= since)
        if until:
            conditions.append(DecisionRun.proposed_at <= until)
        if actor_id:
            conditions.append(DecisionRun.proposed_by == actor_id)
        if autonomy_level:
            conditions.append(DecisionRun.autonomy_level == autonomy_level)

        stmt = (
            select(DecisionRun)
            .where(and_(*conditions))
            .order_by(DecisionRun.proposed_at.desc())
        )
        all_rows = list((await self.db.execute(stmt)).scalars().all())

        # Aggregated KPIs — computed BEFORE filters so the UI can show what's
        # being hidden.
        now = datetime.now(timezone.utc)
        overdue_threshold_h = 24.0  # configurable later (Sprint L category governance)
        waiting_hours: List[float] = []
        overdue = 0
        for r in all_rows:
            waited_h = (now - _aware(r.proposed_at)).total_seconds() / 3600.0
            waiting_hours.append(max(0.0, waited_h))
            if waited_h >= overdue_threshold_h:
                overdue += 1
        avg_waiting_h = (
            sum(waiting_hours) / len(waiting_hours) if waiting_hours else 0.0
        )

        # Anti-fatigue filters
        filtered = all_rows
        if hide_low_risk:
            filtered = [r for r in filtered if (r.risk_level or "").lower() != "low"]
        if min_impact is not None:
            filtered = [
                r for r in filtered
                if _impact_magnitude(r.expected_impact) >= float(min_impact)
            ]

        # Bucketisation
        buckets: Dict[str, List[DecisionRun]] = {}
        for r in filtered:
            key = self._bucket_key(r, group_by)
            buckets.setdefault(key, []).append(r)

        # Per-user cap inside each bucket: keep N most recent per proposer.
        if max_per_user_shown is not None:
            capped: Dict[str, List[DecisionRun]] = {}
            for k, rows in buckets.items():
                seen_per_user: Dict[str, int] = {}
                out: List[DecisionRun] = []
                for r in rows:
                    count = seen_per_user.get(r.proposed_by, 0)
                    if count < max_per_user_shown:
                        seen_per_user[r.proposed_by] = count + 1
                        out.append(r)
                capped[k] = out
            buckets = capped

        # Pagination: we flatten buckets in group-key order for cursoring.
        # Most UIs read one group at a time so this is a secondary concern.
        offset = max(0, (page - 1) * page_size)
        flat: List[DecisionRun] = []
        for rows in buckets.values():
            flat.extend(rows)
        page_rows = flat[offset: offset + page_size]

        # Re-group the paged rows so the response shape is stable.
        groups_out: Dict[str, List[DecisionRun]] = {}
        for r in page_rows:
            k = self._bucket_key(r, group_by)
            groups_out.setdefault(k, []).append(r)

        return {
            "group_by": group_by,
            "groups": [
                {
                    "key": k,
                    "count": len(rows),
                    "decisions": [self._run_to_dict(r) for r in rows],
                }
                for k, rows in sorted(
                    groups_out.items(),
                    key=lambda kv: _group_sort_key(kv[0], group_by),
                )
            ],
            "total": len(all_rows),
            "shown": len(flat),
            "aggregated_kpis": {
                "pending_count": len(all_rows),
                "overdue_count": overdue,
                "avg_waiting_h": round(avg_waiting_h, 2),
            },
        }

    @staticmethod
    def _bucket_key(run: DecisionRun, group_by: str) -> str:
        if group_by == "risk_level":
            return (run.risk_level or "medium").lower()
        if group_by == "decision_type":
            return run.decision_type
        if group_by == "status":
            return run.status
        return "unknown"

    # =========================================================================
    # Sprint M.2 — Bulk Approve/Reject (per-item, anti-fatigue)
    # =========================================================================

    async def bulk_act(
        self,
        *,
        items: List[Dict[str, Any]],
        approved_by: str,
    ) -> List[Dict[str, Any]]:
        """Apply a batch of approve/reject/request_changes actions.

        Per-item independent: one failure does NOT abort the batch (the caller
        shouldn't have to re-inspect the other N-1 items). Each result is
        `{decision_id, status, error?}` — `error` is the exception message on
        failure, absent on success.
        """
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
                decision = await self.approve_decision(
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

    # =========================================================================
    # Sprint M.4 — Modify payload before approval
    # =========================================================================

    async def modify_payload(
        self,
        *,
        decision_id: str,
        patch: Dict[str, Any],
        modified_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Replace whitelisted fields of `action_data` before approval.

        Only decisions in PROPOSED/PENDING_APPROVAL can be modified. Previous
        payload is preserved under `action_data.__modifications__` with
        `{modified_by, modified_at, reason, before_hash, after_hash}` so the
        audit trail survives.

        The full set of allowed fields per `decision_type` is currently
        unrestricted — a Sprint R hook will tighten it per type (e.g. schedule
        decisions let edd_gap/buffer_pct through but never `operations`).
        """
        if len(reason or "") < 10:
            raise ValueError("Modification reason required (min 10 characters)")

        decision_run = await self._get_decision_run(decision_id)
        if not decision_run:
            raise ValueError(f"Decision {decision_id} not found")

        if decision_run.status not in (
            DecisionStatus.PROPOSED.value,
            DecisionStatus.PENDING_APPROVAL.value,
        ):
            raise ValueError(
                f"Decision {decision_id} is not editable (status: {decision_run.status})"
            )

        before = dict(decision_run.action_data or {})
        before_hash = hashlib.sha256(
            json.dumps(before, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Shallow merge; callers pass the fields they want to override.
        new_data = dict(before)
        new_data.update(patch or {})
        after_hash = hashlib.sha256(
            json.dumps(
                {k: v for k, v in new_data.items() if k != "__modifications__"},
                sort_keys=True, default=str,
            ).encode()
        ).hexdigest()

        history = list(new_data.get("__modifications__") or [])
        history.append({
            "modified_by": modified_by,
            "modified_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "before_hash": before_hash,
            "after_hash": after_hash,
        })
        new_data["__modifications__"] = history

        decision_run.action_data = new_data
        decision_run.input_snapshot_hash = after_hash
        # Re-hash the audit chain so tamper detection stays consistent.
        decision_run.audit_hash = DecisionRun.calculate_audit_hash(
            decision_id=decision_run.id,
            policy_version=decision_run.policy_version,
            input_hash=after_hash,
            outcome_hash=decision_run.outcome_hash,
            prev_hash=decision_run.prev_hash,
        )
        await self.db.flush()
        return self._run_to_dict(decision_run)

    # =========================================================================
    # Sprint M.6 — Cross-decision audit timeline
    # =========================================================================

    async def get_audit_timeline(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        actor: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Chronological event stream across all decisions.

        Events: `proposed`, `approval_<action>`, `executed`, `rolled_back`.
        Unlike `get_audit_pack(decision_id)` which returns a single-decision
        timeline, this is the cross-cutting view a reviewer uses to ask
        "what happened to us in the last hour?".
        """
        stmt = select(DecisionRun).where(DecisionRun.tenant_id == self.tenant_id)
        if since:
            stmt = stmt.where(DecisionRun.proposed_at >= since)
        if until:
            stmt = stmt.where(DecisionRun.proposed_at <= until)
        stmt = stmt.order_by(DecisionRun.proposed_at.desc()).limit(max(10, limit))
        rows = list((await self.db.execute(stmt)).scalars().all())

        events: List[Dict[str, Any]] = []
        for r in rows:
            if (not actor) or r.proposed_by == actor:
                events.append({
                    "event": "proposed",
                    "at": _isoformat(r.proposed_at),
                    "by": r.proposed_by,
                    "decision_id": str(r.id),
                    "decision_type": r.decision_type,
                    "risk_level": r.risk_level,
                })
            for a in (r.approvals or []):
                if (not actor) or a.approved_by == actor:
                    events.append({
                        "event": f"approval_{a.action}",
                        "at": _isoformat(a.approved_at),
                        "by": a.approved_by,
                        "decision_id": str(r.id),
                        "reason": a.reason,
                    })
            if r.executed_at and ((not actor) or r.executed_by == actor):
                events.append({
                    "event": "executed",
                    "at": _isoformat(r.executed_at),
                    "by": r.executed_by,
                    "decision_id": str(r.id),
                })
            if r.rolled_back_at and ((not actor) or r.rolled_back_by == actor):
                events.append({
                    "event": "rolled_back",
                    "at": _isoformat(r.rolled_back_at),
                    "by": r.rolled_back_by,
                    "decision_id": str(r.id),
                    "reason": r.rollback_reason,
                })

        # Sort globally newest-first.
        events.sort(key=lambda e: e.get("at") or "", reverse=True)
        return events[:limit]

    # =========================================================================
    # Sprint M.5 — Auto-approval rules configuráveis (TenantConfig)
    # =========================================================================

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
          * `trust_index >= 0.75` when a trust_index is supplied (Blueprint
            v2.0 §4.5 gate — Sprint C 1.2). When `trust_index is None`
            (legacy callers without a schedule commit) this check is
            skipped so existing flows stay green.

        Falls back to False on any error — auto-approval is a power-user
        feature, never the default.
        """
        # Trust gate comes BEFORE the config read so we short-circuit cheap.
        if trust_index is not None and trust_index < 0.75:
            logger.info(
                "Trust gate blocked auto-approval: tenant=%s type=%s TI=%.3f < 0.75",
                self.tenant_id, decision_type, trust_index,
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

    # =========================================================================
    # Existing methods continue below
    # =========================================================================

    async def get_pending_approvals(self, user: str) -> List[Dict[str, Any]]:
        """Get decisions pending approval that user can approve."""
        stmt = select(DecisionRun).where(
            and_(
                DecisionRun.tenant_id == self.tenant_id,
                DecisionRun.status == DecisionStatus.PENDING_APPROVAL.value,
                DecisionRun.proposed_by != user,
            )
        ).order_by(DecisionRun.proposed_at.desc())

        result = await self.db.execute(stmt)
        runs = result.scalars().all()

        # Filter out decisions where user already voted
        pending = []
        for run in runs:
            already_voted = any(a.approved_by == user for a in run.approvals)
            if not already_voted:
                pending.append(self._run_to_dict(run))

        return pending

    async def get_audit_pack(self, decision_id: str) -> Dict[str, Any]:
        """Get complete audit pack for compliance."""
        run = await self._get_decision_run(decision_id)
        if not run:
            raise ValueError(f"Decision {decision_id} not found")

        d = self._run_to_dict(run)
        timeline = [{"event": "proposed", "at": str(run.proposed_at), "by": run.proposed_by}]
        for a in run.approvals:
            timeline.append({"event": f"approval_{a.action}", "at": str(a.approved_at), "by": a.approved_by, "reason": a.reason})
        if run.executed_at:
            timeline.append({"event": "executed", "at": str(run.executed_at), "by": run.executed_by})
        if run.rolled_back_at:
            timeline.append({"event": "rolled_back", "at": str(run.rolled_back_at), "by": run.rolled_back_by, "reason": run.rollback_reason})

        return {
            "decision": d,
            "verification": {
                "audit_hash": run.audit_hash,
                "input_hash": run.input_snapshot_hash,
                "outcome_hash": run.outcome_hash,
                "prev_hash": run.prev_hash,
                "hash_chain_valid": True,
            },
            "timeline": timeline,
            "evidence": run.evidence_refs or [],
        }
    
    # =========================================================================
    # Kill Switch
    # =========================================================================
    
    async def activate_kill_switch(
        self,
        scope: str,
        activated_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Activate kill switch (no approval required)."""
        decision = await self.propose_decision(
            decision_type="kill_switch",
            title=f"KILL SWITCH: {scope}",
            action_data={"scope": scope, "reason": reason},
            proposed_by=activated_by,
            risk_level="critical",
        )

        # Auto-execute (kill switch policy bypasses approval)
        run = await self._get_decision_run(decision["id"])
        if run:
            run.status = DecisionStatus.EXECUTED.value
            run.executed_at = datetime.now(timezone.utc)
            run.executed_by = activated_by
            await self.db.flush()

        logger.critical(f"KILL SWITCH ACTIVATED by {activated_by}: {scope} - {reason}")

        return await self.get_decision(decision["id"])

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    async def _get_decision_run(self, decision_id: str) -> Optional[DecisionRun]:
        """Fetch a DecisionRun by ID."""
        try:
            uid = UUID(decision_id) if isinstance(decision_id, str) else decision_id
        except ValueError:
            return None
        stmt = select(DecisionRun).where(
            and_(DecisionRun.id == uid, DecisionRun.tenant_id == self.tenant_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_last_decision_hash(self) -> Optional[str]:
        """Get the hash of the most recent decision (for chain integrity)."""
        stmt = (
            select(DecisionRun.audit_hash)
            .where(DecisionRun.tenant_id == self.tenant_id)
            .order_by(DecisionRun.proposed_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    @staticmethod
    def _run_to_dict(run: DecisionRun) -> Dict[str, Any]:
        """Convert DecisionRun ORM object to dict."""
        return {
            "id": str(run.id),
            "tenant_id": str(run.tenant_id),
            "decision_type": run.decision_type,
            "title": run.title,
            "description": run.description,
            "status": run.status,
            "policy_version": run.policy_version,
            "autonomy_level": run.autonomy_level,
            "action_data": run.action_data,
            "expected_impact": run.expected_impact,
            "risk_level": run.risk_level,
            "scenario_id": str(run.scenario_id) if run.scenario_id else None,
            "evidence_refs": run.evidence_refs or [],
            "input_snapshot_hash": run.input_snapshot_hash,
            "prev_hash": run.prev_hash,
            "audit_hash": run.audit_hash,
            "proposed_at": run.proposed_at.isoformat() if run.proposed_at else None,
            "proposed_by": run.proposed_by,
            "approved_at": run.approved_at.isoformat() if run.approved_at else None,
            "executed_at": run.executed_at.isoformat() if run.executed_at else None,
            "executed_by": run.executed_by,
            "rolled_back_at": run.rolled_back_at.isoformat() if run.rolled_back_at else None,
            "rolled_back_by": run.rolled_back_by,
            "rollback_reason": run.rollback_reason,
            "approvals": [
                {
                    "id": str(a.id),
                    "action": a.action,
                    "approved_by": a.approved_by,
                    "approved_at": a.approved_at.isoformat() if a.approved_at else None,
                    "reason": a.reason,
                    "approver_role": a.approver_role,
                    "conditions": a.conditions,
                }
                for a in (run.approvals or [])
            ],
        }





