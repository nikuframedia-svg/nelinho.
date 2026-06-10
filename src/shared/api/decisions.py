"""
ProdPlan ONE - Decision Ledger API
===================================

API for decision management, approval workflows, and audit trail.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.shared.auth.headers import (
    get_current_user_or_dev_header,
    require_tenant_header,
    require_user_uuid,
)
from src.shared.auth.jwt_handler import UserContext
from src.shared.auth.rbac import Role, check_sod
from src.shared.database import get_session
from src.shared.models.governance import SharedDecisionRun, DecisionApproval, DecisionStatus, ApprovalStatus
from src.shared.time import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decisions", tags=["Decisions"])

get_tenant_id = require_tenant_header
get_user_id = require_user_uuid


def _role_from_string(raw: str) -> Role:
    """Q.171.B — papel REAL do contexto auth (era hardcoded
    MANAGER_OPERATIONS para QUALQUER aprovador — bypass de SoD). Aliases
    de admin normalizados a montante (headers.py); desconhecido → 403."""
    try:
        return Role(str(raw or "").strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Papel '{raw}' desconhecido — sem autorização para aprovar.",
        )


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
    """Request to approve/reject a decision.

    Q.118.S — `status` decide aprovar vs rejeitar. Antes era ignorado e o
    endpoint aprovava SEMPRE, por isso o botão "Não" (reject) aprovava a
    decisão. Default "APPROVED" mantém compatibilidade.
    """

    status: Optional[str] = "APPROVED"  # "APPROVED" | "REJECTED"
    comment: Optional[str] = None


class BulkActRequest(BaseModel):
    """Q.130.I — aprovar/rejeitar várias decisões `shared.decision_runs`
    numa só chamada.

    O hub (DecisionsPage) lista decisões de `GET /v1/decisions` (tabela
    `shared.decision_runs`). O bulk antigo apontava para
    `/v1/governance/decisions/bulk`, que opera na tabela DIFERENTE
    `governance.decision_run` — os ids nunca cruzavam, devolvendo sempre
    "0 ok, N falhou". Este endpoint opera na MESMA tabela que o list.

    Per-item: uma falha numa decisão (não-PROPOSED, SoD, id inexistente)
    NÃO aborta as restantes — cada uma traz `{decision_id, status, error}`.
    """

    decision_ids: List[str] = Field(..., min_length=1)
    action: str = "approve"  # "approve" | "reject"
    reason: Optional[str] = None


class ModifyPayloadRequest(BaseModel):
    """Q.130.I — editar o payload (`after_state`) de uma decisão PROPOSED
    antes de aprovar (Plan v4 §8 WG05). `reason` ≥10 chars alimenta o
    audit trail."""

    patch: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., min_length=10)


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
        proposed_at=utc_now(),
    )

    async with session.begin_nested():
        session.add(decision)
        await session.flush()  # populates decision.id

        # Q.61.09 — NAO criamos DecisionApproval no propose. A tabela
        # decision_approvals contem so aprovacoes reais. Approvers pendentes
        # sao derivados de `required_approver_roles - users_que_ja_agiram`.
        # Q.61.18 — audit via service unificado (em vez de inline).
        await audit_change(
            session,
            tenant_id=tenant_id,
            entity_type="decision_run",
            entity_id=decision.id,
            action="INSERT",
            new_values={
                "title": request.title,
                "action_type": request.action_type,
                "target": request.target,
                "status": DecisionStatus.PROPOSED.value,
            },
            actor_id=user_id,
            reason="decision proposed",
        )

    from src.shared.auth.rbac import SOD_POLICIES

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


# BE-10 (Q.130.x): the canonical list path is "/" (-> /v1/decisions/), but the
# frontend polls /v1/decisions (no slash) every 5s. With redirect_slashes=True
# that meant a 307 -> 200 round-trip on EVERY poll. Register the same handler at
# the bare prefix ("") too so both forms answer 200 directly, no redirect. The
# bare alias is hidden from the schema to keep the OpenAPI doc clean.
@router.get("", response_model=DecisionListResponse, include_in_schema=False)
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
            # Q.153 (auditoria) — a lista trazia só campos escalares, mas os
            # cartões de decisão (confiança, porquê, consequências, "Ver plano",
            # €) e o what-if das Simulações leem TODOS de `sandbox_result` →
            # ficavam vazios porque nenhuma vista busca o detalhe. Devolvemos o
            # sandbox_result SEM o array pesado `operations` (que o
            # real_cpo_propose_runner enche com o plano inteiro), para não inflar
            # o payload de até 50 decisões. As entidades clicáveis (que dependem
            # de `operations`) ficam para o detalhe GET /v1/decisions/{id}.
            "sandbox_result": {
                k: v for k, v in (d.sandbox_result or {}).items() if k != "operations"
            },
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
    # Q.171.B — contexto COMPLETO (id + papel real) em vez de só o UUID:
    # o papel do aprovador era hardcoded MANAGER_OPERATIONS → bypass SoD.
    user: UserContext = Depends(get_current_user_or_dev_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Approve a decision (SoD check required).
    
    Verifies approver ≠ proposer, creates approval record, updates decision status.
    """
    
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
    
    user_id = user.user_id
    # Q.171.B — papel REAL do aprovador (check_sod ignora proposer_role;
    # OPERATOR fica como placeholder documentado).
    proposer_role = Role.OPERATOR
    approver_role = _role_from_string(user.role)
    
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

    # Q.118.S — honrar o status pedido. "REJECTED" rejeita; qualquer outro
    # (default) aprova. Antes ignorava-se o campo e aprovava-se sempre.
    is_reject = (request.status or "APPROVED").upper() == "REJECTED"
    approval_status = (
        ApprovalStatus.REJECTED.value if is_reject else ApprovalStatus.APPROVED.value
    )
    decision_status = (
        DecisionStatus.REJECTED.value if is_reject else DecisionStatus.APPROVED.value
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
        existing.status = approval_status
        existing.comment = request.comment
        existing.approved_at = utc_now()
    else:
        approval = DecisionApproval(
            decision_id=decision_id,
            approver_id=user_id,
            status=approval_status,
            comment=request.comment,
            approved_at=utc_now(),
        )
        session.add(approval)

    # Update decision status (aprovada OU rejeitada)
    decision.status = decision_status
    await session.flush()

    # Q.157.F.2 — ligar /decisoes ao CPO: aprovar uma decisão de PLANEAMENTO
    # promove o commit CPO (DRAFT→LIVE) na MESMA tx (write-gate: SoD já validado
    # acima, audit dentro do promote). Rejeitar não promove. Best-effort: commit
    # inexistente/já-LIVE não falha o approve (a decisão fica APPROVED na mesma).
    if not is_reject:
        sb = getattr(decision, "sandbox_result", None) or {}
        after = getattr(decision, "after_state", None) or {}
        commit_sha = str(
            after.get("commit_sha") or sb.get("commit_sha") or ""
        ).strip()
        planning_types = {"ADOPT_PLAN", "REPLAN", "AUTO_PROPOSE_SCHEDULE"}
        if commit_sha and decision.action_type in planning_types:
            try:
                from src.plan.cpo.commits import CommitsService

                promoted = await CommitsService(
                    session, tenant_id,
                ).promote_to_live(commit_sha, approver_id=user_id)
                if promoted is not None:
                    logger.info(
                        "decision %s approved → CPO plan %s promoted to LIVE",
                        decision_id, commit_sha[:8],
                    )
                else:
                    logger.warning(
                        "decision %s approved but CPO commit %s not found — "
                        "decisão fica APPROVED na mesma",
                        decision_id, commit_sha[:8],
                    )
            except Exception as exc:  # best-effort — não falha o approve
                logger.warning(
                    "decision %s approve: promote CPO commit %s falhou: %s",
                    decision_id, commit_sha[:8], exc,
                )

    await session.commit()

    # Q.153 — publicar no canal realtime (SSE) para a página /decisoes e o feed
    # de atividade refletirem a decisão sem esperar o poll de 5s. O ledger shared
    # não publicava DECISION_APPROVED/REJECTED (só execute/rollback o faziam), por
    # isso os listeners `useRealtimeType` ficavam mudos. `event_type` casa com o
    # nome do atributo em Topics. Best-effort: a decisão já está committada.
    event_type = "DECISION_REJECTED" if is_reject else "DECISION_APPROVED"
    try:
        from src.shared.kafka_client import EventBase, Topics, publish_event

        await publish_event(
            getattr(Topics, event_type),
            EventBase(
                event_type=event_type,
                tenant_id=tenant_id,
                source_module="shared.api.decisions",
                payload={
                    "decision_id": str(decision_id),
                    "approver_id": str(user_id),
                    "status": decision_status,
                },
            ),
        )
    except Exception as exc:  # pragma: no cover - best-effort
        logger.warning(
            "%s publish failed for %s: %s — decisão na mesma registada",
            event_type, decision_id, exc,
        )

    logger.info(
        "Decision %s: id=%s, approver=%s",
        "rejected" if is_reject else "approved",
        decision_id,
        user_id,
    )

    return {
        "id": str(decision_id),
        "status": "rejected" if is_reject else "approved",
        "message": (
            "Decision rejected successfully"
            if is_reject
            else "Decision approved successfully"
        ),
    }


@router.post("/bulk", status_code=status.HTTP_200_OK)
async def bulk_act_decisions(
    request: BulkActRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    # Q.171.B — ver approve_decision: papel real, não hardcoded.
    user: UserContext = Depends(get_current_user_or_dev_header),
    session: AsyncSession = Depends(get_session),
):
    """Q.130.I — bulk approve/reject de decisões `shared.decision_runs`.

    Per-item: cada decisão é processada independentemente. Falhas (id
    inexistente, status != PROPOSED, SoD) são reportadas no item, não
    levantam 500. Cada transição escreve `audit_change` na MESMA tx
    (invariante 7, Q.61.18).
    """

    user_id = user.user_id
    approver_role = _role_from_string(user.role)  # Q.171.B — papel real

    is_reject = (request.action or "approve").lower() == "reject"
    approval_status = (
        ApprovalStatus.REJECTED.value if is_reject else ApprovalStatus.APPROVED.value
    )
    target_status = (
        DecisionStatus.REJECTED.value if is_reject else DecisionStatus.APPROVED.value
    )

    results: List[Dict[str, Any]] = []

    for raw_id in request.decision_ids:
        # id mal-formado → falha do item, não 500 da chamada inteira.
        try:
            decision_id = UUID(str(raw_id))
        except (ValueError, AttributeError, TypeError):
            results.append({"decision_id": str(raw_id), "status": "error", "error": "invalid id"})
            continue

        decision = await session.get(SharedDecisionRun, decision_id)
        if not decision or decision.tenant_id != tenant_id:
            results.append({"decision_id": str(raw_id), "status": "error", "error": "not found"})
            continue

        if decision.status != DecisionStatus.PROPOSED.value:
            results.append({
                "decision_id": str(raw_id),
                "status": "error",
                "error": f"cannot act on status {decision.status}",
            })
            continue

        # SoD — mesma política simplificada que o approve single.
        is_valid, error_message = check_sod(
            action_type=decision.action_type,
            proposer_id=decision.proposed_by,
            proposer_role=Role.OPERATOR,  # check_sod ignora (Q.171.B)
            approver_id=user_id,
            approver_role=approver_role,
        )
        if not is_valid:
            results.append({
                "decision_id": str(raw_id),
                "status": "error",
                "error": error_message or "SoD check failed",
            })
            continue

        async with session.begin_nested():
            existing_q = select(DecisionApproval).where(
                DecisionApproval.decision_id == decision_id,
                DecisionApproval.approver_id == user_id,
            )
            existing = (await session.execute(existing_q)).scalar_one_or_none()
            if existing is not None:
                existing.status = approval_status
                existing.comment = request.reason
                existing.approved_at = utc_now()
            else:
                session.add(DecisionApproval(
                    decision_id=decision_id,
                    approver_id=user_id,
                    status=approval_status,
                    comment=request.reason,
                    approved_at=utc_now(),
                ))

            old_status = decision.status
            decision.status = target_status

            await audit_change(
                session,
                tenant_id=tenant_id,
                entity_type="decision_run",
                entity_id=decision.id,
                action="UPDATE",
                old_values={"status": old_status},
                new_values={"status": target_status},
                actor_id=user_id,
                reason=request.reason or ("bulk reject" if is_reject else "bulk approve"),
            )

        results.append({"decision_id": str(decision_id), "status": "ok"})

    await session.commit()

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(
        "Bulk %s: %d ok, %d failed (actor=%s)",
        "reject" if is_reject else "approve", ok, len(results) - ok, user_id,
    )
    return {"ok": ok, "failed": len(results) - ok, "results": results}


@router.patch("/{decision_id}/payload", status_code=status.HTTP_200_OK)
async def modify_decision_payload(
    decision_id: UUID,
    request: ModifyPayloadRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    user_id: UUID = Depends(get_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.130.I — editar o payload (`after_state`) de uma decisão PROPOSED
    antes de aprovar (Plan v4 §8 WG05).

    Opera em `shared.decision_runs` (a mesma tabela do list/approve do
    hub) — o antigo `/v1/governance/decisions/{id}/payload` mexia em
    `governance.decision_run` e dava 400 "not found" para ids do hub.
    O patch é merge raso em `after_state`; a edição é auditada na MESMA
    tx (invariante 7).
    """
    decision = await session.get(SharedDecisionRun, decision_id)

    if not decision or decision.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found",
        )

    if decision.status != DecisionStatus.PROPOSED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payload editável só em PROPOSED. Estado actual: {decision.status}",
        )

    async with session.begin_nested():
        old_after = dict(decision.after_state or {})
        new_after = {**old_after, **request.patch}
        # Reatribuir (não mutar in-place) para o SQLAlchemy detetar o dirty JSONB.
        decision.after_state = new_after

        await audit_change(
            session,
            tenant_id=tenant_id,
            entity_type="decision_run",
            entity_id=decision.id,
            action="UPDATE",
            old_values={"after_state": old_after},
            new_values={"after_state": new_after},
            actor_id=user_id,
            reason=request.reason,
        )

    await session.commit()

    logger.info("Decision payload modified: id=%s, actor=%s", decision_id, user_id)

    return {
        "id": str(decision.id),
        "title": decision.title,
        "action_type": decision.action_type,
        "target": decision.target,
        "status": decision.status,
        "before_state": decision.before_state,
        "after_state": decision.after_state,
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
    decision.executed_at = utc_now()

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
    
    # Verify rollback window (24h from execution).
    # `executed_at` is a DateTime(timezone=True) column -> Postgres returns it
    # tz-aware. Comparing it against a tz-naive `datetime.utcnow()` raised
    # "can't compare offset-naive and offset-aware datetimes" (500) on EVERY
    # executed decision. Compare in UTC-aware; normalise executed_at defensively
    # in case it was ever persisted naive.
    if decision.executed_at:
        executed_at = decision.executed_at
        if executed_at.tzinfo is None:
            executed_at = executed_at.replace(tzinfo=timezone.utc)
        rollback_deadline = executed_at + timedelta(hours=24)
        if datetime.now(timezone.utc) > rollback_deadline:
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

    # Q.130.V — invariante 7: a transição EXECUTED→ROLLED_BACK escreve
    # `audit_change` na MESMA tx que a mudança de estado (o `commit` abaixo
    # fecha ambos juntos), seguindo o padrão Q.61.18 de propose/execute.
    # `rolled_back_at` é tz-aware (consistente com o fix Q.130.U) para
    # comparar com `executed_at` (DateTime(timezone=True)) sem TypeError.
    old_status = decision.status
    decision.status = DecisionStatus.ROLLED_BACK.value
    decision.rolled_back_at = datetime.now(timezone.utc)

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="decision_run",
        entity_id=decision.id,
        action="UPDATE",
        old_values={"status": old_status},
        new_values={
            "status": DecisionStatus.ROLLED_BACK.value,
            "rolled_back_at": decision.rolled_back_at.isoformat(),
        },
        actor_id=user_id,
        reason="decision rolled back (advisory)",
    )

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
