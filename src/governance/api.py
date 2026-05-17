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
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from .models import (
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

# Q.17.C — yaml_policy sub-router (NL→YAML rule authoring + lifecycle)
from src.governance.yaml_policy.api import router as _yaml_policy_router  # noqa: E402
router.include_router(_yaml_policy_router)


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

from src.shared.auth.headers import (
    AdminContext,
    require_admin,
    require_tenant_header,
    require_user_header,
)

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID/'api_user' defaults with
# fail-closed dependencies that return 401 when the header is absent.
# Sprint Q.18.A.1: irreversible ops below (bulk, payload patch, execute,
# rollback, kill-switch) now require :func:`require_admin` instead of
# :func:`require_user_header`. Any authenticated user could previously
# stop production via /kill-switch — closed with a single dep swap.
get_tenant_id = require_tenant_header
get_current_user = require_user_header


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


# ============================================================================
# TIMELINE (Sprint M.1 — Write-Gate WG02/WG08)
# ============================================================================

class BulkItemIn(BaseModel):
    decision_id: str
    action: ApprovalAction
    reason: str = Field("", description="Required by approve_decision (min 10 chars)")


class BulkRequest(BaseModel):
    items: List[BulkItemIn]


class ModifyPayloadIn(BaseModel):
    patch: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=10)


