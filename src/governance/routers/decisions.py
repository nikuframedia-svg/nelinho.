"""Decision lifecycle endpoints: propose / list / get / pending-me / approve /
execute / rollback / bulk / payload-patch / audit-pack / delta / kill-switch.

Q.67.6.B5 — split from the legacy ``src/governance/api.py``. All shared
schemas (``DecisionResponse``, ``BulkRequest``, ``ModifyPayloadIn``) live here
because every endpoint in this router consumes or produces them.

Sprint Q.18.A.1: irreversible ops (bulk, payload patch, execute, rollback,
kill-switch) require :func:`require_admin` — any authenticated user could
previously stop production via /kill-switch.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session

from ..models import ApprovalAction, ApprovalRequest, DecisionProposal
from ..service import (
    ApprovalRequiredError,
    GovernanceService,
    SoDViolationError,
)
from ._dependencies import (
    AdminContext,
    get_current_user,
    get_governance_service,
    get_tenant_id,
    require_admin,
)

router = APIRouter(tags=["Governance"])


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


class BulkItemIn(BaseModel):
    decision_id: str
    action: ApprovalAction
    reason: str = Field("", description="Required by approve_decision (min 10 chars)")


class BulkRequest(BaseModel):
    items: List[BulkItemIn]


class ModifyPayloadIn(BaseModel):
    patch: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=10)


# ============================================================================
# PROPOSE / LIST / GET / PENDING-ME / AUDIT-PACK
# ============================================================================

@router.post("/decisions/propose", response_model=DecisionResponse)
async def propose_decision(
    proposal: DecisionProposal,
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """Propose a new decision.

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
    """List decisions with optional filters.

    Supports filtering by status and decision type.
    """
    decisions = await service.list_decisions(
        status=status_filter,
        decision_type=decision_type,
        limit=limit,
        offset=offset,
    )
    return [DecisionResponse(**d) for d in decisions]


