"""
ProdPlan ONE — COPILOT Service (façade)
=======================================

Q.66.D.2 — façade de orquestração do COPILOT. Pós Fase 7 da decomposição
o god-file de 1708L vive distribuído por 4 sub-módulos:

  * :mod:`src.copilot.intent_router` — ``detect_intent`` (fast-path).
  * :mod:`src.copilot.fact_pack_builder` — KPI snapshot, prompt
    rendering, RLM diagnostic, fast-path KPI, entity-aware facts.
  * :mod:`src.copilot.response_renderer` — ``extract_chart_blocks``,
    normalizações (actions/warnings/citations), error builders e
    validação de qualidade de explicação.
  * :mod:`src.copilot.escalation_router` — vocabulário de actions
    escaláveis (CREATE_DECISION_PR, RUN_RUNBOOK, …).

Esta façade mantém compat de imports — characterization tests em
``tests/copilot/test_copilot_service_characterization_q66_d.py`` e
``tests/copilot/test_service.py`` monkeypatcham ``build_context_facts``
e ``retrieve_rag_chunks`` e ``get_ollama_client`` em ``src.copilot.service``,
por isso os símbolos têm de estar acessíveis a este nível.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.context_builder import build_context_facts
from src.copilot.conversation_store import ConversationStore
from src.copilot.fact_pack_builder import (
    build_employee_facts as _build_employee_facts,
    build_fast_path_kpi_response,
    build_rlm_diagnostic_response,
    call_llm_for_intent,
    fetch_kpi_snapshot,
    render_prompt,
    resolve_semantic_queries,
    store_copilot_audit,
)
from src.copilot.guardrails import check_security_flag
from src.copilot.intent_router import detect_intent
from src.copilot.ollama_client import get_ollama_client
from src.copilot.rag import retrieve_rag_chunks
from src.copilot.response_renderer import (
    assemble_copilot_response,
    create_model_offline_response,
    create_security_flag_response,
    create_validation_error_response,
    extract_chart_blocks,
    validate_explanation_quality,
)
from src.copilot.schemas import CopilotAskRequest, CopilotResponse
from src.copilot.utils.redaction import (
    extract_employee_names_from_context,
    redact_response,
)
from src.shared.auth.rbac import Role
from src.shared.config import settings

logger = logging.getLogger(__name__)


class CopilotService:
    """Service para orquestração do COPILOT.

    Os helpers privados (``_detect_intent``, ``_fetch_kpi_snapshot``, …)
    são thin wrappers sobre as funções dos sub-módulos — preservados para
    backwards compat com tests que monkeypatcham via ``CopilotService.X``.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        actor_role: str,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.actor_role = actor_role
        self.has_hr_role = actor_role in (
            Role.HR_MANAGER.value, Role.ADMIN_PLATFORM.value,
        )

    # ------------------------------------------------------------------
    # Sub-module delegates — mantidos como métodos para tests que fazem
    # ``monkeypatch.setattr(CopilotService, "_fetch_kpi_snapshot", ...)``.
    # ------------------------------------------------------------------

    def _detect_intent(self, user_query: str) -> str:
        return detect_intent(user_query)

    async def _fetch_kpi_snapshot(self) -> Optional[Dict[str, Any]]:
        return await fetch_kpi_snapshot(self.session, self.tenant_id)

    def _resolve_semantic_queries(self):
        return resolve_semantic_queries()

    async def _render_prompt(
        self, user_query, context_facts, rag_chunks,
        kpi_snapshot=None, intent="generic",
    ):
        return await render_prompt(
            self.session, self.tenant_id, user_query, context_facts,
            rag_chunks, kpi_snapshot=kpi_snapshot, intent=intent,
        )

    # Pure delegates (no session) — static for monkeypatch friendliness.
    _create_security_flag_response = staticmethod(create_security_flag_response)
    _create_model_offline_response = staticmethod(create_model_offline_response)
    _create_validation_error_response = staticmethod(create_validation_error_response)
    _validate_explanation_quality = staticmethod(validate_explanation_quality)

    # ------------------------------------------------------------------
    # Fast-path / RLM diagnostic orchestration
    # ------------------------------------------------------------------

    async def _handle_fast_path_kpi(
        self,
        request: CopilotAskRequest,
        correlation_id: UUID,
        start_time: float,
    ) -> Tuple[Optional[CopilotResponse], Dict[str, Any]]:
        return await build_fast_path_kpi_response(
            self.session, self.tenant_id, request, correlation_id, start_time,
        )

    async def _handle_rlm_diagnostic(
        self,
        request: CopilotAskRequest,
        correlation_id: UUID,
        start_time: float,
    ) -> Optional[Tuple[CopilotResponse, Dict[str, Any]]]:
        """Q.31.H — corre o RLM agent para uma pergunta diagnóstica.

        Devolve ``None`` quando o agente não chega a uma resposta, para o
        chamador cair no caminho LLM normal.
        """
        # Q.55.B.2 — se a camada semântica está vazia, RLM só responderia
        # "não tenho dados" e roubava a pergunta ao caminho LLM normal.
        semantic_queries = self._resolve_semantic_queries()
        if semantic_queries is None:
            logger.info(
                "RLM: camada semântica indisponível — a cair no caminho LLM."
            )
            return None

        result = await build_rlm_diagnostic_response(
            request, semantic_queries, get_ollama_client(),
            correlation_id, start_time,
        )
        if result is None:
            return None

        response, audit_payload, llm_response_dump = result
        audit_data = await self._store_audit(
            correlation_id, audit_payload["suggestion_id"], request,
            audit_payload["prompt"], llm_response_dump, response.model_dump(),
            True, [], audit_payload["latency_ms"],
        )
        return response, audit_data

    # ------------------------------------------------------------------
    # Audit persistence (only DB write in this module)
    # ------------------------------------------------------------------

    async def _store_audit(
        self,
        correlation_id: UUID,
        suggestion_id: UUID,
        request: CopilotAskRequest,
        prompt: str,
        llm_response: Dict[str, Any],
        response_dict: Dict[str, Any],
        validation_passed: bool,
        validation_errors: List[str],
        latency_ms: int,
    ) -> Dict[str, Any]:
        return await store_copilot_audit(
            self.session,
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            actor_role=self.actor_role,
            correlation_id=correlation_id,
            suggestion_id=suggestion_id,
            request=request,
            prompt=prompt,
            llm_response=llm_response,
            response_dict=response_dict,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # process_ask — the main orchestrator
    # ------------------------------------------------------------------

    async def process_ask(
        self,
        request: CopilotAskRequest,
    ) -> Tuple[CopilotResponse, Dict[str, Any]]:
        """Processar pergunta do utilizador. Returns (CopilotResponse, audit)."""
        correlation_id = uuid4()
        start_time = time.time()
        perf_metrics: Dict[str, Any] = {k: 0 for k in (
            "intent_detection_ms", "kpi_snapshot_ms", "context_build_ms",
            "rag_retrieval_ms", "prompt_render_ms", "llm_call_ms",
            "normalization_ms", "total_ms",
        )}

        # 1. Verificar security flag
        if check_security_flag(request.user_query):
            logger.warning(
                f"SECURITY_FLAG detetado para query: {request.user_query[:100]}"
            )
            return self._create_security_flag_response(correlation_id), {}

        # 1.5. Conversation history for multi-turn context
        conversation_history: List[Dict[str, str]] = []
        if request.conversation_id:
            try:
                conversation_history = await ConversationStore.get_history(
                    self.tenant_id, request.conversation_id
                )
            except Exception as e:
                logger.warning(f"Failed to load conversation history: {e}")

        # 2. Intent
        intent_start = time.time()
        intent = self._detect_intent(request.user_query)
        perf_metrics["intent_detection_ms"] = int((time.time() - intent_start) * 1000)
        logger.info(f"Intent detetado: {intent} para query: {request.user_query[:100]}")

        # 2.5/2.6. Tentar fast-paths (KPI fast-path ou Q.31.H RLM diagnostic).
        # Cada um devolve (resp, audit) quando consegue; senão caímos para LLM.
        fast_path = None
        if intent == "kpi_current":
            fast_path = (self._handle_fast_path_kpi, "Fast path KPI")
        elif intent == "diagnostic":
            fast_path = (self._handle_rlm_diagnostic, "RLM diagnostic")
        if fast_path is not None:
            handler, label = fast_path
            try:
                hit = await handler(request, correlation_id, start_time)
                if hit is not None:
                    resp, audit = hit if isinstance(hit, tuple) else (hit, {})
                    if resp is not None:
                        perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
                        audit["perf_metrics"] = perf_metrics
                        logger.info(f"{label} usado. Total: {perf_metrics['total_ms']}ms")
                        return resp, audit
            except Exception as e:
                logger.warning(f"{label} falhou, caindo para LLM: {e}")

        # 3. KPI snapshot (para contexto LLM)
        kpi_snapshot: Optional[Dict[str, Any]] = None
        if intent == "kpi_current":
            try:
                kpi_start = time.time()
                kpi_snapshot = await self._fetch_kpi_snapshot()
                perf_metrics["kpi_snapshot_ms"] = int((time.time() - kpi_start) * 1000)
            except Exception as e:
                logger.warning(f"Erro ao buscar KPI snapshot: {e}")

        # 4. Context (reduzido para perguntas simples)
        context_start = time.time()
        context_window = request.context_window_hours
        if intent == "kpi_current" or len(request.user_query.split()) <= 5:
            context_window = min(6, context_window)

        context_facts = await build_context_facts(
            self.session,
            self.tenant_id,
            context_window,
            self.actor_role,
            kpi_snapshot=kpi_snapshot,
        )
        perf_metrics["context_build_ms"] = int((time.time() - context_start) * 1000)

        # 4.5 Entity-aware context (Q.18 fix-workforce)
        if request.entity_type == "employee" and request.entity_id is not None:
            try:
                context_facts["employee_context"] = await _build_employee_facts(
                    self.session, self.tenant_id, request.entity_id,
                )
            except Exception as e:
                logger.warning(f"Falha a construir employee_context: {e}")

        # 5. RAG (skip para kpi_current/generic)
        rag_chunks: List[Dict[str, Any]] = []
        if request.include_citations and intent not in ("kpi_current", "generic"):
            try:
                rag_start = time.time()
                top_k = 3 if len(request.user_query.split()) <= 10 else 5
                rag_chunks = await retrieve_rag_chunks(
                    self.session, self.tenant_id, request.user_query, top_k=top_k,
                )
                perf_metrics["rag_retrieval_ms"] = int((time.time() - rag_start) * 1000)
            except Exception as e:
                logger.warning(f"Erro ao recuperar RAG chunks: {e}")
                # Q.55.B.2.1 — RAG falha => rollback para a sessão ficar
                # utilizável pelos passos seguintes.
                try:
                    await self.session.rollback()
                except Exception:  # noqa: S110  Q.61.06: rollback during recovery
                    pass

        # 6. Render prompt
        prompt_start = time.time()
        limited_context = context_facts
        if intent == "kpi_current" or len(request.user_query.split()) <= 5:
            limited_context = {
                "operational_snapshot": context_facts.get("operational_snapshot", {}),
                "kpis": context_facts.get("kpis", {}),
            }
            rag_chunks = rag_chunks[:2] if len(rag_chunks) > 2 else rag_chunks

        prompt = await self._render_prompt(
            request.user_query, limited_context, rag_chunks,
            kpi_snapshot=kpi_snapshot, intent=intent,
        )
        perf_metrics["prompt_render_ms"] = int((time.time() - prompt_start) * 1000)

        prompt_size_chars = len(prompt)
        perf_metrics["prompt_size_chars"] = prompt_size_chars
        perf_metrics["prompt_size_tokens_est"] = prompt_size_chars // 4
        if prompt_size_chars > 8000:
            logger.warning(
                f"Prompt muito grande: {prompt_size_chars} chars "
                f"(~{prompt_size_chars // 4} tokens). Correlation: {correlation_id}"
            )

        # 7. Call Ollama (com fallback agentic para generic)
        model = settings.ollama_model
        ollama_client = get_ollama_client()

        try:
            llm_start = time.time()
            llm_response, tool_calls = await call_llm_for_intent(
                prompt, intent, model, ollama_client, conversation_history,
            )
            if tool_calls:
                perf_metrics["tool_calls"] = tool_calls
            perf_metrics["llm_call_ms"] = int((time.time() - llm_start) * 1000)
            if not isinstance(llm_response, dict):
                logger.error(
                    f"Ollama retornou tipo inválido: {type(llm_response)} "
                    f"- {llm_response}"
                )
                return self._create_validation_error_response(
                    correlation_id,
                    [
                        f"Resposta do LLM não é um dict: "
                        f"{type(llm_response).__name__}"
                    ],
                ), {}
        except Exception as e:
            logger.error(f"Erro ao chamar Ollama: {e}")
            return self._create_model_offline_response(correlation_id), {}

        # 8-9. Normalizar + validar + montar CopilotResponse
        # (pipeline completa em response_renderer.assemble_copilot_response —
        # cobre actions/warnings/facts/citations/charts/Pydantic build).
        suggestion_id = uuid4()
        response, validation_errors, validation_passed = assemble_copilot_response(
            llm_response,
            request_user_query=request.user_query,
            request_entity_type=request.entity_type,
            request_recommendation_origins=getattr(
                request, '_recommendation_origins', [],
            ),
            intent=intent,
            correlation_id=correlation_id,
            suggestion_id=suggestion_id,
            model=model,
            latency_ms=int((time.time() - start_time) * 1000),
        )
        if response is None:
            return self._create_validation_error_response(
                correlation_id, validation_errors,
            ), {}

        # 10-11. Redact + audit + persist conversation + final log
        response_dict = redact_response(
            response.model_dump(),
            extract_employee_names_from_context(context_facts),
            self.has_hr_role,
        )
        perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
        audit_data = await self._store_audit(
            correlation_id, suggestion_id, request, prompt, llm_response,
            response_dict, validation_passed, validation_errors,
            perf_metrics["total_ms"],
        )
        audit_data["perf_metrics"] = perf_metrics

        if request.conversation_id:
            try:
                await ConversationStore.append_turn(
                    self.tenant_id, request.conversation_id,
                    request.user_query, response.summary,
                )
            except Exception as e:
                logger.warning(f"Failed to persist conversation turn: {e}")

        _log_perf(correlation_id, intent, perf_metrics)

        try:
            return CopilotResponse(**response_dict), audit_data
        except ValidationError:
            logger.warning(
                f"Erro ao validar resposta após redaction. Correlation: {correlation_id}"
            )
            return response, audit_data


def _log_perf(
    correlation_id: UUID, intent: str, perf_metrics: Dict[str, Any],
) -> None:
    """Linha de log canónica de performance + alerta se KPI > 5s."""
    logger.info(
        f"COPILOT performance. Correlation: {correlation_id}. "
        f"Intent: {intent}. Total: {perf_metrics['total_ms']}ms. "
        f"Breakdown: intent={perf_metrics['intent_detection_ms']}ms, "
        f"context={perf_metrics['context_build_ms']}ms, "
        f"rag={perf_metrics['rag_retrieval_ms']}ms, "
        f"prompt={perf_metrics['prompt_render_ms']}ms "
        f"(size: {perf_metrics.get('prompt_size_chars', 0)} chars / "
        f"~{perf_metrics.get('prompt_size_tokens_est', 0)} tokens), "
        f"llm={perf_metrics['llm_call_ms']}ms"
    )
    if intent == "kpi_current" and perf_metrics["total_ms"] > 5000:
        logger.warning(
            f"PERFORMANCE ALERT: KPI query demorou {perf_metrics['total_ms']}ms "
            f"(threshold: 5000ms). Correlation: {correlation_id}"
        )


# ─────────────────────────────────────────────────────────────────────────
# Backwards-compat re-exports — testes externos importam estes nomes ou
# fazem ``monkeypatch.setattr("src.copilot.service.X", ...)``. Manter aqui
# para não tocar nos testes.
# ─────────────────────────────────────────────────────────────────────────

__all__ = [
    "CopilotService",
    "extract_chart_blocks",
    "build_context_facts",
    "retrieve_rag_chunks",
    "get_ollama_client",
]
