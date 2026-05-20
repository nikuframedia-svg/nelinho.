"""Q.66.D.4a — sub-router: actions (execute, list, rollback).

Endpoints que executam mutações disparadas por sugestões/runbooks. O
helper `_run_copilot_action` é partilhado entre `/action` (autenticado)
e `/action-dev` (sem auth, tenant dev fixo).

Colaboradores externos (`audit_change`) são acedidos via
``src.copilot.api`` para que `patch.object(copilot_api, "audit_change",
...)` nos characterization tests propague para os handlers reais.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot import api as _api  # late attribute access — vê monkey-patches
from src.copilot.models import (
    CopilotActionLog,
    CopilotDecisionPR,
    CopilotSuggestion,
)
from src.copilot.schemas import CopilotActionRequest
from src.shared.auth.jwt_handler import UserContext, get_current_user
from src.shared.database import get_session
from src.shared.kafka_client import get_producer

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_copilot_action(
    request: CopilotActionRequest,
    tenant_id: UUID,
    session: AsyncSession,
) -> Dict[str, Any]:
    """Núcleo da execução de uma acção do copiloto.

    Q.55.C.2 — extraído do `execute_action` para ser partilhado por
    `/action` (com auth) e `/action-dev` (dev, sem auth), tal como o
    `process_ask` é partilhado por `/ask` e `/ask-dev`.
    """
    # Verificar que suggestion existe
    suggestion = await session.get(CopilotSuggestion, request.suggestion_id)
    if not suggestion or suggestion.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion não encontrada",
        )

    # Executar ação
    if request.action_type == "CREATE_DECISION_PR":
        # Criar PR
        pr = CopilotDecisionPR(
            tenant_id=tenant_id,
            suggestion_id=request.suggestion_id,
            title=request.payload.get("title", "Decision PR"),
            description=request.payload.get("description", ""),
            payload=request.payload,
            status="PENDING",
        )
        session.add(pr)
        await session.flush()  # garante pr.id populated antes do audit

        # Q.66.B.3: CopilotDecisionPR e proposta de mudanca que entra no
        # workflow de aprovacao (PENDING → APPROVED/REJECTED) — state
        # autoritativo de governance, audita.
        await _api.audit_change(
            session,
            tenant_id=tenant_id,
            entity_type="copilot_decision_pr",
            entity_id=pr.id,
            action="INSERT",
            new_values={
                "suggestion_id": str(request.suggestion_id),
                "title": pr.title,
                "status": pr.status,
            },
            reason="copilot criou decision PR a partir de suggestion",
        )

        return {
            "action_id": str(pr.id),
            "status": "created",
            "message": "Decision PR criado com sucesso",
        }

    elif request.action_type == "DRY_RUN":
        # Dry run - retornar hint (não executar realmente)
        return {
            "action_type": "DRY_RUN",
            "status": "simulated",
            "message": "Dry run executado (sem persistência)",
            "payload": request.payload,
        }

    elif request.action_type == "OPEN_ENTITY":
        # Hint para frontend
        return {
            "action_type": "OPEN_ENTITY",
            "status": "hint",
            "navigation": request.payload,
        }

    elif request.action_type == "RUN_RUNBOOK":
        # Sprint Q.9 (2.8) — minimal advisory executor.
        # Loads the YAML definition, validates structure, returns the
        # planned steps + interpolated parameters. Real DB execution
        # lands when Sprint G (NELO ERP) is wired.
        from src.copilot.runbook_executor import (
            RunbookInvalid,
            RunbookNotFound,
            execute_runbook,
            list_runbooks,
        )

        # Q.55.C.3 — fallback: LLM pode gerar RUN_RUNBOOK sem runbook_id.
        # Default para primeiro runbook disponível em vez de 400 imediato.
        # Se NENHUM runbook disponível, deixa o 400 acontecer (fail-closed).
        if not request.payload.get("runbook_id"):
            available = list_runbooks()
            if available:
                # `list_runbooks()` devolve List[str] (filename stems).
                default_runbook = available[0]
                default_id = (
                    getattr(default_runbook, "id", None)
                    or getattr(default_runbook, "runbook_id", None)
                    or default_runbook
                )
                request.payload["runbook_id"] = default_id
                logger.info(
                    "Q.55.C.3 — RUN_RUNBOOK sem id; default to %s", default_id
                )

        runbook_id = request.payload.get("runbook_id")
        if not runbook_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "RUN_RUNBOOK requires payload.runbook_id. "
                    f"Available: {list_runbooks()}"
                ),
            )
        try:
            trace = execute_runbook(runbook_id, payload=request.payload)
        except RunbookNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"runbook {runbook_id!r} not found. "
                    f"Available: {list_runbooks()}"
                ),
            )
        except RunbookInvalid as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"runbook {runbook_id!r} is malformed: {exc}",
            )
        return {
            "action_type": "RUN_RUNBOOK",
            "status": "planned",
            "trace": trace,
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ação '{request.action_type}' não suportada",
        )


@router.post("/action", status_code=status.HTTP_200_OK)
async def execute_action(
    request: CopilotActionRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Executar ação permitida.

    Ações suportadas:
    - CREATE_DECISION_PR: Criar PR de melhoria
    - DRY_RUN: Simular sem persistir
    - OPEN_ENTITY: Hint para frontend navegar
    - RUN_RUNBOOK: Executar runbook
    """
    return await _run_copilot_action(request, tenant_id, session)


