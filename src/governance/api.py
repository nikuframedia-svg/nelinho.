"""
Governance API — Decision Management Endpoints
================================================

Exposes:
- Decision proposal and lifecycle
- Approval workflow
- Audit pack retrieval
- Kill switch
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from .models import (
    AutonomyLevel,
    DecisionStatus,
    ApprovalAction,
    DecisionProposal,
    ApprovalRequest,
)
from .service import (
    GovernanceService,
    SoDViolationError,
    ApprovalRequiredError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/governance", tags=["Governance"])


# ============================================================================
# SCHEMAS
# ============================================================================

class DecisionResponse(BaseModel):
    """Response for a decision."""
    id: str
    decision_type: str
    title: str
    description: Optional[str] = None
    status: str
    autonomy_level: str
    risk_level: str
    proposed_at: str
    proposed_by: str
    approvals: List[Dict[str, Any]] = Field(default_factory=list)
    audit_hash: str
    executed_at: Optional[str] = None
    executed_by: Optional[str] = None


class PolicyResponse(BaseModel):
    """Response for a policy."""
    decision_type: str
    autonomy_level: str
    requires_approval: bool
    required_approvers: int
    requires_different_approver: bool
    description: Optional[str] = None


# ============================================================================
# DEPENDENCIES
# ============================================================================

def get_tenant_id(x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000"))) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


def get_current_user(x_user_id: str = Header(default="api_user")) -> str:
    """Extract current user from header."""
    return x_user_id


async def get_governance_service(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> GovernanceService:
    """Get governance service with DB session."""
    return GovernanceService(db=db, tenant_id=tenant_id)


# ============================================================================
# POLICY ENDPOINTS
# ============================================================================

@router.get("/policies", response_model=List[PolicyResponse])
async def list_policies(
    service: GovernanceService = Depends(get_governance_service),
):
    """
    List all decision policies.
    
    Policies define the governance rules for each decision type.
    """
    return [PolicyResponse(**p) for p in service.list_policies()]


@router.get("/policies/{decision_type}", response_model=PolicyResponse)
async def get_policy(
    decision_type: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """Get policy for a specific decision type."""
    policy = service.get_policy(decision_type)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No policy found for decision type: {decision_type}",
        )
    return PolicyResponse(**policy)


# ============================================================================
# DECISION ENDPOINTS
# ============================================================================

@router.post("/decisions/propose", response_model=DecisionResponse)
async def propose_decision(
    proposal: DecisionProposal,
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Propose a new decision.
    
    This creates a decision record and initiates the approval workflow
    based on the policy for the decision type.
    """
    decision = await service.propose_decision(
        decision_type=proposal.decision_type,
        title=proposal.title,
        action_data=proposal.action_data,
        proposed_by=user,
        description=proposal.description,
        expected_impact=proposal.expected_impact,
        risk_level=proposal.risk_level,
        scenario_id=proposal.scenario_id,
        evidence_refs=proposal.evidence_refs,
    )

    return DecisionResponse(**decision)


@router.get("/decisions", response_model=List[DecisionResponse])
async def list_decisions(
    status_filter: Optional[str] = Query(None, alias="status"),
    decision_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    List decisions with optional filters.
    
    Supports filtering by status and decision type.
    """
    decisions = await service.list_decisions(
        status=status_filter,
        decision_type=decision_type,
        limit=limit,
        offset=offset,
    )

    return [DecisionResponse(**d) for d in decisions]


@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """Get details of a specific decision."""
    decision = await service.get_decision(decision_id)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found",
        )
    return DecisionResponse(**decision)


@router.get("/decisions/pending/me")
async def get_my_pending_approvals(
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Get decisions pending approval that current user can approve.
    
    Filters out decisions where:
    - User is the proposer (if SoD required)
    - User has already voted
    """
    pending = await service.get_pending_approvals(user)

    return {
        "user": user,
        "pending": [DecisionResponse(**d) for d in pending],
        "count": len(pending),
    }


# ============================================================================
# APPROVAL ENDPOINTS
# ============================================================================

@router.post("/decisions/{decision_id}/approve")
async def approve_decision(
    decision_id: str,
    request: ApprovalRequest,
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Approve, reject, or request changes for a decision.
    
    Enforces:
    - Separation of Duties (proposer cannot approve own decision)
    - Required number of approvers
    - No duplicate votes from same user
    """
    try:
        decision = await service.approve_decision(
            decision_id=decision_id,
            action=request.action,
            approved_by=user,
            reason=request.reason,
            conditions=request.conditions,
        )
        
        return {
            "success": True,
            "decision_id": decision_id,
            "new_status": decision["status"],
            "action": request.action.value,
            "approved_by": user,
            "message": f"Decision {request.action.value}d successfully",
        }
        
    except SoDViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# EXECUTION ENDPOINTS
# ============================================================================

@router.post("/decisions/{decision_id}/execute")
async def execute_decision(
    decision_id: str,
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Execute an approved decision.
    
    Only approved decisions can be executed.
    """
    try:
        decision = await service.execute_decision(
            decision_id=decision_id,
            executed_by=user,
        )
        
        return {
            "success": True,
            "decision_id": decision_id,
            "status": decision["status"],
            "executed_by": user,
            "executed_at": decision["executed_at"],
            "outcome_hash": decision.get("outcome_hash"),
        }
        
    except ApprovalRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/decisions/{decision_id}/rollback")
async def rollback_decision(
    decision_id: str,
    reason: str = Query(..., min_length=10, description="Reason for rollback"),
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Rollback an executed decision.
    
    Requires a reason (min 10 characters) for audit purposes.
    """
    try:
        decision = await service.rollback_decision(
            decision_id=decision_id,
            rolled_back_by=user,
            reason=reason,
        )
        
        return {
            "success": True,
            "decision_id": decision_id,
            "status": decision["status"],
            "rolled_back_by": user,
            "rolled_back_at": decision["rolled_back_at"],
            "reason": reason,
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# AUDIT ENDPOINTS
# ============================================================================

@router.get("/decisions/{decision_id}/audit-pack")
async def get_audit_pack(
    decision_id: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Get complete audit pack for a decision.
    
    Includes:
    - Full decision record
    - Hash chain verification
    - Complete timeline
    - Evidence references
    """
    try:
        return await service.get_audit_pack(decision_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ============================================================================
# KILL SWITCH
# ============================================================================

@router.post("/kill-switch")
async def activate_kill_switch(
    scope: str = Query(..., description="Scope to kill (e.g., 'all', 'decision_type:X')"),
    reason: str = Query(..., min_length=10, description="Reason for kill switch"),
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    EMERGENCY: Activate kill switch.
    
    This immediately stops execution of decisions in the specified scope.
    No approval required - this is for emergency situations only.
    
    All kill switch activations are logged and audited.
    """
    decision = await service.activate_kill_switch(
        scope=scope,
        activated_by=user,
        reason=reason,
    )
    
    return {
        "success": True,
        "kill_switch_id": decision["id"],
        "scope": scope,
        "activated_by": user,
        "activated_at": decision["executed_at"],
        "reason": reason,
        "warning": "KILL SWITCH ACTIVATED - Decisions in scope are now blocked",
    }





