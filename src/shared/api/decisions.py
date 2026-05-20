"""
ProdPlan ONE - Decision Ledger API
===================================

API for decision management, approval workflows, and audit trail.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.shared.auth.headers import require_tenant_header, require_user_uuid
from src.shared.database import get_session
from src.shared.models.governance import SharedDecisionRun, DecisionApproval, DecisionStatus, ApprovalStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decisions", tags=["Decisions"])

get_tenant_id = require_tenant_header
get_user_id = require_user_uuid


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class DecisionProposalRequest(BaseModel):
    """Request to propose a decision."""
    
    title: str = Field(..., min_length=1, max_length=255)
    action_type: str = Field(..., min_length=1, max_length=50)  # "INCREASE_SS", "ADJUST_PRICE", etc.
    target: str = Field(..., min_length=1, max_length=255)  # SKU ID, product ID, etc.
    sandbox_result: Optional[Dict[str, Any]] = None
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Optional[Dict[str, Any]] = None


class DecisionListResponse(BaseModel):
    """Response for decision list."""
    
    decisions: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class DecisionDetailResponse(BaseModel):
    """Response for decision detail."""
    
    id: UUID
    title: str
    action_type: str
    target: str
    status: str
    sandbox_result: Optional[Dict[str, Any]]
    before_state: Dict[str, Any]
    after_state: Optional[Dict[str, Any]]
    proposed_by: UUID
    proposed_at: datetime
    executed_at: Optional[datetime]
    rolled_back_at: Optional[datetime]
    approvals: List[Dict[str, Any]]


class DecisionApprovalRequest(BaseModel):
    """Request to approve/reject a decision."""
    
    comment: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/propose", status_code=status.HTTP_201_CREATED)
async def propose_decision(
    request: DecisionProposalRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Propose a new decision (convert sandbox preview to decision proposal).
    
    Creates DecisionRun with status "PROPOSED" and routes to approvers based on SoD policy.
    """
    # Q.61.10 — Unit-of-Work: DecisionRun INSERT + AuditLog INSERT
    # numa unica transaccao (savepoint). Se a auditoria falhar, a
    # decision tambem rollback — invariante 7 (audit na MESMA tx que
    # a mudanca de estado) deixa de depender de disciplina humana.
    decision = SharedDecisionRun(
        tenant_id=tenant_id,
        title=request.title,
        action_type=request.action_type,
        target=request.target,
        status=DecisionStatus.PROPOSED.value,
        sandbox_result=request.sandbox_result,
        before_state=request.before_state,
        after_state=request.after_state,
        proposed_by=user_id,
        proposed_at=datetime.utcnow(),
    )

    async with session.begin_nested():
        session.add(decision)
        await session.flush()  # populates decision.id

        # Q.61.09 — NAO criamos DecisionApproval no propose. A tabela
        # decision_approvals contem so aprovacoes reais. Approvers pendentes
        # sao derivados de `required_approver_roles - users_que_ja_agiram`.
        audit = AuditLog(
            tenant_id=tenant_id,
            entity_type="decision_run",
            entity_id=decision.id,
            action="INSERT",
            old_values=None,
            new_values={
                "title": request.title,
                "action_type": request.action_type,
                "target": request.target,
                "status": DecisionStatus.PROPOSED.value,
            },
            actor_id=user_id,
            reason="decision proposed",
        )
        session.add(audit)

    from src.shared.auth.rbac import SOD_POLICIES, Role

    required_approver_roles = SOD_POLICIES.get(
        request.action_type,
        SOD_POLICIES.get("GENERIC_ACTION", [Role.MANAGER_OPERATIONS])
    )

    logger.info(
        f"Decision proposed: id={decision.id}, title={request.title}, "
        f"action_type={request.action_type}, required_roles={[r.value for r in required_approver_roles]}"
    )

    return {
        "id": str(decision.id),
        "status": "proposed",
        "message": "Decision proposal created successfully",
    }


