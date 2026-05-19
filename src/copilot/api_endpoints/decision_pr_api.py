"""
Q.37.C — Ciclo de vida do CREATE_DECISION_PR
=============================================

O `CREATE_DECISION_PR` cria um `CopilotDecisionPR` em PENDING. Faltava
o resto do ciclo: listar, aprovar (com SoD), rejeitar, executar.

Invariante 4 — o copiloto **propõe**, um humano **aprova**, e só depois
há **execução**. Este router materializa esses três passos:

  GET  /api/copilot/decision-prs            — listar (filtro por status)
  GET  /api/copilot/decision-prs/{id}       — um PR
  POST /api/copilot/decision-prs/{id}/approve  — aprovar (SoD: aprovador
                                                 != proponente)
  POST /api/copilot/decision-prs/{id}/reject   — rejeitar
  POST /api/copilot/decision-prs/{id}/execute  — executar (só de APPROVED)

SoD (Segregation of Duties): o proponente é o `actor_id` da
`CopilotSuggestion` ligada ao PR. `check_sod` de `src/shared/auth/rbac.py`
recusa que o mesmo utilizador aprove a sua própria proposta (403).

Sem migration Alembic — os campos novos do ciclo (rejected_by,
rejected_at, executed_by, execution_result) vão para o `payload` JSONB
existente do `CopilotDecisionPR`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.actions import (
    Action,
    ActionExecutor,
    ActionHandlerNotImplementedError,
    ActionMode,
)
from src.copilot.models import CopilotDecisionPR, CopilotSuggestion
from src.shared.auth.jwt_handler import UserContext, get_current_user
from src.shared.auth.rbac import Role, check_sod
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["COPILOT Decision PRs"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extrai o tenant do header X-Tenant-Id."""
    return x_tenant_id


# ─────────────────────────────────────────────────────────────────────
# Serialização
# ─────────────────────────────────────────────────────────────────────

def _pr_to_dict(pr: CopilotDecisionPR) -> Dict[str, Any]:
    payload = pr.payload or {}
    return {
        "id": str(pr.id),
        "suggestion_id": str(pr.suggestion_id),
        "title": pr.title,
        "description": pr.description,
        "status": pr.status,
        "action_type": payload.get("action_type"),
        "payload": payload,
        "approved_by": str(pr.approved_by) if pr.approved_by else None,
        "approved_at": pr.approved_at.isoformat() if pr.approved_at else None,
        "rejected_by": payload.get("rejected_by"),
        "rejected_at": payload.get("rejected_at"),
        "executed_by": payload.get("executed_by"),
        "execution_result": payload.get("execution_result"),
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
    }


async def _load_pr(
    pr_id: UUID, tenant_id: UUID, session: AsyncSession
) -> CopilotDecisionPR:
    pr = await session.get(CopilotDecisionPR, pr_id)
    if not pr or pr.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision PR não encontrado",
        )
    return pr


def _patch_payload(pr: CopilotDecisionPR, updates: Dict[str, Any]) -> None:
    """Funde `updates` no payload JSONB e marca o campo como sujo.

    SQLAlchemy não deteca mutações in-place de um dict JSONB — é preciso
    reatribuir o atributo para que o flush persista a mudança.
    """
    merged = dict(pr.payload or {})
    merged.update(updates)
    pr.payload = merged


# ─────────────────────────────────────────────────────────────────────
# GET — listar / um
# ─────────────────────────────────────────────────────────────────────

@router.get("/decision-prs", status_code=status.HTTP_200_OK)
async def list_decision_prs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> List[Dict[str, Any]]:
    """Lista Decision PRs do tenant, opcionalmente filtrados por status."""
    query = select(CopilotDecisionPR).where(
        CopilotDecisionPR.tenant_id == tenant_id
    )
    if status_filter:
        query = query.where(CopilotDecisionPR.status == status_filter.upper())
    query = query.order_by(CopilotDecisionPR.created_at.desc()).limit(limit).offset(offset)

    result = await session.execute(query)
    return [_pr_to_dict(pr) for pr in result.scalars().all()]


