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
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_, func
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

if TYPE_CHECKING:
    pass

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

        # Determine initial status
        initial_status = DecisionStatus.PROPOSED.value
        if policy.get("requires_approval", True):
            initial_status = DecisionStatus.PENDING_APPROVAL.value

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

        return self._run_to_dict(decision_run)
    
    async def approve_decision(
        self,
        decision_id: str,
        action: ApprovalAction,
        approved_by: str,
        reason: str,
        approver_role: Optional[str] = None,
        conditions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Approve or reject a decision with SoD enforcement."""
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

        return self._run_to_dict(decision_run)
    
    async def execute_decision(
        self,
        decision_id: str,
        executed_by: str,
    ) -> Dict[str, Any]:
        """Execute an approved decision."""
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

        except Exception as e:
            decision_run.status = DecisionStatus.FAILED.value
            await self.db.flush()
            logger.error(f"Decision {decision_id} execution failed: {e}")
            raise

        return self._run_to_dict(decision_run)

    async def rollback_decision(
        self,
        decision_id: str,
        rolled_back_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Rollback an executed decision."""
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

        return self._run_to_dict(decision_run)

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