@router.get("/", response_model=DecisionListResponse)
async def list_decisions(
    status_filter: Optional[str] = Query(None, alias="status_filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """List decisions with filtering and pagination."""
    
    # Build query
    query = select(SharedDecisionRun).where(SharedDecisionRun.tenant_id == tenant_id)
    
    if status_filter:
        try:
            status_enum = DecisionStatus(status_filter.upper())
            query = query.where(SharedDecisionRun.status == status_enum.value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(desc(SharedDecisionRun.proposed_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    # Execute
    result = await session.execute(query)
    decisions = result.scalars().all()
    
    # Serialize
    decisions_list = [
        {
            "id": str(d.id),
            "title": d.title,
            "action_type": d.action_type,
            "target": d.target,
            "status": d.status,
            "proposed_by": str(d.proposed_by),
            "proposed_at": d.proposed_at.isoformat(),
            "executed_at": d.executed_at.isoformat() if d.executed_at else None,
        }
        for d in decisions
    ]
    
    return DecisionListResponse(
        decisions=decisions_list,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{decision_id}", response_model=DecisionDetailResponse)
async def get_decision(
    decision_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get decision detail with approvals."""
    
    decision = await session.get(SharedDecisionRun, decision_id)
    
    if not decision or decision.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )
    
    # Load approvals
    approvals_query = select(DecisionApproval).where(
        DecisionApproval.decision_id == decision_id
    )
    approvals_result = await session.execute(approvals_query)
    approvals = approvals_result.scalars().all()
    
    return DecisionDetailResponse(
        id=decision.id,
        title=decision.title,
        action_type=decision.action_type,
        target=decision.target,
        status=decision.status,
        sandbox_result=decision.sandbox_result,
        before_state=decision.before_state,
        after_state=decision.after_state,
        proposed_by=decision.proposed_by,
        proposed_at=decision.proposed_at,
        executed_at=decision.executed_at,
        rolled_back_at=decision.rolled_back_at,
        approvals=[
            {
                "id": str(a.id),
                "approver_id": str(a.approver_id),
                "status": a.status,
                "comment": a.comment,
                "approved_at": a.approved_at.isoformat() if a.approved_at else None,
            }
            for a in approvals
        ],
    )


@router.post("/{decision_id}/approve", status_code=status.HTTP_200_OK)
async def approve_decision(
    decision_id: UUID,
    request: DecisionApprovalRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Approve a decision (SoD check required).
    
    Verifies approver ≠ proposer, creates approval record, updates decision status.
    """
    from src.shared.auth.rbac import check_sod, Role
    
    decision = await session.get(SharedDecisionRun, decision_id)
    
    if not decision or decision.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )
    
    # Verify status
    if decision.status != DecisionStatus.PROPOSED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decision cannot be approved. Current status: {decision.status}",
        )
    
    # Check SoD policy (simplified for development without full auth)
    proposer_role = Role.OPERATOR  # Default fallback
    approver_role = Role.MANAGER_OPERATIONS  # Default approver role
    
    is_valid, error_message = check_sod(
        action_type=decision.action_type,
        proposer_id=decision.proposed_by,
        proposer_role=proposer_role,
        approver_id=user_id,
        approver_role=approver_role,
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message or "SoD check failed",
        )

    # Q.61.09 — find_or_create. Antes do Q.61.09 o propose criava sempre
    # um placeholder com approver_id=proposer; quando este endpoint
    # corria, criava-se um SEGUNDO row, deixando o primeiro orfao. Agora
    # so existem rows reais.
    existing_q = select(DecisionApproval).where(
        DecisionApproval.decision_id == decision_id,
        DecisionApproval.approver_id == user_id,
    )
    existing = (await session.execute(existing_q)).scalar_one_or_none()
    if existing is not None:
        existing.status = ApprovalStatus.APPROVED.value
        existing.comment = request.comment
        existing.approved_at = datetime.utcnow()
    else:
        approval = DecisionApproval(
            decision_id=decision_id,
            approver_id=user_id,
            status=ApprovalStatus.APPROVED.value,
            comment=request.comment,
            approved_at=datetime.utcnow(),
        )
        session.add(approval)

    # Update decision status
    decision.status = DecisionStatus.APPROVED.value
    await session.flush()

    await session.commit()
    
    logger.info(f"Decision approved: id={decision_id}, approver={user_id}")
    
    return {
        "id": str(decision_id),
        "status": "approved",
        "message": "Decision approved successfully",
    }


@router.post("/{decision_id}/execute", status_code=status.HTTP_200_OK)
async def execute_decision(
    decision_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Execute an approved decision.
    
    Verifies status is APPROVED, executes action, updates status to EXECUTED.
    """
    decision = await session.get(SharedDecisionRun, decision_id)
    
    if not decision or decision.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )
    
    # Verify status
    if decision.status != DecisionStatus.APPROVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decision cannot be executed. Current status: {decision.status}",
        )
    
    # Sprint Q.9 (2.2) — advisory mode by design until Sprint G (NELO ERP)
    # is wired. We mark the decision EXECUTED in the audit trail and publish
    # a DECISION_EXECUTED Kafka event so the realtime layer (SSE) reflects
    # the change. No physical mutation of the ERP / schedule until the
    # ActionExecutor handlers are wired against real systems — see
    # `governance.action_executor` for the registry that takes over once
    # Sprint G lands.
    decision.status = DecisionStatus.EXECUTED.value
    decision.executed_at = datetime.utcnow()

    await session.commit()

    # Best-effort event publish — advisory loop should still notify clients.
    try:
        from src.shared.kafka_client import publish_event, Topics, EventBase
        await publish_event(
            Topics.DECISION_EXECUTED,
            EventBase(
                event_type="DECISION_EXECUTED",
                tenant_id=tenant_id,
                source_module="shared.api.decisions",
                payload={
                    "decision_id": str(decision_id),
                    "executor_id": str(user_id),
                    "executed_at": decision.executed_at.isoformat(),
                    "advisory_mode": True,
                },
            ),
        )
    except Exception as exc:
        logger.warning(
            "DECISION_EXECUTED publish failed for %s: %s — audit trail still set",
            decision_id, exc,
        )

    logger.info(
        "Decision executed (advisory): id=%s, executor=%s",
        decision_id, user_id,
    )

    return {
        "id": str(decision_id),
        "status": "executed",
        "executed_at": decision.executed_at.isoformat(),
        "advisory_mode": True,
        "message": "Decision marked EXECUTED (advisory; ERP integration in Sprint G)",
    }