@router.get("/decisions/timeline")
async def get_timeline(
    group_by: str = Query(
        "criticality",
        description="criticality | risk_level | decision_type | status",
    ),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    actor_id: Optional[str] = Query(None, description="Proposer filter"),
    autonomy_level: Optional[str] = Query(None),
    min_impact: Optional[float] = Query(
        None,
        description="WG08 anti-fatigue: hide decisions with expected_impact magnitude below this",
    ),
    hide_low_risk: bool = Query(False, description="WG08 anti-fatigue"),
    max_per_user_shown: Optional[int] = Query(
        None,
        description="WG08 anti-fatigue: cap rows per proposer inside each group",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    service: GovernanceService = Depends(get_governance_service),
):
    """Pending-decision dashboard grouped by criticality / risk / type / status."""
    try:
        return await service.get_timeline(
            group_by=group_by,
            since=since, until=until,
            actor_id=actor_id, autonomy_level=autonomy_level,
            min_impact=min_impact,
            hide_low_risk=hide_low_risk,
            max_per_user_shown=max_per_user_shown,
            page=page, page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# BULK APPROVE (Sprint M.2 — WG04)
# ============================================================================

@router.post("/decisions/bulk")
async def bulk_act(
    body: BulkRequest,
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """Apply multiple approve/reject/request_changes in a single call.

    Per-item response — a SoD violation on one decision does not abort the rest.

    Sprint Q.18.A.1: admin-only. Bulk approve/reject is a privileged
    operation — single approvals still go through the per-item endpoint
    where SoD enforces "approver != proposer".
    """
    results = await service.bulk_act(
        items=[item.model_dump() for item in body.items],
        approved_by=admin.user_id,
    )
    ok = sum(1 for r in results if r["status"] == "ok")
    return {"ok": ok, "failed": len(results) - ok, "results": results}


# ============================================================================
# MODIFY BEFORE APPROVE (Sprint M.4 — WG05)
# ============================================================================

@router.patch("/decisions/{decision_id}/payload")
async def modify_decision_payload(
    decision_id: str,
    body: ModifyPayloadIn,
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """Modify a pending decision's payload before approval.

    Sprint Q.18.A.1: admin-only. Editing a proposed decision changes
    what every subsequent approver votes on — concentrate the trust
    surface on admins.
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
# AUDIT TIMELINE (Sprint M.6 — WG06)
# ============================================================================

@router.get("/audit/timeline")
async def get_audit_timeline(
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    actor: Optional[str] = Query(None),
    limit: int = Query(200, ge=10, le=1000),
    service: GovernanceService = Depends(get_governance_service),
):
    """Chronological cross-decision event stream (propose/approve/execute/rollback)."""
    return {
        "events": await service.get_audit_timeline(
            since=since, until=until, actor=actor, limit=limit,
        ),
    }


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
# EXECUTION ENDPOINTS
# ============================================================================

@router.post("/decisions/{decision_id}/execute")
async def execute_decision(
    decision_id: str,
    admin: AdminContext = Depends(require_admin),
    service: GovernanceService = Depends(get_governance_service),
):
    """
    Execute an approved decision.

    Only approved decisions can be executed.

    Sprint Q.18.A.1: admin-only. Execution writes to the production
    schedule/inventory/payroll — irreversible without a rollback decision.
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
    """
    Rollback an executed decision.

    Requires a reason (min 10 characters) for audit purposes.

    Sprint Q.18.A.1: admin-only. Rolling back inverts production state
    — same blast radius as execute.
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


@router.post("/kill-switch")
async def activate_kill_switch(
    scope: str = Query(..., description="Scope to kill (e.g., 'all', 'decision_type:X')"),
    reason: str = Query(..., min_length=10, description="Reason for kill switch"),
    admin: AdminContext = Depends(require_admin),
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


# ============================================================================
# RULE FIRING LOG (Sprint Q.14.A)
# ============================================================================
#
# The audit substrate for *"why did this suggestion appear?"* — every
# instrumented detector / LLM producer persists a row to
# `governance.rule_firing` (see src/shared/decorators.py). This endpoint
# is the read surface: cursor-paginated list with filters by rule_id +
# outcome + date range. Frontend `RuleFiringsPage` (Q.15) consumes it.


class RuleFiringResponse(BaseModel):
    """One audit row from `governance.rule_firing`."""

    id: str
    rule_id: str
    variant_id: Optional[str] = None
    fired_at: str
    last_fired_at: Optional[str] = None
    fire_count: int
    outcome: str
    dedupe_key: Optional[str] = None
    correlation_id: Optional[str] = None
    trigger_payload: Dict[str, Any] = Field(default_factory=dict)
    rule_output: Dict[str, Any] = Field(default_factory=dict)
    accepted_at: Optional[str] = None
    accepted_by: Optional[str] = None
    notes: Optional[str] = None


@router.get(
    "/rule-firings",
    response_model=List[RuleFiringResponse],
)
async def list_rule_firings(
    rule_id: Optional[str] = Query(None, description="Filter by rule_id"),
    outcome: Optional[str] = Query(
        None,
        description="Filter by outcome (proposed/accepted/rejected/expired/superseded)",
    ),
    since: Optional[datetime] = Query(
        None, description="Only firings on/after this timestamp (UTC)",
    ),
    until: Optional[datetime] = Query(
        None, description="Only firings before this timestamp (UTC)",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> List[RuleFiringResponse]:
    """List rule firings for the current tenant.

    Sprint Q.14.A — answers the *"why did the system suggest X 3 weeks
    ago?"* question. Filters compose with AND. Default order is most-
    recent first (so paginating "give me the last 50" works without a
    cursor).
    """
    from sqlalchemy import select
    from src.governance.models import RuleFiring

    stmt = (
        select(RuleFiring)
        .where(RuleFiring.tenant_id == tenant_id)
        .order_by(RuleFiring.fired_at.desc())
    )
    if rule_id is not None:
        stmt = stmt.where(RuleFiring.rule_id == rule_id)
    if outcome is not None:
        stmt = stmt.where(RuleFiring.outcome == outcome)
    if since is not None:
        stmt = stmt.where(RuleFiring.fired_at >= since)
    if until is not None:
        stmt = stmt.where(RuleFiring.fired_at < until)

    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()

    return [
        RuleFiringResponse(
            id=str(r.id),
            rule_id=r.rule_id,
            variant_id=r.variant_id,
            fired_at=r.fired_at.isoformat(),
            last_fired_at=(
                r.last_fired_at.isoformat() if r.last_fired_at else None
            ),
            fire_count=r.fire_count,
            outcome=r.outcome,
            dedupe_key=r.dedupe_key,
            correlation_id=str(r.correlation_id) if r.correlation_id else None,
            trigger_payload=r.trigger_payload or {},
            rule_output=r.rule_output or {},
            accepted_at=r.accepted_at.isoformat() if r.accepted_at else None,
            accepted_by=str(r.accepted_by) if r.accepted_by else None,
            notes=r.notes,
        )
        for r in rows
    ]


class RuleFiringOutcomeUpdate(BaseModel):
    """Body for `PATCH /v1/governance/rule-firings/{id}/outcome`."""

    outcome: str = Field(..., description="New outcome: accepted/rejected/expired/superseded")
    notes: Optional[str] = Field(None, max_length=1000)


@router.patch("/rule-firings/{firing_id}/outcome")
async def update_rule_firing_outcome(
    firing_id: UUID,
    payload: RuleFiringOutcomeUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update the outcome of a rule firing — closes the audit loop.

    When an operator accepts / rejects a suggestion in the UI, the
    frontend posts here. The Q.14.C A/B framework reads
    ``accepted/(accepted+rejected+expired)`` per ``rule_id`` to compare
    variants. Without this endpoint, every row stays at ``proposed``
    forever and adoption stats are meaningless.
    """
    from sqlalchemy import select, update
    from src.governance.models import RuleFiring, RuleFiringOutcome

    valid_outcomes = {
        RuleFiringOutcome.ACCEPTED.value,
        RuleFiringOutcome.REJECTED.value,
        RuleFiringOutcome.EXPIRED.value,
        RuleFiringOutcome.SUPERSEDED.value,
    }
    if payload.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid outcome '{payload.outcome}'. "
                f"Allowed: {sorted(valid_outcomes)}"
            ),
        )

    stmt = select(RuleFiring).where(
        RuleFiring.id == firing_id,
        RuleFiring.tenant_id == tenant_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"rule firing {firing_id} not found in this tenant",
        )

    now = datetime.utcnow()
    user_uuid: Optional[UUID] = None
    try:
        user_uuid = UUID(str(user))
    except (ValueError, TypeError):
        # `get_current_user` returns a string; if it's not a UUID,
        # we keep accepted_by NULL but still record the notes/outcome.
        pass

    await db.execute(
        update(RuleFiring)
        .where(RuleFiring.id == firing_id)
        .values(
            outcome=payload.outcome,
            accepted_at=now if payload.outcome == RuleFiringOutcome.ACCEPTED.value else row.accepted_at,
            accepted_by=user_uuid if payload.outcome == RuleFiringOutcome.ACCEPTED.value else row.accepted_by,
            notes=payload.notes,
        )
    )
    await db.commit()
    return {"id": str(firing_id), "outcome": payload.outcome}


# ============================================================================
# A/B ADOPTION STATS (Sprint Q.14.C)
# ============================================================================


@router.get("/rule-firings/adoption")
async def rule_firings_adoption(
    rule_id: str = Query(..., description="rule_id to summarise"),
    credible_interval: float = Query(
        0.95, ge=0.5, lt=1.0,
        description="Bayesian credible interval level (0.5-0.99)",
    ),
    min_sample: int = Query(
        50, ge=1,
        description="Minimum decided firings per variant before winner declared",
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Per-variant adoption stats for an A/B'd rule.

    Sprint Q.14.C — answers *"is variant A actually beating variant B?"*
    Aggregates `rule_firing` rows by `(variant_id, outcome)` and returns
    per-variant Bayesian Beta-Bernoulli posterior + 95% credible
    interval. A "winner" is declared only when the top variant's CI
    sits strictly above the runner-up's CI AND both have enough sample
    (`min_sample`, default 50).

    Returns the shape :class:`AdoptionReport` produces (see
    src/governance/ab_framework.py). Frontend
    `RuleFiringsAdoptionPage` (Q.15) consumes it.
    """
    from sqlalchemy import func, select

    from src.governance.ab_framework import compute_adoption_stats
    from src.governance.models import RuleFiring

    stmt = (
        select(
            RuleFiring.variant_id,
            RuleFiring.outcome,
            func.count(RuleFiring.id).label("n"),
        )
        .where(RuleFiring.tenant_id == tenant_id)
        .where(RuleFiring.rule_id == rule_id)
        .where(RuleFiring.variant_id.is_not(None))
        .group_by(RuleFiring.variant_id, RuleFiring.outcome)
    )
    result = await db.execute(stmt)
    rows = [
        (variant_id, outcome, int(n))
        for variant_id, outcome, n in result.all()
    ]

    report = compute_adoption_stats(
        rule_id=rule_id,
        rows=rows,
        credible_interval=credible_interval,
        min_sample_for_winner=min_sample,
    )
    return report.to_dict()


# ──────────────────────────────────────────────────────────────────────────
# Onda 14 N — Activity outbox ledger viewer
# ──────────────────────────────────────────────────────────────────────────

@router.get("/event-outbox")
async def list_event_outbox(
    status_filter: Optional[str] = None,
    limit: int = 50,
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session),
):
    """Lista eventos do outbox (pending/sent/failed)."""
    from sqlalchemy import select as _sa_select
    from src.shared.outbox_models import EventOutbox
    stmt = _sa_select(EventOutbox).where(EventOutbox.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(EventOutbox.status == status_filter)
    stmt = stmt.order_by(EventOutbox.created_at.desc()).limit(max(1, min(limit, 200)))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "status": r.status,
                "aggregate_id": str(r.aggregate_id) if getattr(r, "aggregate_id", None) else None,
                "payload_keys": list(r.payload.keys()) if isinstance(r.payload, dict) else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


# ──────────────────────────────────────────────────────────────────────────
# Onda 14 N — RBAC matrix viewer
# ──────────────────────────────────────────────────────────────────────────

@router.get("/rbac/matrix")
async def get_rbac_matrix():
    """Devolve a matriz roles × permissions actual (Sprint Q.18.N)."""
    from src.shared.auth.rbac import ROLE_PERMISSIONS, Role, Permission
    return {
        "roles": [r.value for r in Role],
        "permissions": [p.value for p in Permission],
        "matrix": {
            role.value: sorted([p.value for p in perms])
            for role, perms in ROLE_PERMISSIONS.items()
        },
    }