@router.get("/decisions/pending/me")
async def get_my_pending_approvals(
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """Get decisions pending approval that current user can approve.

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


@router.get("/decisions/{decision_id}/audit-pack")
async def get_audit_pack(
    decision_id: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """Get complete audit pack for a decision.

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
# APPROVE
# ============================================================================

@router.post("/decisions/{decision_id}/approve")
async def approve_decision(
    decision_id: str,
    request: ApprovalRequest,
    user: str = Depends(get_current_user),
    service: GovernanceService = Depends(get_governance_service),
):
    """Approve, reject, or request changes for a decision.

    Enforces:
    - Separation of Duties (proposer cannot approve own decision)
    - Required number of approvers
    - No duplicate votes from same user
    - Sprint Q.2 — `rejection_category` is mandatory when action=REJECT
      (one of COST | QUALITY | CUSTOMER | CAPACITY | MOLD | WORKFORCE | OTHER).
    """
    if (
        request.action == ApprovalAction.REJECT
        and request.rejection_category is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "rejection_category is required when action=reject "
                "(one of COST, QUALITY, CUSTOMER, CAPACITY, MOLD, "
                "WORKFORCE, OTHER)"
            ),
        )

    try:
        decision = await service.approve_decision(
            decision_id=decision_id,
            action=request.action,
            approved_by=user,
            reason=request.reason,
            conditions=request.conditions,
            rejection_category=(
                request.rejection_category.value
                if request.rejection_category is not None else None
            ),
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
# BULK / MODIFY (Sprint M.2 WG04 + M.4 WG05)
# ============================================================================

@router.post("/decisions/bulk")
async def bulk_act(
    body: BulkRequest,
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """Apply multiple approve/reject/request_changes in a single call.

    Per-item response — a SoD violation on one decision does not abort the rest.

    Sprint Q.18.A.1: admin-only.
    """
    results = await service.bulk_act(
        items=[item.model_dump() for item in body.items],
        approved_by=admin.user_id,
    )
    ok = sum(1 for r in results if r["status"] == "ok")
    return {"ok": ok, "failed": len(results) - ok, "results": results}


@router.patch("/decisions/{decision_id}/payload")
async def modify_decision_payload(
    decision_id: str,
    body: ModifyPayloadIn,
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """Modify a pending decision's payload before approval.

    Sprint Q.18.A.1: admin-only.
    """
    try:
        return await service.modify_payload(
            decision_id=decision_id,
            patch=body.patch,
            modified_by=admin.user_id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# EXECUTE / ROLLBACK
# ============================================================================

@router.post("/decisions/{decision_id}/execute")
async def execute_decision(
    decision_id: str,
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """Execute an approved decision.

    Only approved decisions can be executed.

    Sprint Q.18.A.1: admin-only.
    """
    try:
        decision = await service.execute_decision(
            decision_id=decision_id,
            executed_by=admin.user_id,
        )
        return {
            "success": True,
            "decision_id": decision_id,
            "status": decision["status"],
            "executed_by": admin.user_id,
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
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """Rollback an executed decision.

    Requires a reason (min 10 characters) for audit purposes.

    Sprint Q.18.A.1: admin-only.
    """
    try:
        decision = await service.rollback_decision(
            decision_id=decision_id,
            rolled_back_by=admin.user_id,
            reason=reason,
        )
        return {
            "success": True,
            "decision_id": decision_id,
            "status": decision["status"],
            "rolled_back_by": admin.user_id,
            "rolled_back_at": decision["rolled_back_at"],
            "reason": reason,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ============================================================================
# DECISION DELTA (Sprint M.3 — WG03)
# ============================================================================

@router.get("/decisions/{decision_id}/delta")
async def get_decision_delta(
    decision_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
    service: GovernanceService = Depends(get_governance_service),
):
    """Compute the scheduler delta that this decision represents.

    The decision's `action_data` must include `commit_sha256` pointing to a
    `ScheduleCommit`. We diff that commit against its immediate parent (the
    previous approved plan) so reviewers see *what changed*, not the full plan.

    Returns 404 if:
      * the decision doesn't exist
      * the decision doesn't carry a `commit_sha256` (not a schedule change)
      * the commit or its parent can't be resolved
    """
    decision = await service.get_decision(decision_id)
    if not decision:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Decision {decision_id} not found",
        )
    action_data = decision.get("action_data") or {}
    commit_sha = action_data.get("commit_sha256") or action_data.get("commit_sha")
    if not commit_sha:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Decision has no commit_sha256 in action_data — not a schedule change",
        )

    # Lazy import keeps governance free of plan deps at module import time.
    from src.plan.cpo.commits import CommitsService

    commits = CommitsService(db, tenant_id)
    to_commit = await commits.get_by_sha(commit_sha) or await commits.get_by_sha_prefix(commit_sha)
    if to_commit is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Commit {commit_sha} not found",
        )
    if to_commit.parent_id is None:
        # Root commit — nothing to diff against.
        return {
            "decision_id": decision_id,
            "commit_sha256": to_commit.commit_sha256,
            "parent_sha256": None,
            "is_root_commit": True,
            "diff": None,
        }

    # Resolve the parent by id — CommitsService only exposes sha-based lookup,
    # so do a direct query.
    from sqlalchemy import select as _select
    from src.plan.cpo.commits import ScheduleCommit

    parent_stmt = _select(ScheduleCommit).where(
        (ScheduleCommit.tenant_id == tenant_id) & (ScheduleCommit.id == to_commit.parent_id)
    )
    parent = (await db.execute(parent_stmt)).scalar_one_or_none()
    if parent is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Parent commit of {commit_sha} not found",
        )

    diff = await commits.diff(parent.commit_sha256, to_commit.commit_sha256)
    return {
        "decision_id": decision_id,
        "commit_sha256": to_commit.commit_sha256,
        "parent_sha256": parent.commit_sha256,
        "trust_index_before": parent.trust_index,
        "trust_index_after": to_commit.trust_index,
        "trust_index_delta": round(to_commit.trust_index - parent.trust_index, 4),
        "diff": diff,
    }


# ============================================================================
# KILL SWITCH
# ============================================================================

@router.post("/kill-switch")
async def activate_kill_switch(
    scope: str = Query(..., description="Scope to kill (e.g., 'all', 'decision_type:X')"),
    reason: str = Query(..., min_length=10, description="Reason for kill switch"),
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """EMERGENCY: Activate kill switch.

    This immediately stops execution of decisions in the specified scope.
    No approval required - this is for emergency situations only.

    All kill switch activations are logged and audited.
    """
    decision = await service.activate_kill_switch(
        scope=scope,
        activated_by=admin.user_id,
        reason=reason,
    )
    return {
        "success": True,
        "kill_switch_id": decision["id"],
        "scope": scope,
        "activated_by": admin.user_id,
        "activated_at": decision["executed_at"],
        "reason": reason,
        "warning": "KILL SWITCH ACTIVATED - Decisions in scope are now blocked",
    }


__all__ = [
    "router",
    "BulkItemIn",
    "BulkRequest",
    "DecisionResponse",
    "ModifyPayloadIn",
]