@router.post("/{decision_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_decision(
    decision_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Rollback an executed decision (within 24h window).
    
    Verifies rollback window, reverts state using before_state, updates status to ROLLED_BACK.
    """
    decision = await session.get(SharedDecisionRun, decision_id)
    
    if not decision or decision.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )
    
    # Verify status
    if decision.status != DecisionStatus.EXECUTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decision cannot be rolled back. Current status: {decision.status}",
        )
    
    # Verify rollback window (24h from execution)
    if decision.executed_at:
        rollback_deadline = decision.executed_at + timedelta(hours=24)
        if datetime.utcnow() > rollback_deadline:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rollback window expired. Deadline: {rollback_deadline.isoformat()}",
            )
    
    # Sprint Q.9 (2.3) — advisory rollback. The `before_state` snapshot is
    # exposed to the caller for audit, but no physical revert is performed
    # against the ERP / schedule until Sprint G. Surfacing the snapshot lets
    # downstream consumers (Timeline UI, audit reports) show the operator
    # what would have been reverted.
    before_state_snapshot = (
        decision.before_state if hasattr(decision, "before_state") else None
    )

    decision.status = DecisionStatus.ROLLED_BACK.value
    decision.rolled_back_at = datetime.utcnow()

    await session.commit()

    try:
        from src.shared.kafka_client import publish_event, Topics, EventBase
        await publish_event(
            Topics.DECISION_ROLLED_BACK,
            EventBase(
                event_type="DECISION_ROLLED_BACK",
                tenant_id=tenant_id,
                source_module="shared.api.decisions",
                payload={
                    "decision_id": str(decision_id),
                    "user_id": str(user_id),
                    "rolled_back_at": decision.rolled_back_at.isoformat(),
                    "advisory_mode": True,
                    "before_state_present": before_state_snapshot is not None,
                },
            ),
        )
    except Exception as exc:
        logger.warning(
            "DECISION_ROLLED_BACK publish failed for %s: %s — audit trail still set",
            decision_id, exc,
        )

    logger.info(
        "Decision rolled back (advisory): id=%s, user=%s",
        decision_id, user_id,
    )

    return {
        "id": str(decision_id),
        "status": "rolled_back",
        "rolled_back_at": decision.rolled_back_at.isoformat(),
        "before_state": before_state_snapshot,
        "advisory_mode": True,
        "message": "Decision marked ROLLED_BACK (advisory; ERP revert in Sprint G)",
    }


@router.get("/{decision_id}/audit", response_model=Dict[str, Any])
async def get_decision_audit(
    decision_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get full audit trail for a decision."""
    
    decision = await session.get(SharedDecisionRun, decision_id)
    
    if not decision or decision.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )
    
    # Load approvals
    approvals_query = select(DecisionApproval).where(
        DecisionApproval.decision_id == decision_id
    )
    approvals_result = await session.execute(approvals_query)
    approvals = approvals_result.scalars().all()
    
    return {
        "decision": {
            "id": str(decision.id),
            "title": decision.title,
            "action_type": decision.action_type,
            "target": decision.target,
            "status": decision.status,
            "proposed_by": str(decision.proposed_by),
            "proposed_at": decision.proposed_at.isoformat(),
            "executed_at": decision.executed_at.isoformat() if decision.executed_at else None,
            "rolled_back_at": decision.rolled_back_at.isoformat() if decision.rolled_back_at else None,
        },
        "approvals": [
            {
                "id": str(a.id),
                "approver_id": str(a.approver_id),
                "status": a.status,
                "comment": a.comment,
                "approved_at": a.approved_at.isoformat() if a.approved_at else None,
            }
            for a in approvals
        ],
        "state_changes": {
            "before_state": decision.before_state,
            "after_state": decision.after_state,
        },
    }
