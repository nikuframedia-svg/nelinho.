"""Q.66.D.4a — sub-router: ask / recommendations / insights / daily-feedback.

Endpoints LLM-facing que pedem ao copiloto para *responder* ou para
*sugerir/explicar*. O `_run_copilot_action` (mutações reais) vive em
`actions.py`; a CRUD de conversas em `conversations.py`; health/sandbox/
rag/causal em `health.py`.

Colaboradores externos (`CopilotService`, `get_rate_limiter`,
`generate_daily_feedback`, `generate_recommendations`) são acedidos via
``src.copilot.api`` para que `patch.object(copilot_api, "<name>", ...)`
nos characterization tests da Q.66.D.1c propague para os handlers reais.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot import api as _api  # late attribute access — vê monkey-patches
from src.copilot.schemas import (
    CopilotAskRequest,
    CopilotResponse,
    DailyFeedbackResponse,
    ExplainRecommendationsRequest,
)
from src.shared.auth.jwt_handler import UserContext, get_current_user
from src.shared.database import get_session
from src.shared.time import local_today

logger = logging.getLogger(__name__)

router = APIRouter()


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
# AVISO: este cache é single-process. Em produção com --workers 2 (deploy/systemd/prodplan-api.service:26)
# dois workers têm espaço de memória independente → idempotência não é garantida entre workers.
# Fix correcto: trocar por Redis (padrão rate_limiter.py). Aceite como risco conhecido até lá.


def _idempotency_get(tenant_id: UUID, user_id: str, key: str) -> Optional[CopilotResponse]:
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
    cache_key = (str(tenant_id), str(user_id), key)
    _IDEMPOTENCY_CACHE[cache_key] = (response, time.time() + _IDEMPOTENCY_TTL_SECONDS)
    # Best-effort sweep: limit unbounded growth
    if len(_IDEMPOTENCY_CACHE) > 1000:
        now = time.time()
        for k, (_, exp) in list(_IDEMPOTENCY_CACHE.items()):
            if exp < now:
                _IDEMPOTENCY_CACHE.pop(k, None)


# ──────────────────────────────────────────────────────────────────────────
# POST /ask + /ask-dev
# ──────────────────────────────────────────────────────────────────────────


@router.post("/ask", response_model=CopilotResponse, status_code=status.HTTP_200_OK)
async def ask_copilot(
    request: CopilotAskRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
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
    rate_limiter = _api.get_rate_limiter()
    await rate_limiter.enforce_rate_limit(tenant_id, user.user_id)

    # Service
    service = _api.CopilotService(session, tenant_id, user.user_id, user.role)

    # Processar com tratamento de erros
    try:
        response, _audit_data = await service.process_ask(request)
        if request.idempotency_key:
            _idempotency_set(tenant_id, user.user_id, request.idempotency_key, response)
        return response
    except Exception as e:
        # Capturar qualquer erro não tratado e normalizar
        correlation_id = uuid4()

        logger.error(
            f"Erro inesperado ao processar pergunta do COPILOT. "
            f"Correlation: {correlation_id}. Erro: {e!s}",
            exc_info=True,
        )

        # Q.170.G — DECISÃO documentada: o envelope 200 + type=ERROR é o
        # contrato do chat (o FE mostra a badge de erro e o utilizador pode
        # retentar; um 5xx alimentaria o circuit-breaker global e bloqueava
        # o copiloto inteiro por um erro pontual). O custo era observabilidade
        # (falhas invisíveis nas métricas) — a métrica abaixo fecha isso.
        try:
            from src.shared.metrics import bump_silent_fallback
            bump_silent_fallback("copilot_ask", "unhandled_exception")
        except Exception as metric_exc:  # pragma: no cover — best-effort
            logger.debug("métrica copilot_ask falhou: %s", metric_exc)

        # Retornar resposta de erro normalizada
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


@router.post(
    "/ask-dev",
    response_model=CopilotResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(_api.dev_only)],
)
async def ask_copilot_dev(
    request: CopilotAskRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    # Valores padrão para desenvolvimento
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_user_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_role = "ADMIN"

    # Rate limiting (com valores dev)
    rate_limiter = _api.get_rate_limiter()
    await rate_limiter.enforce_rate_limit(dev_tenant_id, dev_user_id)

    # Service
    service = _api.CopilotService(session, dev_tenant_id, dev_user_id, dev_role)

    # Processar
    response, _audit_data = await service.process_ask(request)

    return response


# ──────────────────────────────────────────────────────────────────────────
# GET /daily-feedback + /daily-feedback-dev
# ──────────────────────────────────────────────────────────────────────────


@router.get("/daily-feedback", response_model=DailyFeedbackResponse)
async def get_daily_feedback(
    date_param: Optional[str] = None,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter feedback diário do COPILOT.

    Se não existir ou expirado, gera novo.
    """
    target_date = date_param or local_today().isoformat()

    # Gerar feedback (com cache interno)
    feedback = await _api.generate_daily_feedback(session, tenant_id, target_date)

    return feedback