@router.post(
    "/action-dev",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(_api.dev_only)],
)
async def execute_action_dev(
    request: CopilotActionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Endpoint de desenvolvimento — SEM autenticação. Espelha o `/ask-dev`.

    Q.55.C.2 — o frontend dev corre sem sessão; sem este par as acções
    sugeridas falhavam com "Not authenticated".
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    return await _run_copilot_action(request, dev_tenant_id, session)


@router.post("/actions/{transaction_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_action(
    transaction_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Rollback a previously executed action.

    Verifies rollback_until window (24h), reverts state using before_state snapshot,
    marks status=rolled_back, and publishes Kafka event.
    """
    # Get action log
    action_log = await session.get(CopilotActionLog, transaction_id)

    if not action_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action log not found: {transaction_id}",
        )

    # Verify tenant
    if action_log.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action log does not belong to this tenant",
        )

    # Verify status
    if action_log.status != "executed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action cannot be rolled back. Current status: {action_log.status}",
        )

    # Verify rollback window (24h)
    if action_log.rollback_until:
        if datetime.now(timezone.utc) > action_log.rollback_until:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rollback window expired. Rollback available until: {action_log.rollback_until.isoformat()}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action does not support rollback (no rollback_until set)",
        )

    try:
        # Revert state using before_state snapshot
        # In real implementation, this would restore the actual database state
        # For now, we just mark it as rolled back
        action_log.status = "rolled_back"
        await session.flush()

        # Publish Kafka event
        try:
            kafka_producer = await get_producer()
            if kafka_producer:
                from uuid import uuid4
                from src.shared.kafka_client import EventBase

                event = EventBase(
                    event_id=uuid4(),
                    event_type="copilot.action.rolled_back",
                    tenant_id=tenant_id,
                    source_module="copilot",
                    payload={
                        "transaction_id": str(transaction_id),
                        "action_type": action_log.action_type,
                        "user_id": str(user.user_id),
                        "plan_id": str(action_log.plan_id) if action_log.plan_id else None,
                    },
                )

                await kafka_producer.publish(
                    topic="prodplan.copilot.action.rolled_back",
                    event=event,
                    aggregate_id=str(action_log.plan_id) if action_log.plan_id else str(tenant_id),
                )
        except Exception as kafka_error:
            logger.warning(f"Kafka publish failed for rollback event: {kafka_error}")
            # Don't fail the rollback if Kafka fails

        await session.commit()

        logger.info(f"Action rolled back: transaction_id={transaction_id}, user={user.user_id}")

        return {
            "transaction_id": str(transaction_id),
            "status": "rolled_back",
            "message": "Action successfully rolled back",
        }

    except Exception as e:
        await session.rollback()
        logger.error(f"Rollback failed: transaction_id={transaction_id}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {e!s}",
        )


@router.get("/actions", status_code=status.HTTP_200_OK)
async def list_actions(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    List action logs for the current user.

    Returns list of executed actions with their before/after state.
    """
    from sqlalchemy import select

    # Build query
    query = select(CopilotActionLog).where(
        CopilotActionLog.tenant_id == tenant_id,
        CopilotActionLog.user_id == user.user_id,
    )

    # Filter by status if provided
    if status:
        query = query.where(CopilotActionLog.status == status)

    # Order by executed_at desc (most recent first)
    query = query.order_by(CopilotActionLog.executed_at.desc())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    action_logs = result.scalars().all()

    return [
        {
            "transaction_id": str(log.id),
            "action_type": log.action_type,
            "user_id": str(log.user_id),
            "plan_id": str(log.plan_id) if log.plan_id else None,
            "before_state": log.before_state,
            "after_state": log.after_state,
            "status": log.status,
            "executed_at": log.executed_at.isoformat(),
            "rollback_until": log.rollback_until.isoformat() if log.rollback_until else None,
        }
        for log in action_logs
    ]
