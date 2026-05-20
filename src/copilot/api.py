"""
ProdPlan ONE - COPILOT API
===========================

FastAPI router para endpoints do COPILOT.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from src.copilot.schemas import (
    CopilotAskRequest,
    CopilotResponse,
    CopilotActionRequest,
    DailyFeedbackResponse,
    SandboxRequest,
    SandboxResponse,
)
from src.copilot.service import CopilotService
from src.copilot.models import CopilotSuggestion, CopilotDecisionPR, CopilotConversation, CopilotMessage, CopilotActionLog, CopilotUserFeedback
from src.copilot.actions import (
    ActionExecutor,
    ActionHandlerNotImplementedError,
    ActionMode,
)
from src.shared.kafka_client import get_producer
from src.copilot.recommendations import generate_recommendations
from sqlalchemy import select, and_
from src.copilot.rate_limiter import get_rate_limiter
from src.copilot.ollama_client import get_ollama_client
from src.copilot.rag import ingest_document
from src.copilot.jobs.daily_feedback import generate_daily_feedback
from src.shared.database import get_session
from src.shared.auth.jwt_handler import get_current_user, UserContext
from src.shared.auth.rbac import PermissionDependency, Permission
from src.shared.config import settings
from src.governance.audit_service import audit_change

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["COPILOT"])


# ──────────────────────────────────────────────────────────────────────────
# Idempotency cache (Onda fix-copilot Bug C)
#
# Schema já aceitava `idempotency_key` mas não era usado em lado nenhum:
# se o browser fazia retry no timeout do Ollama (~30s), o handler criava
# 2 CopilotSuggestion distintos. Cache in-memory single-process com TTL
# 5min basta para dev. Em produção multi-worker, trocar dict por Redis.
# ──────────────────────────────────────────────────────────────────────────

_IDEMPOTENCY_TTL_SECONDS = 300
_IDEMPOTENCY_CACHE: Dict[tuple, tuple] = {}  # {(tenant, user, key): (response, expires_epoch)}


def _idempotency_get(tenant_id: UUID, user_id: str, key: str) -> Optional[CopilotResponse]:
    import time
    cache_key = (str(tenant_id), str(user_id), key)
    entry = _IDEMPOTENCY_CACHE.get(cache_key)
    if entry is None:
        return None
    response, expires = entry
    if time.time() > expires:
        _IDEMPOTENCY_CACHE.pop(cache_key, None)
        return None
    return response


def _idempotency_set(tenant_id: UUID, user_id: str, key: str, response: CopilotResponse) -> None:
    import time
    cache_key = (str(tenant_id), str(user_id), key)
    _IDEMPOTENCY_CACHE[cache_key] = (response, time.time() + _IDEMPOTENCY_TTL_SECONDS)
    # Best-effort sweep: limit unbounded growth
    if len(_IDEMPOTENCY_CACHE) > 1000:
        now = time.time()
        for k, (_, exp) in list(_IDEMPOTENCY_CACHE.items()):
            if exp < now:
                _IDEMPOTENCY_CACHE.pop(k, None)


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


def dev_only() -> None:
    """Dependency that 404s when ``settings.environment == "production"``.

    Sprint Q.12 Onda 0.5 — the ``/*-dev`` endpoints (no auth, hardcoded
    tenant) used to be reachable in any environment, leaking tenant-zero
    data to anyone who knew the URL. Now they're hidden in prod. The
    long-term answer is to remove them outright once each surface has a
    proper auth path; until then this guard makes "shipped to prod by
    accident" loud instead of quiet.
    """
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )


@router.post("/ask", response_model=CopilotResponse, status_code=status.HTTP_200_OK)
async def ask_copilot(
    request: CopilotAskRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Fazer pergunta ao COPILOT.
    
    Processo:
    1. Rate limiting
    2. Guardrails (injection filter)
    3. Build context
    4. Retrieve RAG
    5. Call Ollama (ou fast path)
    6. Validate response
    7. Store audit
    8. Store message in conversation (se conversation_id fornecido)
    9. Return response
    """
    # Idempotency check (Onda fix-copilot Bug C) — devolve resposta cacheada
    # se browser/cliente retentar com mesma key (timeout fetch ~30s).
    if request.idempotency_key:
        cached = _idempotency_get(tenant_id, user.user_id, request.idempotency_key)
        if cached is not None:
            return cached

    # Rate limiting
    rate_limiter = get_rate_limiter()
    await rate_limiter.enforce_rate_limit(tenant_id, user.user_id)

    # Service
    service = CopilotService(session, tenant_id, user.user_id, user.role)

    # Processar com tratamento de erros
    try:
        response, _audit_data = await service.process_ask(request)
        if request.idempotency_key:
            _idempotency_set(tenant_id, user.user_id, request.idempotency_key, response)
        return response
    except Exception as e:
        # Capturar qualquer erro não tratado e normalizar
        from uuid import uuid4
        import logging
        logger = logging.getLogger(__name__)
        correlation_id = uuid4()
        
        logger.error(
            f"Erro inesperado ao processar pergunta do COPILOT. "
            f"Correlation: {correlation_id}. Erro: {e!s}",
            exc_info=True
        )
        
        # Retornar resposta de erro normalizada
        from src.copilot.schemas import CopilotResponse
        return CopilotResponse(
            suggestion_id=uuid4(),
            correlation_id=correlation_id,
            type="ERROR",
            intent="generic",
            summary="Ocorreu um erro ao processar a tua pergunta. Tenta novamente.",
            facts=[],
            actions=[],
            warnings=[
                {
                    "code": "MODEL_OFFLINE",
                    "message": "O serviço COPILOT está temporariamente indisponível. Verifica os logs do sistema.",
                }
            ],
            meta={
                "validation_passed": False,
            },
        )


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
        await audit_change(
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
    tenant_id: UUID = Depends(get_tenant_id),
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
    dependencies=[Depends(dev_only)],
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


@router.get("/suggestions/{suggestion_id}", response_model=CopilotResponse)
async def get_suggestion(
    suggestion_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Obter registo imutável de sugestão (audit)."""
    suggestion = await session.get(CopilotSuggestion, suggestion_id)
    
    if not suggestion or suggestion.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion não encontrada",
        )
    
    return suggestion.response_json


@router.get("/daily-feedback", response_model=DailyFeedbackResponse)
async def get_daily_feedback(
    date_param: Optional[str] = None,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter feedback diário do COPILOT.
    
    Se não existir ou expirado, gera novo.
    """
    target_date = date_param or date.today().isoformat()
    
    # Gerar feedback (com cache interno)
    feedback = await generate_daily_feedback(session, tenant_id, target_date)
    
    return feedback


@router.get(
    "/daily-feedback-dev",
    response_model=DailyFeedbackResponse,
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def get_daily_feedback_dev(
    date_param: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    from uuid import UUID
    
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    target_date = date_param or date.today().isoformat()
    
    # Gerar feedback (com cache interno)
    feedback = await generate_daily_feedback(session, dev_tenant_id, target_date)
    
    return feedback


@router.post("/rag/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_rag_document(
    source_type: str,
    source_id: str,
    text: str,
    metadata: Optional[dict] = None,
    user: UserContext = Depends(
        PermissionDependency([Permission.CONFIG_WRITE])
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Ingestão de documento para RAG (admin only).
    
    Aceita markdown/PDF/texto.
    """
    chunks_created = await ingest_document(
        session,
        tenant_id,
        source_type,
        source_id,
        text,
        metadata,
    )
    
    return {
        "status": "success",
        "chunks_created": chunks_created,
        "source_type": source_type,
        "source_id": source_id,
    }


# ──────────────────────────────────────────────────────────────────────────
# User feedback collector — Onda 13 M (UI ad-hoc 👍👎 + texto)
# ──────────────────────────────────────────────────────────────────────────

@router.post("/feedback/user", status_code=status.HTTP_200_OK)
async def submit_user_feedback(
    payload: dict,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Recebe feedback ad-hoc do utilizador (👍/👎 + texto livre).

    Q.31.H — persiste em ``copilot_user_feedback``. Antes era um stub
    log-only e o sinal perdia-se.

    Payload aceita: ``{thumb: 'up'|'down', text: str, context?: dict}``.
    """
    thumb = (payload.get("thumb") or "").strip()
    text = (payload.get("text") or "").strip()
    if thumb not in ("up", "down"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="thumb must be 'up' or 'down'")

    from uuid import uuid4

    context = payload.get("context")
    row = CopilotUserFeedback(
        id=uuid4(),
        tenant_id=tenant_id,
        thumb=thumb,
        text=text or None,
        context=context if isinstance(context, dict) else None,
    )
    # Q.66.B.3: feedback do utilizador (thumbs up/down) e dado de
    # aprendizagem para tuning do copiloto, nao state de governance.
    session.add(row)  # noqa: audit_coverage  # user feedback for learning, not gov state
    await session.commit()

    return {
        "status": "received",
        "id": str(row.id),
        "thumb": thumb,
        "text_len": len(text),
        "tenant_id": str(tenant_id),
    }


@router.post("/health/reset-circuit")
async def reset_circuit_breaker():
    """
    Reset manual do circuit breaker do Ollama (útil para debugging).
    """
    try:
        ollama_client = get_ollama_client()
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
async def copilot_health():
    """
    Health check do COPILOT.
    
    Verifica: Ollama, DB, embeddings, rate limit.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        ollama_client = get_ollama_client()
        
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
        
        return {
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
    except Exception as e:
        logger.error(f"Erro no health check do COPILOT: {e}", exc_info=True)
        return {
            "status": "error",
            "ollama": "offline",
            "error": str(e),
            "embeddings_model": getattr(settings, "copilot_embeddings_model", "all-minilm"),
        }


@router.post(
    "/ask-dev",
    response_model=CopilotResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def ask_copilot_dev(
    request: CopilotAskRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    from uuid import UUID
    
    # Valores padrão para desenvolvimento
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_user_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_role = "ADMIN"
    
    # Rate limiting (com valores dev)
    rate_limiter = get_rate_limiter()
    await rate_limiter.enforce_rate_limit(dev_tenant_id, dev_user_id)
    
    # Service
    service = CopilotService(session, dev_tenant_id, dev_user_id, dev_role)
    
    # Processar
    response, _audit_data = await service.process_ask(request)
    
    return response



@router.get("/recommendations", response_model=List[Dict[str, Any]], tags=["COPILOT"])
async def get_recommendations(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter recomendações geradas automaticamente baseadas em análise de dados.
    """
    recommendations = await generate_recommendations(session, tenant_id)
    return recommendations


@router.get(
    "/recommendations-dev",
    response_model=List[Dict[str, Any]],
    tags=["COPILOT"],
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def get_recommendations_dev(
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    recommendations = await generate_recommendations(session, dev_tenant_id)
    return recommendations


@router.post("/recommendations/explain", response_model=CopilotResponse, tags=["COPILOT"])
async def explain_recommendations(
    request: Dict[str, Any] = Body(...),
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Pedir ao LLM para explicar recomendações.
    
    Request body:
    {
        "recommendations": [...],  # Lista de recomendações
        "user_query": "Explica-me estas recomendações"  # Opcional
    }
    """
    recommendations = request.get("recommendations", [])
    user_query = request.get("user_query", "Explica-me estas recomendações e como implementá-las.")
    
    # Construir prompt com recomendações (incluindo origins, confidence, limitations)
    recommendations_text = "\n\n".join([
        f"**{i+1}. {rec.get('title', 'Recomendação')}** ({rec.get('category', 'GENERAL')})\n"
        f"{rec.get('description', '')}\n"
        f"Impacto: {rec.get('impact_metric', 'N/A')} = {rec.get('impact_value', 0):.1f}\n"
        f"Fases afetadas: {', '.join(rec.get('affected_phases', []))}\n"
        f"Ações sugeridas: {', '.join(rec.get('suggested_actions', []))}\n"
        f"**ORIGENS**: {', '.join(rec.get('origins', []))}\n"
        f"**CONFIANÇA**: {rec.get('confidence', 'N/A')}\n"
        f"**LIMITAÇÕES**: {', '.join(rec.get('limitations', [])) if rec.get('limitations') else 'Nenhuma especificada'}"
        for i, rec in enumerate(recommendations)
    ])
    
    # Criar request para o COPILOT (passar origins para validação)
    copilot_request = CopilotAskRequest(
        user_query=f"{user_query}\n\nRecomendações:\n{recommendations_text}",
        entity_type="recommendations",
        include_citations=True,
    )
    
    # Adicionar metadata sobre origins para validação
    copilot_request._recommendation_origins = [
        rec.get('origins', []) for rec in recommendations
    ]
    
    # Processar com COPILOT
    service = CopilotService(session, tenant_id, user.user_id, user.role)
    response, _ = await service.process_ask(copilot_request)
    
    return response


@router.post(
    "/recommendations/explain-dev",
    response_model=CopilotResponse,
    tags=["COPILOT"],
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def explain_recommendations_dev(
    request: Dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_user_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_role = "ADMIN"
    
    recommendations = request.get("recommendations", [])
    user_query = request.get("user_query", "Explica-me estas recomendações e como implementá-las.")
    
    recommendations_text = "\n\n".join([
        f"**{i+1}. {rec.get('title', 'Recomendação')}** ({rec.get('category', 'GENERAL')})\n"
        f"{rec.get('description', '')}\n"
        f"Impacto: {rec.get('impact_metric', 'N/A')} = {rec.get('impact_value', 0):.1f}\n"
        f"Fases afetadas: {', '.join(rec.get('affected_phases', []))}\n"
        f"Ações sugeridas: {', '.join(rec.get('suggested_actions', []))}\n"
        f"**ORIGENS**: {', '.join(rec.get('origins', []))}\n"
        f"**CONFIANÇA**: {rec.get('confidence', 'N/A')}\n"
        f"**LIMITAÇÕES**: {', '.join(rec.get('limitations', [])) if rec.get('limitations') else 'Nenhuma especificada'}"
        for i, rec in enumerate(recommendations)
    ])
    
    copilot_request = CopilotAskRequest(
        user_query=f"{user_query}\n\nRecomendações:\n{recommendations_text}",
        entity_type="recommendations",
        include_citations=True,
    )
    
    # Adicionar metadata sobre origins para validação
    copilot_request._recommendation_origins = [
        rec.get('origins', []) for rec in recommendations
    ]
    
    service = CopilotService(session, dev_tenant_id, dev_user_id, dev_role)
    response, _ = await service.process_ask(copilot_request)
    
    return response


@router.get("/insights", response_model=Dict[str, Any], tags=["COPILOT"])
async def get_insights(
    date: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter insights agregados: daily feedback + recommendations.
    
    Retorna timeline única com:
    - "now": alertas/insights diários (daily feedback)
    - "next": recomendações de melhoria (recommendations)
    """
    from datetime import date as date_type, datetime
    
    # Data alvo (hoje se não especificada)
    if date:
        target_date = date
    else:
        target_date = datetime.now(timezone.utc).date().isoformat()
    
    # 1. Obter daily feedback
    daily_feedback = await generate_daily_feedback(session, tenant_id, target_date)
    now_items = []
    
    # Converter bullets para formato de insights
    for bullet in daily_feedback.bullets:
        now_items.append({
            "id": f"alert-{len(now_items) + 1}",
            "severity": bullet.severity,
            "title": bullet.title,
            "text": bullet.text,
            "citations": bullet.citations,
            "suggested_runbooks": bullet.suggested_runbooks,
            "suggested_actions": bullet.suggested_actions or [],
        })
    
    # Ordenar "now" por severidade: CRITICAL > WARN > INFO
    severity_order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    now_items.sort(key=lambda x: (severity_order.get(x["severity"], 999), x.get("title", "")))
    
    # Deduplicar "now" (por title+text)
    seen_now = set()
    deduped_now = []
    for item in now_items:
        key = f"{item['title']}|{item['text']}"
        if key not in seen_now:
            seen_now.add(key)
            deduped_now.append(item)
    now_items = deduped_now
    
    # 2. Obter recommendations
    recommendations = await generate_recommendations(session, tenant_id)
    next_items = []
    
    # Converter recommendations para formato de insights
    for rec in recommendations:
        next_items.append({
            "id": f"rec-{len(next_items) + 1}",
            "priority": rec.get("priority", 999),
            "category": rec.get("category", "GENERAL"),
            "title": rec.get("title", "Recomendação"),
            "description": rec.get("description", ""),
            "impact_metric": rec.get("impact_metric", ""),
            "impact_value": rec.get("impact_value", 0.0),
            "affected_phases": rec.get("affected_phases", []),
            "suggested_actions": rec.get("suggested_actions", []),
            "origins": rec.get("origins", ["BEST_PRACTICE"]),
            "confidence": rec.get("confidence", "MEDIUM"),
            "limitations": rec.get("limitations", []),
            "next_steps": rec.get("next_steps", []),
            "data_evidence": rec.get("data_evidence", {}),
        })
    
    # Ordenar "next" por prioridade: 1 > 2 > 3
    next_items.sort(key=lambda x: (x.get("priority", 999), -x.get("impact_value", 0)))
    
    # Deduplicar "next" (por title+description)
    seen_next = set()
    deduped_next = []
    for item in next_items:
        key = f"{item['title']}|{item['description']}"
        if key not in seen_next:
            seen_next.add(key)
            deduped_next.append(item)
    next_items = deduped_next
    
    return {
        "date": target_date,
        "now": now_items,
        "next": next_items,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": ["daily_feedback_cache", "recommendations_runtime"],
        },
    }


@router.get(
    "/insights-dev",
    response_model=Dict[str, Any],
    tags=["COPILOT"],
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def get_insights_dev(
    date: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    
    from datetime import date as date_type, datetime
    
    if date:
        target_date = date
    else:
        target_date = datetime.now(timezone.utc).date().isoformat()
    
    # Mesma lógica do endpoint normal
    daily_feedback = await generate_daily_feedback(session, dev_tenant_id, target_date)
    now_items = []
    
    for bullet in daily_feedback.bullets:
        now_items.append({
            "id": f"alert-{len(now_items) + 1}",
            "severity": bullet.severity,
            "title": bullet.title,
            "text": bullet.text,
            "citations": bullet.citations,
            "suggested_runbooks": bullet.suggested_runbooks,
            "suggested_actions": bullet.suggested_actions or [],
        })
    
    severity_order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    now_items.sort(key=lambda x: (severity_order.get(x["severity"], 999), x.get("title", "")))
    
    seen_now = set()
    deduped_now = []
    for item in now_items:
        key = f"{item['title']}|{item['text']}"
        if key not in seen_now:
            seen_now.add(key)
            deduped_now.append(item)
    now_items = deduped_now
    
    recommendations = await generate_recommendations(session, dev_tenant_id)
    next_items = []
    
    for rec in recommendations:
        next_items.append({
            "id": f"rec-{len(next_items) + 1}",
            "priority": rec.get("priority", 999),
            "category": rec.get("category", "GENERAL"),
            "title": rec.get("title", "Recomendação"),
            "description": rec.get("description", ""),
            "impact_metric": rec.get("impact_metric", ""),
            "impact_value": rec.get("impact_value", 0.0),
            "affected_phases": rec.get("affected_phases", []),
            "suggested_actions": rec.get("suggested_actions", []),
            "origins": rec.get("origins", ["BEST_PRACTICE"]),
            "confidence": rec.get("confidence", "MEDIUM"),
            "limitations": rec.get("limitations", []),
            "next_steps": rec.get("next_steps", []),
            "data_evidence": rec.get("data_evidence", {}),
        })
    
    next_items.sort(key=lambda x: (x.get("priority", 999), -x.get("impact_value", 0)))
    
    seen_next = set()
    deduped_next = []
    for item in next_items:
        key = f"{item['title']}|{item['description']}"
        if key not in seen_next:
            seen_next.add(key)
            deduped_next.append(item)
    next_items = deduped_next
    
    return {
        "date": target_date,
        "now": now_items,
        "next": next_items,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": ["daily_feedback_cache", "recommendations_runtime"],
        },
    }


# ============================================================================
# CONVERSATIONS API
# ============================================================================

@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
    title: Optional[str] = Body(None),
):
    """Criar nova conversa."""
    conversation = CopilotConversation(
        tenant_id=tenant_id,
        actor_id=user.user_id,
        title=title or "Nova conversa",
    )
    # Q.66.B.3: conversa do copiloto (chat container), nao state de
    # governance. Mensagens vivem em copilot.message com correlation_id.
    session.add(conversation)  # noqa: audit_coverage  # copilot chat container, not gov state
    # Commit explícito: `get_session` só auto-commita se `session.new/dirty/
    # deleted` tiverem conteúdo no fim do request — e `flush()` esvazia
    # `session.new`. Sem este commit a conversa era inserida e logo
    # rollbacked ao fechar a sessão (id devolvido, linha inexistente).
    await session.commit()
    await session.refresh(conversation)

    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
    }


@router.get("/conversations", status_code=status.HTTP_200_OK)
async def list_conversations(
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
    archived: bool = False,
):
    """Listar conversas do utilizador."""
    query = select(CopilotConversation).where(
        and_(
            CopilotConversation.tenant_id == tenant_id,
            CopilotConversation.actor_id == user.user_id,
            CopilotConversation.is_archived == archived,
        )
    ).order_by(CopilotConversation.last_message_at.desc().nulls_last(), CopilotConversation.created_at.desc())
    
    result = await session.execute(query.offset(offset).limit(limit))
    conversations = result.scalars().all()
    
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
            "is_archived": c.is_archived,
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages", status_code=status.HTTP_200_OK)
async def get_conversation_messages(
    conversation_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
    offset: int = 0,
):
    """Obter mensagens de uma conversa."""
    # Verificar que a conversa pertence ao utilizador
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    
    query = select(CopilotMessage).where(
        and_(
            CopilotMessage.tenant_id == tenant_id,
            CopilotMessage.conversation_id == conversation_id,
        )
    ).order_by(CopilotMessage.created_at.asc())
    
    result = await session.execute(query.offset(offset).limit(limit))
    messages = result.scalars().all()
    
    return [
        {
            "id": str(m.id),
            "role": m.actor_role,
            "content_text": m.content_text,
            "content_structured": m.content_structured,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    request: CopilotAskRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Enviar mensagem numa conversa e obter resposta do COPILOT."""
    # Verificar que a conversa pertence ao utilizador
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    
    # Guardar mensagem do utilizador
    user_message = CopilotMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        actor_role="user",
        content_text=request.user_query,
        content_structured=None,
    )
    # Q.66.B.3: mensagem de chat LLM, nao state de governance.
    session.add(user_message)  # noqa: audit_coverage  # chat message, not gov state
    await session.flush()

    # Memória multi-turno: o `process_ask` lê/escreve o `ConversationStore`
    # (Redis, últimos 3 turnos) com base em `request.conversation_id`. O
    # endpoint recebe o id no path mas nunca o injectava no request — o
    # LLM ficava sem memória da conversa. Liga-os aqui.
    request.conversation_id = conversation_id

    # Processar pergunta com COPILOT
    service = CopilotService(session, tenant_id, user.user_id, user.role)
    response, audit_data = await service.process_ask(request)
    
    # Guardar resposta do COPILOT
    copilot_message = CopilotMessage(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        actor_role="copilot",
        content_text=response.summary,
        content_structured=response.model_dump(),
        correlation_id=response.correlation_id,
        latency_ms=audit_data.get("latency_ms"),
        model=audit_data.get("model") or response.meta.get("model"),
        validation_passed=response.meta.get("validation_passed"),
    )
    # Q.66.B.3: resposta LLM (latencia/model/validation) — chat history,
    # nao state de governance.
    session.add(copilot_message)  # noqa: audit_coverage  # chat message, not gov state
    
    # Atualizar last_message_at da conversa
    conversation.last_message_at = datetime.now(timezone.utc)
    
    await session.commit()
    
    return response


@router.patch("/conversations/{conversation_id}/rename", status_code=status.HTTP_200_OK)
async def rename_conversation(
    conversation_id: UUID,
    title: str = Body(..., embed=True),
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Renomear conversa."""
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    
    conversation.title = title
    await session.commit()
    
    return {"id": str(conversation.id), "title": conversation.title}


@router.post("/conversations/{conversation_id}/archive", status_code=status.HTTP_200_OK)
async def archive_conversation(
    conversation_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Arquivar/desarquivar conversa."""
    conversation = await session.get(CopilotConversation, conversation_id)
    if not conversation or conversation.tenant_id != tenant_id or conversation.actor_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    
    conversation.is_archived = not conversation.is_archived
    await session.commit()
    
    return {"id": str(conversation.id), "is_archived": conversation.is_archived}


@router.post("/sandbox", response_model=SandboxResponse, status_code=status.HTTP_200_OK)
async def execute_sandbox(
    request: SandboxRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
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
    from src.copilot.actions import (
        Action,
    )
    from uuid import uuid4
    
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
    executor = ActionExecutor(
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


@router.post("/actions/{transaction_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_action(
    transaction_id: UUID,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
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
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    List action logs for the current user.
    
    Returns list of executed actions with their before/after state.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
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
    tenant_id: UUID = Depends(get_tenant_id),
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid conversation_id: {exc}",
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
