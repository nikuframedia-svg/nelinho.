"""Q.66.D.4a — sub-router: health / sandbox / rag-ingest / causal-audit.

Agrupa endpoints operacionais e ortogonais ao chat: health-check do
Ollama, reset manual do circuit breaker, execução em sandbox isolada,
ingestão RAG e gravação de CausalChain (Camada-4 ABL).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot import api as _api  # late attribute access — vê monkey-patches
from src.copilot.actions import ActionHandlerNotImplementedError, ActionMode, list_available_action_types
from src.copilot.schemas import SandboxRequest, SandboxResponse
from src.shared.auth.jwt_handler import UserContext, get_current_user
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.config import settings
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────
# POST /rag/ingest
# ──────────────────────────────────────────────────────────────────────────


class RagIngestRequest(BaseModel):
    """Q.171.C — contrato do ingest RAG com bounds."""

    source_type: str = Field(..., min_length=1, max_length=64)
    source_id: str = Field(..., min_length=1, max_length=256)
    text: str = Field(..., min_length=1, max_length=100_000)
    metadata: Optional[dict] = None


@router.post("/rag/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_rag_document(
    # Q.171.C — eram 3 query-strings SEM bounds (DoS por texto gigante no
    # pipeline de embeddings). Body tipado com limites honestos.
    body: "RagIngestRequest",
    user: UserContext = Depends(
        PermissionDependency([Permission.CONFIG_WRITE])
    ),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Ingestão de documento para RAG (admin only).

    Aceita markdown/PDF/texto.
    """
    chunks_created = await _api.ingest_document(
        session,
        tenant_id,
        body.source_type,
        body.source_id,
        body.text,
        body.metadata,
    )

    return {
        "status": "success",
        "chunks_created": chunks_created,
        "source_type": body.source_type,
        "source_id": body.source_id,
    }


# ──────────────────────────────────────────────────────────────────────────
# Health + circuit breaker
# ──────────────────────────────────────────────────────────────────────────


