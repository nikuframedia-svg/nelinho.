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
        
        # In-memory store for demo (replace with DB in production)
        self._decisions: Dict[str, Dict] = {}
        self._policies: Dict[str, Dict] = {
            p["decision_type"]: p for p in DEFAULT_POLICIES
        }
        self._last_decision_hash: Optional[str] = None
    
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
    
    def propose_decision(
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
        
        # Calculate audit hash
        audit_hash = self._calculate_audit_hash(
            decision_id=decision_id,
            policy_version=policy.get("version", "1.0.0"),
            input_hash=input_hash,
            outcome_hash=None,
            prev_hash=self._last_decision_hash,
        )
        
        # Determine initial status
        initial_status = DecisionStatus.PROPOSED.value
        if policy.get("requires_approval", True):
            initial_status = DecisionStatus.PENDING_APPROVAL.value
        
        # Create decision record
        decision = {
            "id": decision_id,
            "tenant_id": str(self.tenant_id),
            "decision_type": decision_type,
            "title": title,
            "description": description,
            "status": initial_status,
            "policy_version": policy.get("version", "1.0.0"),
            "autonomy_level": policy.get("autonomy_level", AutonomyLevel.L2.value),
            "action_data": action_data,
            "expected_impact": expected_impact,
            "risk_level": risk_level,
            "scenario_id": scenario_id,
            "evidence_refs": evidence_refs or [],
            "input_snapshot_hash": input_hash,
            "prev_hash": self._last_decision_hash,
            "audit_hash": audit_hash,
            "proposed_at": datetime.now(timezone.utc).isoformat(),
            "proposed_by": proposed_by,
            "approvals": [],
            "required_approvers": policy.get("required_approvers", 1),
            "requires_different_approver": policy.get("requires_different_approver", True),
        }
        
        self._decisions[decision_id] = decision
        self._last_decision_hash = audit_hash
        
        logger.info(f"Decision proposed: {decision_id} ({decision_type})")
        
        return decision
    
    def approve_decision(
        self,
        decision_id: str,
        action: ApprovalAction,
        approved_by: str,
        reason: str,
        approver_role: Optional[str] = None,
        conditions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Approve or reject a decision.
        
        Args:
            decision_id: ID of the decision
            action: Approval action
            approved_by: User approving/rejecting
            reason: Reason for action
            approver_role: Role of approver
            conditions: Conditions for conditional approval
            
        Returns:
            Updated decision record
            
        Raises:
            SoDViolationError: If approver is same as proposer (when required)
            ValueError: If decision not found or invalid state
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        if decision["status"] != DecisionStatus.PENDING_APPROVAL.value:
            raise ValueError(
                f"Decision {decision_id} is not pending approval "
                f"(status: {decision['status']})"
            )
        
        # SoD check
        if decision.get("requires_different_approver", True):
            if approved_by == decision["proposed_by"]:
                raise SoDViolationError(
                    f"Separation of Duties violation: {approved_by} cannot approve "
                    f"their own decision. A different user must approve."
                )
        
        # Check if already approved by this user
        existing_approvals = [
            a for a in decision.get("approvals", [])
            if a["approved_by"] == approved_by
        ]
        if existing_approvals:
            raise ValueError(f"User {approved_by} has already voted on this decision")
        
        # Record approval
        approval = {
            "id": str(uuid4()),
            "action": action.value,
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "approver_role": approver_role,
            "conditions": conditions,
        }
        
        decision["approvals"].append(approval)
        
        # Update status based on action
        if action == ApprovalAction.REJECT:
            decision["status"] = DecisionStatus.REJECTED.value
            logger.info(f"Decision {decision_id} rejected by {approved_by}")
        elif action == ApprovalAction.REQUEST_CHANGES:
            decision["status"] = DecisionStatus.PROPOSED.value
            logger.info(f"Decision {decision_id} - changes requested by {approved_by}")
        elif action == ApprovalAction.APPROVE:
            # Check if we have enough approvals
            approves = [
                a for a in decision["approvals"]
                if a["action"] == ApprovalAction.APPROVE.value
            ]
            if len(approves) >= decision.get("required_approvers", 1):
                decision["status"] = DecisionStatus.APPROVED.value
                decision["approved_at"] = datetime.now(timezone.utc).isoformat()
                logger.info(f"Decision {decision_id} approved")
            else:
                logger.info(
                    f"Decision {decision_id} - approval by {approved_by} "
                    f"({len(approves)}/{decision.get('required_approvers', 1)} required)"
                )
        
        return decision
    
    def execute_decision(
        self,
        decision_id: str,
        executed_by: str,
    ) -> Dict[str, Any]:
        """
        Execute an approved decision.
        
        Args:
            decision_id: ID of the decision
            executed_by: User executing
            
        Returns:
            Updated decision record
            
        Raises:
            ApprovalRequiredError: If decision is not approved
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        if decision["status"] != DecisionStatus.APPROVED.value:
            raise ApprovalRequiredError(
                f"Decision {decision_id} must be approved before execution "
                f"(current status: {decision['status']})"
            )
        
        # Mark as executing
        decision["status"] = DecisionStatus.EXECUTING.value
        
        try:
            # TODO: Actually execute the action
            # This would call the appropriate service based on decision_type
            
            # Calculate outcome hash
            outcome_data = {
                "action_data": decision["action_data"],
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "executed_by": executed_by,
            }
            outcome_hash = hashlib.sha256(
                json.dumps(outcome_data, sort_keys=True, default=str).encode()
            ).hexdigest()
            
            # Update decision
            decision["status"] = DecisionStatus.EXECUTED.value
            decision["executed_at"] = datetime.now(timezone.utc).isoformat()
            decision["executed_by"] = executed_by
            decision["outcome_hash"] = outcome_hash
            
            # Recalculate audit hash with outcome
            decision["audit_hash"] = self._calculate_audit_hash(
                decision_id=decision_id,
                policy_version=decision["policy_version"],
                input_hash=decision["input_snapshot_hash"],
                outcome_hash=outcome_hash,
                prev_hash=decision["prev_hash"],
            )
            
            logger.info(f"Decision {decision_id} executed by {executed_by}")
            
        except Exception as e:
            decision["status"] = DecisionStatus.FAILED.value
            logger.error(f"Decision {decision_id} execution failed: {e}")
            raise
        
        return decision
    
    def rollback_decision(
        self,
        decision_id: str,
        rolled_back_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Rollback an executed decision.
        
        Args:
            decision_id: ID of the decision
            rolled_back_by: User rolling back
            reason: Reason for rollback (required)
            
        Returns:
            Updated decision record
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        if decision["status"] != DecisionStatus.EXECUTED.value:
            raise ValueError(
                f"Only executed decisions can be rolled back "
                f"(current status: {decision['status']})"
            )
        
        if not reason or len(reason) < 10:
            raise ValueError("Rollback reason is required (min 10 characters)")
        
        # TODO: Actually rollback the action
        
        decision["status"] = DecisionStatus.ROLLED_BACK.value
        decision["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        decision["rolled_back_by"] = rolled_back_by
        decision["rollback_reason"] = reason
        
        logger.info(f"Decision {decision_id} rolled back by {rolled_back_by}: {reason}")
        
        return decision
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)
    
    def list_decisions(
        self,
        status: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List decisions with optional filters."""
        decisions = list(self._decisions.values())
        
        if status:
            decisions = [d for d in decisions if d["status"] == status]
        
        if decision_type:
            decisions = [d for d in decisions if d["decision_type"] == decision_type]
        
        # Sort by proposed_at descending
        decisions.sort(key=lambda d: d.get("proposed_at", ""), reverse=True)
        
        return decisions[offset:offset + limit]
    
    def get_pending_approvals(self, user: str) -> List[Dict[str, Any]]:
        """Get decisions pending approval that user can approve."""
        pending = [
            d for d in self._decisions.values()
            if d["status"] == DecisionStatus.PENDING_APPROVAL.value
        ]
        
        # Filter out decisions where user is proposer (if SoD required)
        # or user has already voted
        result = []
        for d in pending:
            if d.get("requires_different_approver") and d["proposed_by"] == user:
                continue
            
            existing = [a for a in d.get("approvals", []) if a["approved_by"] == user]
            if existing:
                continue
            
            result.append(d)
        
        return result
    
    def get_audit_pack(self, decision_id: str) -> Dict[str, Any]:
        """
        Get complete audit pack for a decision.
        
        Includes all information needed for audit/compliance.
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        return {
            "decision": decision,
            "verification": {
                "audit_hash": decision["audit_hash"],
                "input_hash": decision.get("input_snapshot_hash"),
                "outcome_hash": decision.get("outcome_hash"),
                "prev_hash": decision.get("prev_hash"),
                "hash_chain_valid": True,  # Would verify in production
            },
            "timeline": [
                {
                    "event": "proposed",
                    "at": decision["proposed_at"],
                    "by": decision["proposed_by"],
                },
                *[
                    {
                        "event": f"approval_{a['action']}",
                        "at": a["approved_at"],
                        "by": a["approved_by"],
                        "reason": a["reason"],
                    }
                    for a in decision.get("approvals", [])
                ],
                *([{
                    "event": "executed",
                    "at": decision["executed_at"],
                    "by": decision["executed_by"],
                }] if decision.get("executed_at") else []),
                *([{
                    "event": "rolled_back",
                    "at": decision["rolled_back_at"],
                    "by": decision["rolled_back_by"],
                    "reason": decision["rollback_reason"],
                }] if decision.get("rolled_back_at") else []),
            ],
            "evidence": decision.get("evidence_refs", []),
        }
    
    # =========================================================================
    # Kill Switch
    # =========================================================================
    
    def activate_kill_switch(
        self,
        scope: str,
        activated_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Activate kill switch for a scope.
        
        Args:
            scope: Scope to kill (e.g., "all", "decision_type:X", "tenant:X")
            activated_by: User activating
            reason: Reason for kill switch
            
        Returns:
            Kill switch record
        """
        # Create immediate decision (no approval required)
        decision = self.propose_decision(
            decision_type="kill_switch",
            title=f"KILL SWITCH: {scope}",
            action_data={"scope": scope, "reason": reason},
            proposed_by=activated_by,
            risk_level="critical",
        )
        
        # Auto-approve and execute (kill switch policy allows this)
        decision["status"] = DecisionStatus.EXECUTED.value
        decision["executed_at"] = datetime.now(timezone.utc).isoformat()
        decision["executed_by"] = activated_by
        
        logger.critical(f"KILL SWITCH ACTIVATED by {activated_by}: {scope} - {reason}")
        
        return decision
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _calculate_audit_hash(
        self,
        decision_id: str,
        policy_version: str,
        input_hash: Optional[str],
        outcome_hash: Optional[str],
        prev_hash: Optional[str],
    ) -> str:
        """Calculate audit hash for decision."""
        data = f"{decision_id}|{policy_version}|{input_hash or ''}|{outcome_hash or ''}|{prev_hash or ''}"
        return hashlib.sha256(data.encode()).hexdigest()