@router.get("/decision-prs/{pr_id}", status_code=status.HTTP_200_OK)
async def get_decision_pr(
    pr_id: UUID,
    _user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Devolve um Decision PR."""
    pr = await _load_pr(pr_id, tenant_id, session)
    return _pr_to_dict(pr)


# ─────────────────────────────────────────────────────────────────────
# POST — approve / reject / execute
# ─────────────────────────────────────────────────────────────────────

@router.post("/decision-prs/{pr_id}/approve", status_code=status.HTTP_200_OK)
async def approve_decision_pr(
    pr_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Aprova um Decision PR PENDING.

    SoD — o aprovador NÃO pode ser o proponente. O proponente é o
    `actor_id` da `CopilotSuggestion` ligada ao PR.
    """
    pr = await _load_pr(pr_id, tenant_id, session)
    if pr.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PR não está PENDING (status actual: {pr.status})",
        )

    suggestion = await session.get(CopilotSuggestion, pr.suggestion_id)
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion ligada ao PR não encontrada",
        )
    proposer_id = suggestion.actor_id

    # SoD — `check_sod` recusa aprovador == proponente.
    try:
        approver_role = Role(user.role)
        proposer_role = Role(suggestion.actor_role)
    except ValueError:
        # Papéis fora do enum — fallback genérico (o check de identidade
        # abaixo é o que mais importa).
        approver_role = Role.MANAGER_OPERATIONS
        proposer_role = Role.MANAGER_OPERATIONS

    action_type = (pr.payload or {}).get("action_type", "GENERIC_ACTION")
    is_valid, error = check_sod(
        action_type=action_type,
        proposer_id=proposer_id,
        proposer_role=proposer_role,
        approver_id=user.user_id,
        approver_role=approver_role,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Segregation of Duties: {error}",
        )

    pr.status = "APPROVED"
    pr.approved_by = user.user_id
    pr.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await session.commit()

    logger.info("Decision PR %s aprovado por %s", pr_id, user.user_id)
    return _pr_to_dict(pr)


@router.post("/decision-prs/{pr_id}/reject", status_code=status.HTTP_200_OK)
async def reject_decision_pr(
    pr_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Rejeita um Decision PR PENDING."""
    pr = await _load_pr(pr_id, tenant_id, session)
    if pr.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PR não está PENDING (status actual: {pr.status})",
        )

    pr.status = "REJECTED"
    _patch_payload(pr, {
        "rejected_by": str(user.user_id),
        "rejected_at": datetime.now(timezone.utc).isoformat(),
    })
    await session.commit()

    logger.info("Decision PR %s rejeitado por %s", pr_id, user.user_id)
    return _pr_to_dict(pr)


@router.post("/decision-prs/{pr_id}/execute", status_code=status.HTTP_200_OK)
async def execute_decision_pr(
    pr_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Executa um Decision PR — só de status APPROVED.

    Chama o `ActionExecutor` em modo EXECUTE com o `payload.action_type`
    (handler real registado em Q.37.D). O `ActionExecutor` grava o
    `CopilotActionLog` (audit trail).
    """
    pr = await _load_pr(pr_id, tenant_id, session)
    if pr.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Só PRs APPROVED podem executar (status actual: {pr.status}). "
                "Invariante 4 — aprovação humana antes da execução."
            ),
        )

    payload = pr.payload or {}
    action_type = payload.get("action_type")
    if not action_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload.action_type em falta — nada para executar.",
        )

    action = Action(
        action_id=str(uuid4()),
        action_type=action_type,
        description=pr.title,
        modes=["execute"],
        estimated_impact=payload.get("estimated_impact", {}),
        payload=payload,
    )
    executor = ActionExecutor(
        session=session,
        tenant_id=tenant_id,
        user_id=user.user_id,
        kafka_producer=None,
    )
    try:
        result = await executor.execute_action(
            action=action,
            mode=ActionMode.EXECUTE,
            plan_id=None,
        )
    except ActionHandlerNotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        )
    except ValueError as exc:
        # Handler recusou (ex.: axioma 7 no inventário) — input inválido.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    pr.status = "EXECUTED"
    _patch_payload(pr, {
        "executed_by": str(user.user_id),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "execution_result": result,
    })
    await session.commit()

    logger.info("Decision PR %s executado por %s", pr_id, user.user_id)
    return _pr_to_dict(pr)