@router.post("/health/reset-circuit")
async def reset_circuit_breaker():
    """
    Reset manual do circuit breaker do Ollama (útil para debugging).
    """
    try:
        ollama_client = _api.get_ollama_client()
        ollama_client.reset_circuit_breaker()
        return {
            "status": "success",
            "message": "Circuit breaker resetado",
        }
    except Exception as e:
        logger.error(f"Erro ao resetar circuit breaker: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


@router.get("/health")
async def copilot_health(response: Response):
    """
    Health check do COPILOT.

    Verifica: Ollama, DB, embeddings, rate limit.
    Retorna 503 quando Ollama está offline (degraded) para que probes de
    orquestração detectem a degradação via HTTP status code.
    """
    try:
        ollama_client = _api.get_ollama_client()

        # Se circuit breaker está aberto, tentar resetar se já passou tempo suficiente
        if hasattr(ollama_client, '_circuit_open_until') and ollama_client._circuit_open_until:
            remaining = (ollama_client._circuit_open_until - datetime.now(timezone.utc)).total_seconds()
            if remaining < 0:
                # Circuit já deveria estar fechado, resetar manualmente
                ollama_client.reset_circuit_breaker()
                logger.info("Circuit breaker resetado no health check")

        ollama_online = await ollama_client.health_check()

        # Log detalhado para debugging
        if not ollama_online:
            circuit_info = "fechado"
            if hasattr(ollama_client, '_circuit_open_until') and ollama_client._circuit_open_until:
                remaining = (ollama_client._circuit_open_until - datetime.now(timezone.utc)).total_seconds()
                circuit_info = f"aberto (fecha em {remaining:.1f}s)"

            logger.warning(
                f"Ollama está offline. Base URL: {ollama_client.base_url}. "
                f"Circuit breaker: {circuit_info}. "
                f"Failure count: {getattr(ollama_client, '_failure_count', 0)}"
            )

        body = {
            "status": "healthy" if ollama_online else "degraded",
            "ollama": "online" if ollama_online else "offline",
            "embeddings_model": getattr(settings, "copilot_embeddings_model", "all-minilm"),
            "ollama_base_url": ollama_client.base_url,
            "ollama_model": settings.ollama_model,
            "rate_limit": {
                "per_hour": settings.copilot_rate_limit_per_hour,
                "per_day": settings.copilot_rate_limit_per_day,
            },
        }
        if not ollama_online:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return body
    except Exception as e:
        logger.error(f"Erro no health check do COPILOT: {e}", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "ollama": "offline",
            "error": "Erro interno no health check.",
            "embeddings_model": getattr(settings, "copilot_embeddings_model", "all-minilm"),
        }


# ──────────────────────────────────────────────────────────────────────────
# POST /sandbox
# ──────────────────────────────────────────────────────────────────────────


@router.get("/sandbox/actions")
async def list_sandbox_actions(
    # Mesmos guards do POST /sandbox — a lista de handlers é discovery
    # interno, não conteúdo público (gate Q.168.D de cobertura tenant).
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
):
    """Lista os action_types com handler registado (útil para discovery pela UI)."""
    return {"available_types": list_available_action_types()}


@router.post("/sandbox", response_model=SandboxResponse, status_code=status.HTTP_200_OK)
async def execute_sandbox(
    request: SandboxRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Execute action in sandbox (isolated transaction with auto-rollback).

    Uses ActionExecutor with SANDBOX mode to test actions without committing changes.
    Returns before/after state and deltas for preview.

    Request:
    {
        "action_type": "INCREASE_SS",
        "target": "SKU-123",
        "params": {"qty": 100},
        "capture_state": ["inventory", "kpis"]
    }

    Response:
    {
        "success": true,
        "before_state": {...},
        "after_state": {...},
        "deltas": {...},
        "actual_impact": {...},
        "message": "..."
    }
    """
    from src.copilot.actions import Action

    # Create Action object from request
    action = Action(
        action_id=str(uuid4()),
        action_type=request.action_type,
        description=f"Sandbox execution: {request.action_type} on {request.target}",
        modes=["preview", "sandbox", "execute"],
        estimated_impact={},  # Will be calculated
        payload={
            "target": request.target,
            **request.params,
        },
    )

    # Create executor
    executor = _api.ActionExecutor(
        session=session,
        tenant_id=tenant_id,
        user_id=user.user_id,
        kafka_producer=None,  # Don't publish events for sandbox
    )

    try:
        # Execute in sandbox mode (auto-rollback)
        result = await executor.execute_action(
            action=action,
            mode=ActionMode.SANDBOX,
            plan_id=None,
        )

        # Extract deltas from actual_impact
        deltas = result.get("actual_impact", {})

        return SandboxResponse(
            success=True,
            before_state=result.get("before_state", {}),
            after_state=result.get("after_state", {}),
            deltas=deltas,
            actual_impact=result.get("actual_impact", {}),
            message=result.get("message", "Sandbox execution completed"),
        )

    except ActionHandlerNotImplementedError as exc:
        # Sprint Q.12 Onda 0.4 — sandbox previously fabricated an
        # ``after_state`` from a stub. Surface 501 so the UI can show
        # "not yet wired" instead of bogus deltas.
        logger.warning(
            "Sandbox 501 — no handler for action_type=%s", exc.action_type,
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        )
    except Exception as e:
        logger.error(f"Sandbox execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sandbox execution failed: {e!s}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Camada 4 ABL — causal audit endpoint (Sprint Q.13.G)
# ═══════════════════════════════════════════════════════════════════════════════
#
# `record_causal_audit` (Q.13.D) verifies + persists a CausalChain for
# the nightly ABL feedback job. The function shipped without callsites
# because no copilot codepath today emits a structured chain. This
# endpoint exposes the helper so:
#
#   * Frontend ExplainPanel can post chains it constructs from copilot
#     responses + counterfactual queries.
#   * Integration tests can seed the ABL pipeline without touching
#     `copilot.service.process_ask`.
#   * Operators can re-feed historical chains after an outage.
#
# When the LLM evolves to emit chains directly inside `process_ask`,
# the function `record_causal_audit` stays the canonical entry — this
# endpoint will continue working, and a direct call from the service
# stays a one-liner.


@router.post(
    "/causal/audit",
    status_code=status.HTTP_201_CREATED,
)
async def post_causal_audit(
    payload: Dict[str, Any] = Body(...),
    _user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Persist a verified CausalChain for the Camada-4 ABL job.

    Body shape::

        {
          "conversation_id": "<uuid>",
          "chain": { ...CausalChain dict... },
          "kernel_delta": <float, optional>,
          "correlation_id": "<uuid, optional>"
        }

    Returns ``201`` with the staged audit message id, ``400`` when the
    payload is missing required fields or fails verification, ``500``
    when the persist step itself crashes.
    """
    from src.copilot.causal.runtime import record_causal_audit

    conversation_id_raw = payload.get("conversation_id")
    chain_dict = payload.get("chain")
    if not conversation_id_raw or not isinstance(chain_dict, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: conversation_id, chain",
        )
    try:
        conversation_id = UUID(str(conversation_id_raw))
    except (ValueError, TypeError) as exc:
        logger.debug("UUID parse error para conversation_id: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation_id: must be UUID format",
        )

    kernel_delta_raw = payload.get("kernel_delta")
    kernel_delta: Optional[float] = None
    if kernel_delta_raw is not None:
        try:
            kernel_delta = float(kernel_delta_raw)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="kernel_delta must be a number",
            )

    correlation_id_raw = payload.get("correlation_id")
    correlation_id: Optional[UUID] = None
    if correlation_id_raw is not None:
        try:
            correlation_id = UUID(str(correlation_id_raw))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="correlation_id must be a UUID",
            )

    msg = await record_causal_audit(
        session=session,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        chain_dict=chain_dict,
        kernel_delta=kernel_delta,
        correlation_id=correlation_id,
    )
    if msg is None:
        # `record_causal_audit` returns None when verify_chain_dict
        # rejects the body OR persist crashes. Map both to 400 since
        # the operator-facing remediation is the same: fix the chain
        # body and retry.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Causal chain verification failed or persist could not stage "
                "the row. Check chain shape (mechanism, claims, evidence) and "
                "the server log for the verification reason."
            ),
        )

    await session.commit()
    audit_payload = (msg.content_structured or {}).get("causal_audit") or {}
    verification = audit_payload.get("verification") or {}
    return {
        "audit_message_id": str(msg.id),
        "conversation_id": str(msg.conversation_id),
        "validation_passed": bool(msg.validation_passed),
        "verification": {
            "passed": bool(verification.get("passed", False)),
            "reasons": verification.get("reasons") or [],
        },
    }