@router.get(
    "/daily-feedback-dev",
    response_model=DailyFeedbackResponse,
    include_in_schema=False,
    dependencies=[Depends(_api.dev_only)],
)
async def get_daily_feedback_dev(
    date_param: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    target_date = date_param or local_today().isoformat()

    feedback = await _api.generate_daily_feedback(session, dev_tenant_id, target_date)

    return feedback


# ──────────────────────────────────────────────────────────────────────────
# GET /recommendations + /recommendations-dev
# ──────────────────────────────────────────────────────────────────────────


@router.get("/recommendations", response_model=List[Dict[str, Any]], tags=["COPILOT"])
async def get_recommendations(
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter recomendações geradas automaticamente baseadas em análise de dados.
    """
    try:
        recommendations = await _api.generate_recommendations(session, tenant_id)
    except Exception as e:
        logger.error("Erro ao gerar recomendações: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao gerar recomendações.",
        ) from e
    return recommendations


@router.get(
    "/recommendations-dev",
    response_model=List[Dict[str, Any]],
    tags=["COPILOT"],
    include_in_schema=False,
    dependencies=[Depends(_api.dev_only)],
)
async def get_recommendations_dev(
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    try:
        recommendations = await _api.generate_recommendations(session, dev_tenant_id)
    except Exception as e:
        logger.error("Erro ao gerar recomendações (dev): %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao gerar recomendações.",
        ) from e
    return recommendations


# ──────────────────────────────────────────────────────────────────────────
# POST /recommendations/explain + /recommendations/explain-dev
# ──────────────────────────────────────────────────────────────────────────


@router.post("/recommendations/explain", response_model=CopilotResponse, tags=["COPILOT"])
async def explain_recommendations(
    request: ExplainRecommendationsRequest,
    user: UserContext = Depends(get_current_user),
    tenant_id: UUID = Depends(_api.get_tenant_id),
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
    recommendations = request.recommendations
    user_query = request.user_query or "Explica-me estas recomendações e como implementá-las."

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
    service = _api.CopilotService(session, tenant_id, user.user_id, user.role)
    response, _ = await service.process_ask(copilot_request)

    return response


@router.post(
    "/recommendations/explain-dev",
    response_model=CopilotResponse,
    tags=["COPILOT"],
    include_in_schema=False,
    dependencies=[Depends(_api.dev_only)],
)
async def explain_recommendations_dev(
    request: ExplainRecommendationsRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Endpoint de desenvolvimento - SEM autenticação.

    Sprint Q.12 Onda 0.5: gated to non-production via ``dev_only``.
    """
    dev_tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_user_id = UUID("00000000-0000-0000-0000-000000000001")
    dev_role = "ADMIN"

    recommendations = request.recommendations
    user_query = request.user_query or "Explica-me estas recomendações e como implementá-las."

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

    copilot_request._recommendation_origins = [
        rec.get('origins', []) for rec in recommendations
    ]

    service = _api.CopilotService(session, dev_tenant_id, dev_user_id, dev_role)
    response, _ = await service.process_ask(copilot_request)

    return response


# ──────────────────────────────────────────────────────────────────────────
# GET /insights + /insights-dev
# ──────────────────────────────────────────────────────────────────────────


@router.get("/insights", response_model=Dict[str, Any], tags=["COPILOT"])
async def get_insights(
    date: Optional[str] = None,
    tenant_id: UUID = Depends(_api.get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Obter insights agregados: daily feedback + recommendations.

    Retorna timeline única com:
    - "now": alertas/insights diários (daily feedback)
    - "next": recomendações de melhoria (recommendations)
    """
    # Data alvo (hoje se não especificada)
    if date:
        target_date = date
    else:
        target_date = datetime.now(timezone.utc).date().isoformat()

    # 1. Obter daily feedback
    daily_feedback = await _api.generate_daily_feedback(session, tenant_id, target_date)
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
    recommendations = await _api.generate_recommendations(session, tenant_id)
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


@router.get(
    "/insights-dev",
    response_model=Dict[str, Any],
    tags=["COPILOT"],
    include_in_schema=False,
    dependencies=[Depends(_api.dev_only)],
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

    if date:
        target_date = date
    else:
        target_date = datetime.now(timezone.utc).date().isoformat()

    daily_feedback = await _api.generate_daily_feedback(session, dev_tenant_id, target_date)
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

    recommendations = await _api.generate_recommendations(session, dev_tenant_id)
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
