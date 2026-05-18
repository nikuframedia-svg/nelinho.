"""
ProdPlan ONE - COPILOT Service
================================

Service layer para orquestração do COPILOT.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.models import CopilotSuggestion
from src.copilot.schemas import CopilotResponse, CopilotAskRequest
from pydantic import ValidationError
from src.copilot.context_builder import build_context_facts
from src.copilot.conversation_store import ConversationStore
from src.copilot.rag import retrieve_rag_chunks
from src.copilot.ollama_client import get_ollama_client
from src.copilot.tool_executor import ToolExecutor
from src.copilot.guardrails import (
    check_security_flag,
    validate_response_structure,
)
from src.copilot.utils.hashing import sha256_hash
from src.copilot.utils.redaction import redact_response, extract_employee_names_from_context
from src.shared.config import settings
from src.shared.auth.rbac import Role

logger = logging.getLogger(__name__)


def _render_production_fact_pack(production: Dict[str, Any]) -> str:
    """Q.34.A.4 — bloco de texto com o resumo de produção real, para o
    prompt. Diz ao LLM o que citar (`table:plan.production_orders`).
    Devolve "" quando não há dados."""
    if not production or not production.get("has_data"):
        return ""
    qh = production.get("query_hash", "")
    in_prod = production.get("orders_in_production", 0)
    delivered = production.get("orders_delivered_or_stored", 0)
    lines = [
        f"### PRODUÇÃO (fonte: table:plan.production_orders; query_hash:{qh})",
        f"- Ordens: {production.get('orders_total', 0)} totais "
        f"({in_prod} em produção no chão de fábrica, "
        f"{delivered} já entregues/armazenadas/embaladas)",
        # Q.35.3.1 — o `status` vem todo IN_PROGRESS do sync; o WIP real é
        # contado pela fase actual. NÃO chamar "Entregue" um gargalo.
        f"- WIP real (ordens em fases de produção) = {in_prod}. As fases "
        "administrativas (Entregue/Armazem/Embalado) não são produção.",
    ]
    wip = production.get("wip_by_phase") or []
    if wip:
        lines.append("- WIP por fase de produção: " + "; ".join(
            f"{w['phase']} {w['orders']}" for w in wip[:8]))
    by_type = production.get("wip_by_product_type") or {}
    if by_type:
        lines.append("- Por tipo de produto: " + "; ".join(
            f"{k} {v}" for k, v in by_type.items()))
    transp = production.get("orders_by_transport_date") or []
    if transp:
        lines.append("- Ordens por data de transporte: " + "; ".join(
            f"{t['date']}={t['orders']}" for t in transp[:8]))
    oldest = production.get("oldest_in_progress_created")
    if oldest:
        lines.append(f"- Ordem em curso mais antiga (criada): {oldest}")
    lines.append(
        'Citar com: source_type="db", '
        f'ref="table:plan.production_orders;query_hash:{qh}".')
    return "\n".join(lines) + "\n\n"


def _render_quality_fact_pack(quality: Dict[str, Any]) -> str:
    """Q.34.A.4 — bloco de texto com o resumo de qualidade real
    (`quality.rework_entry`). Só para o reader DB (`db.rework_entry`); a
    camada antiga não tem o mesmo contrato. Devolve "" quando não há dados."""
    if not quality or not quality.get("has_data"):
        return ""
    if quality.get("source") != "db.rework_entry":
        return ""
    qh = quality.get("query_hash", "")
    lines = [
        f"### QUALIDADE (fonte: table:quality.rework_entry; query_hash:{qh})",
        f"- Erros/retrabalho: {quality.get('total_errors', 0)} registados "
        f"({quality.get('unresolved_errors', 0)} por resolver)",
    ]
    by_phase = quality.get("errors_by_phase") or []
    if by_phase:
        lines.append("- Erros por fase: " + "; ".join(
            f"{e['phase']} {e['errors']}" for e in by_phase[:8]))
    by_rc = quality.get("errors_by_root_cause") or {}
    if by_rc:
        lines.append("- Por causa raiz: " + "; ".join(
            f"{k} {v}" for k, v in by_rc.items()))
    # Q.35.3.2 — custo/horas só existem em poucos registos. NÃO apresentar
    # a soma como "custo total" — dizer explicitamente a cobertura, senão
    # o copiloto reporta €610 como se fosse o custo dos 3659 erros.
    total_errors = quality.get("total_errors", 0)
    cost = quality.get("cost_estimate_eur_known")
    cost_n = quality.get("cost_known_count", 0)
    if cost and cost_n:
        lines.append(
            f"- Custo de retrabalho conhecido: €{cost:,.0f} — mas só "
            f"{cost_n} de {total_errors} erros têm custo registado no ERP. "
            "NÃO apresentar este valor como o custo total da qualidade.")
    hours = quality.get("hours_lost_known")
    hours_n = quality.get("hours_known_count", 0)
    if hours and hours_n:
        lines.append(
            f"- Horas perdidas conhecidas: {hours:.0f}h — só em {hours_n} "
            f"de {total_errors} registos.")
    lines.append(
        'Citar com: source_type="db", '
        f'ref="table:quality.rework_entry;query_hash:{qh}".')
    return "\n".join(lines) + "\n\n"


class CopilotService:
    """Service para orquestração do COPILOT."""
    
    def __init__(self, session: AsyncSession, tenant_id: UUID, actor_id: UUID, actor_role: str):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.actor_role = actor_role
        self.has_hr_role = actor_role in (Role.HR_MANAGER.value, Role.ADMIN_PLATFORM.value)

    async def _load_conversation_history(
        self, conversation_id: UUID,
    ) -> List[Dict[str, str]]:
        """Histórico multi-turno: Redis (rápido) com fallback durável ao Postgres.

        Q.32.B.1 — o Redis (`ConversationStore`) é cache efémero: 3 turnos,
        TTL 30 min. Quando expira — ou o Redis está em baixo — o histórico
        desaparecia por completo. Agora reconstruímos do `copilot_message`,
        que é a fonte durável de verdade.
        """
        try:
            history = await ConversationStore.get_history(
                self.tenant_id, conversation_id,
            )
            if history:
                return history
        except Exception as e:
            logger.warning(f"Redis conversation history indisponível: {e}")

        # Fallback durável — Postgres `copilot_message`.
        try:
            from sqlalchemy import select

            from src.copilot.models import CopilotMessage

            stmt = (
                select(CopilotMessage)
                .where(
                    CopilotMessage.tenant_id == self.tenant_id,
                    CopilotMessage.conversation_id == conversation_id,
                )
                .order_by(CopilotMessage.created_at.desc())
                .limit(6)  # MAX_TURNS (3) × 2 mensagens por turno
            )
            rows = list((await self.session.execute(stmt)).scalars().all())
            rows.reverse()  # ordem cronológica para o LLM
            return [
                {
                    "role": "assistant" if m.actor_role == "copilot" else "user",
                    "content": m.content_text or "",
                }
                for m in rows
            ]
        except Exception as e:
            logger.warning(f"Postgres conversation history indisponível: {e}")
            return []

    async def _build_learned_signal(self, *, window_days: int = 90) -> str:
        """Bloco "sinal aprendido" — feedback 👍/👎 agregado, para o prompt.

        Q.32.C.2 — é assim que o copiloto melhora ao longo do tempo sem
        retrain: vê a taxa de aprovação histórica das suas respostas
        (`copilot_user_feedback`, agregado por `FeedbackSignalsService`) e
        calibra o rigor. Determinístico, derivado de dados. Devolve "" se
        ainda não há sinal significativo.
        """
        try:
            from src.copilot.feedback_signals import (
                MIN_SAMPLES_FOR_SIGNAL,
                FeedbackSignalsService,
            )

            svc = FeedbackSignalsService(self.session, self.tenant_id)
            by_intent = await svc.by_intent(window_days=window_days)
        except Exception as e:
            logger.warning(f"learned signal indisponível: {e}")
            # Q.35.2 — mesmo motivo do rollback na recolha de RAG: não
            # deixar uma query falhada poisonar a transação para o
            # `_store_audit` que corre a seguir.
            try:
                await self.session.rollback()
            except Exception:
                pass
            return ""

        total_up = sum(fb.up for fb in by_intent.values())
        total_down = sum(fb.down for fb in by_intent.values())
        total = total_up + total_down
        if total < MIN_SAMPLES_FOR_SIGNAL:
            return ""

        overall_pct = round(100.0 * total_up / total, 1)
        lines = [
            f"## SINAL APRENDIDO (feedback dos utilizadores — últimos {window_days} dias)",
            "",
            "Os utilizadores avaliaram as tuas respostas anteriores. Usa isto "
            "para calibrar o rigor — NÃO menciones estes números na resposta.",
            f"- Globalmente: 👍 {overall_pct}% ({total} avaliações)",
        ]
        significant = [fb for fb in by_intent.values() if fb.is_significant]
        if significant:
            parts = []
            for fb in sorted(significant, key=lambda f: f.up_pct):
                note = (
                    " — abaixo da média, sê mais rigoroso e cita melhor"
                    if fb.up_pct < 60 else ""
                )
                parts.append(f"{fb.intent} 👍 {fb.up_pct}% (N={fb.total}){note}")
            lines.append("- Por tema: " + "; ".join(parts))
        return "\n".join(lines)

    def _build_tool_auth_headers(self) -> Dict[str, str]:
        """Auth headers para as chamadas HTTP dos tools de volta à app.

        Q.33.B.2 — quase todos os endpoints exigem um tenant
        (`require_tenant_header`). Um access token assinado resolve o
        tenant em qualquer ambiente (o JWT é lido primeiro); os headers
        `X-*` são o fallback dev/test. Best-effort: se o minting falhar,
        ainda enviamos os `X-*` para o dev continuar a funcionar.
        """
        headers: Dict[str, str] = {
            "X-Tenant-Id": str(self.tenant_id),
            "X-User-Id": str(self.actor_id),
        }
        try:
            from src.shared.auth.jwt_handler import create_access_token

            headers["Authorization"] = "Bearer " + create_access_token(
                user_id=self.actor_id,
                tenant_id=self.tenant_id,
                role=self.actor_role,
            )
        except Exception as exc:
            logger.warning(f"tool auth token minting falhou: {exc}")
        return headers

    async def process_ask(
        self,
        request: CopilotAskRequest,
    ) -> Tuple[CopilotResponse, Dict[str, Any]]:
        """
        Processar pergunta do utilizador.
        
        Returns:
            (CopilotResponse, audit_data)
        """
        correlation_id = uuid4()
        start_time = time.time()
        perf_metrics = {
            "intent_detection_ms": 0,
            "kpi_snapshot_ms": 0,
            "context_build_ms": 0,
            "rag_retrieval_ms": 0,
            "prompt_render_ms": 0,
            "llm_call_ms": 0,
            "normalization_ms": 0,
            "total_ms": 0,
        }
        
        # 1. Verificar security flag
        if check_security_flag(request.user_query):
            logger.warning(f"SECURITY_FLAG detetado para query: {request.user_query[:100]}")
            return self._create_security_flag_response(correlation_id), {}

        # 1.5. Load conversation history for multi-turn context.
        # Q.32.B.1 — Redis com fallback durável ao Postgres copilot_message.
        conversation_history: List[Dict[str, str]] = []
        if request.conversation_id:
            conversation_history = await self._load_conversation_history(
                request.conversation_id
            )
        
        # 2. Detectar intent
        intent_start = time.time()
        intent = self._detect_intent(request.user_query)
        perf_metrics["intent_detection_ms"] = int((time.time() - intent_start) * 1000)
        logger.info(f"Intent detetado: {intent} para query: {request.user_query[:100]}")
        
        # 2.5. FAST PATH: Se intent é kpi_current, responder diretamente sem LLM
        if intent == "kpi_current":
            try:
                fast_response, fast_audit = await self._handle_fast_path_kpi(request, correlation_id, start_time)
                if fast_response:
                    perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
                    fast_audit["perf_metrics"] = perf_metrics
                    logger.info(
                        f"Fast path usado para KPI query. Latency: {fast_audit.get('latency_ms', 0)}ms. "
                        f"Metrics: {perf_metrics}"
                    )
                    return fast_response, fast_audit
            except Exception as e:
                logger.warning(f"Erro no fast path, caindo para LLM: {e}")
                # Continuar para LLM path se fast path falhar
        
        # 2.55. FAST PATH: saudações / smalltalk → resposta fixa, zero LLM.
        if intent == "smalltalk":
            try:
                fast_response, fast_audit = self._handle_fast_path_smalltalk(
                    request, correlation_id, start_time
                )
                if fast_response:
                    perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
                    fast_audit["perf_metrics"] = perf_metrics
                    logger.info(
                        f"Fast path smalltalk usado. Latency: {perf_metrics['total_ms']}ms"
                    )
                    return fast_response, fast_audit
            except Exception as e:
                logger.warning(f"Erro no fast path smalltalk, caindo para LLM: {e}")

        # 2.6. DIAGNOSTIC — duas camadas, com fallback em cascata:
        #   (a) Q.33.A.2 — dispatch directo aos 3 detectores de causa raiz
        #       (`investigate_quality_drop` / `find_common_cause` /
        #       `what_changed`). Só engata quando a capability está wired
        #       para o tenant; corre o detector in-process e compõe a
        #       resposta. É o caminho preferido — dá uma causa raiz real.
        #   (b) Q.31.H — o RLM agent corre think→query→observe sobre o
        #       estado da fábrica (sub-queries tipadas, sem dump de 200k
        #       tokens). Fallback quando (a) não devolve nada.
        # Ambos isolados: se levantam ou devolvem None, cai no caminho LLM
        # normal abaixo. Os outros intents nunca passam por aqui.
        if intent == "diagnostic":
            try:
                diag_result = await self._handle_diagnostic_dispatch(
                    request, correlation_id, start_time
                )
                if diag_result is not None:
                    diag_response, diag_audit = diag_result
                    perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
                    diag_audit["perf_metrics"] = perf_metrics
                    logger.info(
                        f"Diagnostic dispatch usado. Latency: {perf_metrics['total_ms']}ms"
                    )
                    return diag_response, diag_audit
            except Exception as e:
                logger.warning(f"Diagnostic dispatch falhou, a tentar RLM: {e}")

            try:
                rlm_result = await self._handle_rlm_diagnostic(
                    request, correlation_id, start_time
                )
                if rlm_result is not None:
                    rlm_response, rlm_audit = rlm_result
                    perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
                    rlm_audit["perf_metrics"] = perf_metrics
                    logger.info(
                        f"RLM diagnostic usado. Latency: {perf_metrics['total_ms']}ms"
                    )
                    return rlm_response, rlm_audit
            except Exception as e:
                logger.warning(f"RLM diagnostic falhou, caindo para LLM: {e}")
                # Continuar para o caminho LLM normal.

        # 3. Se intent é kpi_current, buscar snapshot de KPIs (para contexto do LLM)
        kpi_snapshot = None
        if intent == "kpi_current":
            try:
                kpi_start = time.time()
                kpi_snapshot = await self._fetch_kpi_snapshot()
                perf_metrics["kpi_snapshot_ms"] = int((time.time() - kpi_start) * 1000)
            except Exception as e:
                logger.warning(f"Erro ao buscar KPI snapshot: {e}")
        
        # 4. Build context (reduzir tamanho para perguntas simples)
        context_start = time.time()
        # Reduzir context_window para perguntas simples (menos dados = prompt menor = mais rápido)
        context_window = request.context_window_hours
        if intent == "kpi_current" or len(request.user_query.split()) <= 5:
            # Perguntas curtas ou KPIs: usar apenas últimas 6 horas
            context_window = min(6, context_window)
        
        context_facts = await build_context_facts(
            self.session,
            self.tenant_id,
            context_window,
            self.actor_role,
            kpi_snapshot=kpi_snapshot,
        )
        perf_metrics["context_build_ms"] = int((time.time() - context_start) * 1000)

        # 4.5 Entity-aware context (Q.18 fix-workforce):
        # Quando o frontend envia entity_type="employee" + entity_id, injectar
        # quality_score + nível derivado + skills na context_facts para o LLM
        # responder perguntas como "que barcos posso atribuir ao {nome}?".
        if request.entity_type == "employee" and request.entity_id is not None:
            try:
                context_facts["employee_context"] = await _build_employee_facts(
                    self.session, self.tenant_id, request.entity_id
                )
            except Exception as e:
                logger.warning(f"Falha a construir employee_context: {e}")

        # 5. Retrieve RAG (apenas se necessário - reduzir ainda mais)
        rag_chunks = []
        if request.include_citations and intent not in ("kpi_current", "generic"):
            # Só usar RAG para perguntas complexas, não para KPIs simples
            try:
                rag_start = time.time()
                # Reduzir top_k para perguntas simples
                top_k = 3 if len(request.user_query.split()) <= 10 else 5
                rag_chunks = await retrieve_rag_chunks(
                    self.session,
                    self.tenant_id,
                    request.user_query,
                    top_k=top_k,  # Reduzido para 3-5 dependendo da complexidade
                )
                perf_metrics["rag_retrieval_ms"] = int((time.time() - rag_start) * 1000)
            except Exception as e:
                logger.warning(f"Erro ao recuperar RAG chunks: {e}")
                # Q.35.2 — uma query falhada (ex.: `copilot_rag_chunk` não
                # existe em dev — pgvector é skipped) deixa a transação
                # asyncpg ABORTADA. Sem rollback, TODA a query seguinte na
                # mesma sessão (learned signal, `_store_audit`) rebenta com
                # InFailedSQLTransactionError → a resposta inteira vira
                # ERROR/MODEL_OFFLINE falso. Limpar a transação aqui.
                try:
                    await self.session.rollback()
                except Exception:
                    pass
        
        # 6. Render prompt (com fact pack se kpi_snapshot disponível)
        # Limitar contexto para perguntas simples (reduzir prompt size = resposta mais rápida)
        prompt_start = time.time()
        # Para perguntas curtas, limitar contexto a apenas KPIs essenciais
        limited_context = context_facts
        if intent == "kpi_current" or len(request.user_query.split()) <= 5:
            # Manter apenas KPIs e métricas essenciais, remover detalhes operacionais.
            # Q.34.A.4 — manter também `production`/`quality`: são os resumos
            # de dados reais (production_orders, rework_entry) que o fact pack
            # usa para responder com números concretos a perguntas curtas.
            limited_context = {
                "operational_snapshot": context_facts.get("operational_snapshot", {}),
                "kpis": context_facts.get("kpis", {}),
                "production": context_facts.get("production", {}),
                "quality": context_facts.get("quality", {}),
            }
            # Limitar RAG chunks também
            rag_chunks = rag_chunks[:2] if len(rag_chunks) > 2 else rag_chunks
        
        # Q.32.C.2 — sinal aprendido: feedback 👍/👎 histórico injectado no
        # prompt para o copiloto calibrar o rigor ao longo do tempo.
        learned_signal = await self._build_learned_signal()

        prompt = await self._render_prompt(
            request.user_query,
            limited_context,
            rag_chunks,
            kpi_snapshot=kpi_snapshot,
            intent=intent,
            learned_signal=learned_signal,
        )
        perf_metrics["prompt_render_ms"] = int((time.time() - prompt_start) * 1000)
        
        # Log prompt size para monitorização
        prompt_size_chars = len(prompt)
        prompt_size_tokens = prompt_size_chars // 4  # Estimativa: 1 token ≈ 4 chars
        perf_metrics["prompt_size_chars"] = prompt_size_chars
        perf_metrics["prompt_size_tokens_est"] = prompt_size_tokens
        if prompt_size_chars > 8000:  # ~2000 tokens
            logger.warning(f"Prompt muito grande: {prompt_size_chars} chars (~{prompt_size_tokens} tokens). Correlation: {correlation_id}")
        
        # 7. Call Ollama
        model = settings.ollama_model
        ollama_client = get_ollama_client()

        # Q.37.E — `tool_log` é sempre definido (vazio no caminho sem
        # loop agêntico) para a injecção de citations mais abaixo não
        # rebentar com NameError.
        tool_log: List[Dict[str, Any]] = []
        try:
            llm_start = time.time()
            # For generic intents with tool registry loaded, use agentic tool loop
            # so the LLM can call factory data tools (backlog, WIP, bottlenecks, etc.)
            # Q.33.B.2 — gated behind `copilot_agentic_tools_enabled` (off by
            # default). The registry now loads in-process (`/v1/tools` works),
            # but the loop's final-answer step doesn't yet emit a schema-valid
            # CopilotResponse — running it regressed generic answers to
            # VALIDATION_FAILED. The loop's own integration is a separate
            # sub-sprint; until then generic intents take the plain-chat path.
            from src.copilot.tool_registry import get_tool_registry_sync
            registry = get_tool_registry_sync()
            if (
                settings.copilot_agentic_tools_enabled
                and intent == "generic"
                and registry
                and registry.tools
            ):
                # Pass auth so the tool's HTTP call back into this app
                # resolves the tenant instead of 401-ing. A minted JWT
                # works in every environment; the X-* headers are the
                # dev/test fallback path.
                executor = ToolExecutor(
                    registry, auth_headers=self._build_tool_auth_headers(),
                )
                # Q.37.E — `final_system_prompt` é o system_prompt.md
                # original; o passo de síntese final do loop usa-o (em
                # vez do TOOL_SYSTEM_PROMPT) para emitir um
                # CopilotResponse que passa a validação do schema.
                final_system_prompt = await self._render_system_prompt()
                llm_response, tool_log = await executor.execute_with_tools(
                    user_query=prompt,
                    model=model,
                    history=conversation_history or None,
                    format="json",
                    final_system_prompt=final_system_prompt,
                )
                perf_metrics["tool_calls"] = len(tool_log)
            else:
                llm_response = await ollama_client.chat(
                    prompt,
                    model,
                    format="json",
                    history=conversation_history or None,
                )
            perf_metrics["llm_call_ms"] = int((time.time() - llm_start) * 1000)
            # Garantir que é um dict
            if not isinstance(llm_response, dict):
                logger.error(f"Ollama retornou tipo inválido: {type(llm_response)} - {llm_response}")
                return self._create_validation_error_response(
                    correlation_id,
                    [f"Resposta do LLM não é um dict: {type(llm_response).__name__}"],
                ), {}
        except Exception as e:
            logger.error(f"Erro ao chamar Ollama: {e}")
            return self._create_model_offline_response(correlation_id), {}
        
        # 6. Normalizar actions ANTES da validação (o LLM pode retornar formatos incorretos)
        actions_normalized = []
        actions_raw = llm_response.get("actions", [])
        
        # Garantir que actions é uma lista
        if not isinstance(actions_raw, list):
            logger.warning(f"actions não é uma lista: {type(actions_raw).__name__}, convertendo...")
            actions_raw = []
        
        # Q.35.5.1 — só estes 4 action_type têm handler real no endpoint
        # /api/copilot/action; e RUN_RUNBOOK só executa runbooks que
        # carregam mesmo. O LLM por vezes inventa acções (RUN_RUNBOOK de
        # um runbook inexistente, action_types fora do enum) — propor um
        # botão que rebenta ao clicar é pior que não o propor.
        from src.copilot.runbook_executor import loadable_runbooks

        valid_action_types = {
            "CREATE_DECISION_PR", "DRY_RUN", "OPEN_ENTITY", "RUN_RUNBOOK",
        }
        real_runbooks = set(loadable_runbooks())

        for action in actions_raw:
            # Se for string, tentar converter para dict
            if isinstance(action, str):
                logger.warning(f"Ação é string: '{action}', ignorando...")
                continue

            # Se for dict, normalizar
            if isinstance(action, dict):
                # Se tiver "type" mas não "action_type", converter
                if "type" in action and "action_type" not in action:
                    action["action_type"] = action.pop("type")
                # Garantir que tem "label" (obrigatório)
                if "label" not in action:
                    action["label"] = action.get("action_type", "Ação")
                action_type = action.get("action_type")
                if not action_type:
                    continue
                # Q.35.5.1 — descartar acções sem handler real.
                if action_type not in valid_action_types:
                    logger.warning(
                        f"Q.35.5.1 — action_type sem handler descartado: "
                        f"{action_type!r}"
                    )
                    continue
                if action_type == "RUN_RUNBOOK":
                    rb_id = (action.get("payload") or {}).get("runbook_id")
                    if rb_id not in real_runbooks:
                        logger.warning(
                            f"Q.35.5.1 — RUN_RUNBOOK descartado: runbook "
                            f"{rb_id!r} não existe (reais: {sorted(real_runbooks)})"
                        )
                        continue
                actions_normalized.append(action)
            else:
                logger.warning(f"Ação tem tipo inválido: {type(action).__name__}, ignorando...")
        
        # Substituir actions normalizadas no llm_response
        llm_response["actions"] = actions_normalized
        
        # 6.5. Normalizar warnings ANTES de normalizar facts (para verificar INSUFFICIENT_EVIDENCE)
        warnings_raw = llm_response.get("warnings", [])
        warnings_normalized = []
        if isinstance(warnings_raw, list):
            for warning in warnings_raw:
                if isinstance(warning, dict):
                    # Validar warning code
                    code = warning.get("code", "")
                    valid_codes = ("INSUFFICIENT_EVIDENCE", "SECURITY_FLAG", "LOW_TRUST_INDEX", "MODEL_OFFLINE", "VALIDATION_FAILED", "EXPLANATION_TOO_SHALLOW", "EXPLANATION_MISSING_CAUSAL_LINK", "EXPLANATION_FALSE_CAUSALITY")
                    if code not in valid_codes:
                        # Q.35.2.2 — código de warning inventado pelo LLM:
                        # DESCARTAR o warning. Antes convertia-se em
                        # VALIDATION_FAILED, o que punha um badge "Validação
                        # falhou" assustador numa resposta `ANSWER` que afinal
                        # passou — desonesto e confundia o utilizador.
                        logger.info(
                            f"Warning code inválido descartado: {warning.get('code')}"
                        )
                        continue

                    # Garantir que tem message
                    message = warning.get("message", "")
                    if not message:
                        message = code
                    
                    warnings_normalized.append({
                        "code": code,
                        "message": message,
                    })
        llm_response["warnings"] = warnings_normalized
        
        # Verificar se há INSUFFICIENT_EVIDENCE
        has_insufficient_evidence = any(
            w.get("code") == "INSUFFICIENT_EVIDENCE" for w in warnings_normalized
        )
        
        # 6.6. Normalizar citations ANTES da validação (para evitar erros de source_type inválido)
        facts_raw = llm_response.get("facts", [])
        if isinstance(facts_raw, list):
            normalized_facts = []
            for fact in facts_raw:
                if isinstance(fact, dict):
                    # Normalizar citations: corrigir source_type inválido
                    citations = fact.get("citations", [])
                    normalized_citations = []
                    for citation in citations:
                        if isinstance(citation, dict):
                            source_type = citation.get("source_type", "db")
                            # Se source_type é inválido (ex: 'BEST_PRACTICE'), converter para válido
                            valid_source_types = ["db", "rag", "event", "calculation", "recommendation", "system_data"]
                            if source_type not in valid_source_types:
                                # Q.35.2.1 — `BEST_PRACTICE` mapeia bem para
                                # `recommendation`; tudo o resto cai em
                                # `system_data` (a marca honesta de "gerado
                                # pelo sistema/copiloto"). Antes mapeava-se
                                # `HEURISTIC`→`rag`, o que mentia sobre a
                                # origem (sugeria recuperação da base de
                                # conhecimento quando não houve nenhuma).
                                orig = str(source_type).upper()
                                if "PRACTICE" in orig:
                                    source_type = "recommendation"
                                else:
                                    source_type = "system_data"
                                logger.warning(
                                    f"Citation com source_type inválido '{citation.get('source_type')}' "
                                    f"convertido para '{source_type}'. Correlation: {correlation_id}"
                                )
                            # Garantir que todos os campos obrigatórios existem com valores válidos
                            ref = citation.get("ref", "")
                            label = citation.get("label", "")
                            # Se ref ou label estão vazios, tentar gerar a partir de outros campos
                            if not ref:
                                if citation.get("source_id"):
                                    ref = f"{source_type}:{citation.get('source_id')}"
                                elif citation.get("chunk_id"):
                                    ref = f"{source_type}:chunk:{citation.get('chunk_id')}"
                                elif citation.get("table"):
                                    ref = f"{source_type}:table:{citation.get('table')}"
                                else:
                                    ref = f"{source_type}:unknown"
                            
                            if not label:
                                label = (
                                    citation.get("title") or 
                                    citation.get("source_id") or 
                                    citation.get("chunk_id") or 
                                    citation.get("table") or 
                                    f"Fonte {source_type}"
                                )
                            
                            # Validar e normalizar valores numéricos
                            try:
                                confidence = float(citation.get("confidence", 0.8))
                                confidence = max(0.0, min(1.0, confidence))
                            except (ValueError, TypeError):
                                confidence = 0.8
                            
                            try:
                                trust_index = float(citation.get("trust_index", 0.75))
                                trust_index = max(0.0, min(1.0, trust_index))
                            except (ValueError, TypeError):
                                trust_index = 0.75
                            
                            # Garantir que ref e label não excedem tamanhos máximos
                            ref = ref[:500]  # max_length=500
                            label = label[:200]  # max_length=200
                            
                            normalized_citation = {
                                "source_type": source_type,
                                "ref": ref,
                                "label": label,
                                "confidence": confidence,
                                "trust_index": trust_index,
                            }
                            normalized_citations.append(normalized_citation)
                    # Garantir que fact tem text (obrigatório) e citations
                    fact_text = fact.get("text", "")
                    if not fact_text:
                        # Se não há text, tentar gerar a partir de outros campos
                        fact_text = fact.get("description") or fact.get("summary") or fact.get("content") or ""
                    
                    if not fact_text:
                        # Se ainda não há text, pular este fact
                        logger.warning(f"Fact sem texto, ignorando. Correlation: {correlation_id}")
                        continue
                    
                    # Q.35.2.1 — evidence enforcement honesto. Um facto sem
                    # citação real:
                    #  - intents de dados (kpi/quality/plan/diagnostic): é um
                    #    número/afirmação sem fonte → DESCARTAR o facto e
                    #    sinalizar INSUFFICIENT_EVIDENCE. Antes fabricava-se
                    #    uma citação "system:copilot:ungrounded" só para o
                    #    facto passar na validação — o copiloto mostrava um
                    #    número não verificado como se fosse facto.
                    #  - generic: é uma afirmação conversacional do próprio
                    #    copiloto (ex.: auto-descrição) → manter, com a marca
                    #    honesta "afirmação do COPILOT, sem fonte de dados".
                    if not normalized_citations and not has_insufficient_evidence:
                        if intent in ("kpi_current", "quality_summary", "plan_summary", "diagnostic"):
                            logger.info(
                                f"Fact sem citation descartado (intent={intent}): "
                                f"'{fact_text[:80]}'"
                            )
                            warnings_list = llm_response.get("warnings", [])
                            if not any(w.get("code") == "INSUFFICIENT_EVIDENCE" for w in warnings_list):
                                warnings_list.append({
                                    "code": "INSUFFICIENT_EVIDENCE",
                                    "message": "Algumas afirmações não tinham fonte de dados verificável e foram omitidas.",
                                })
                                llm_response["warnings"] = warnings_list
                            continue  # não adiciona o facto sem fonte
                        else:
                            # generic — afirmação do próprio copiloto.
                            normalized_citations = [{
                                "source_type": "system_data",
                                "ref": "system:copilot:generated",
                                "label": "Afirmação do COPILOT (sem fonte de dados)",
                                "confidence": 0.5,
                                "trust_index": 0.5,
                            }]

                    fact_normalized = {
                        "text": fact_text,
                        "citations": normalized_citations,
                    }
                    normalized_facts.append(fact_normalized)
                elif isinstance(fact, str):
                    # Q.35.2.1 — facto string (sem citação possível). Mesmo
                    # critério do ramo dict: nos intents de dados é
                    # descartado (sem fonte → não se mostra); no generic é
                    # uma afirmação do copiloto, mantida com marca honesta.
                    # NUNCA `citations: []` — o schema `Fact` exige ≥1.
                    if intent in ("kpi_current", "quality_summary", "plan_summary", "diagnostic"):
                        logger.info(
                            f"Fact string sem fonte descartado (intent={intent})"
                        )
                        warnings_list = llm_response.get("warnings", [])
                        if not any(w.get("code") == "INSUFFICIENT_EVIDENCE" for w in warnings_list):
                            warnings_list.append({
                                "code": "INSUFFICIENT_EVIDENCE",
                                "message": "Algumas afirmações não tinham fonte de dados verificável e foram omitidas.",
                            })
                            llm_response["warnings"] = warnings_list
                    else:
                        normalized_facts.append({
                            "text": fact,
                            "citations": [{
                                "source_type": "system_data",
                                "ref": "system:copilot:generated",
                                "label": "Afirmação do COPILOT (sem fonte de dados)",
                                "confidence": 0.5,
                                "trust_index": 0.5,
                            }],
                        })
            llm_response["facts"] = normalized_facts
        
        # 7. Validate response (agora com actions e citations já normalizadas)
        validation_passed, validation_errors = validate_response_structure(llm_response)
        
        # 7.1. Validação adicional: qualidade da explicação (para recomendações)
        if "recommendations" in request.user_query.lower() or request.entity_type == "recommendations":
            # Obter origins das recomendações (se disponível)
            recommendation_origins = getattr(request, '_recommendation_origins', [])
            explanation_quality_errors = self._validate_explanation_quality(
                llm_response, 
                request.user_query,
                recommendation_origins=recommendation_origins
            )
            if explanation_quality_errors:
                validation_errors.extend(explanation_quality_errors)
                validation_passed = False
        
        if not validation_passed:
            logger.error(f"Validação falhou: {validation_errors}")
            logger.debug(f"LLM response que falhou validação: {llm_response}")
            # Criar resposta de erro com mais detalhes
            return self._create_validation_error_response(
                correlation_id,
                validation_errors,
            ), {}
        
        # 8. Construir CopilotResponse (facts já estão normalizadas no passo 6.5)
        suggestion_id = uuid4()

        # Facts já estão normalizadas no passo 6.6
        facts_normalized = llm_response.get("facts", [])

        # Warnings já estão normalizados no passo 6.5
        warnings_normalized = llm_response.get("warnings", [])

        # Q.37.E — injecção determinística de citations das tool calls.
        # Cada entrada do `tool_log` (loop agêntico) gera uma citation
        # `source_type="calculation"`, `ref="tool:<id>;params_hash:<...>"`.
        # O hash dos params é determinístico → a mesma tool call produz
        # sempre a mesma citation (auditável, reproduzível). As citations
        # são acrescentadas a cada fact, dando proveniência aos números
        # que vieram das ferramentas.
        if tool_log:
            from src.copilot.utils.citations import create_tool_citation

            tool_citations = []
            seen_refs = set()
            for entry in tool_log:
                citation = create_tool_citation(
                    tool_id=entry.get("tool_id", "unknown"),
                    params=entry.get("params", {}),
                )
                if citation["ref"] not in seen_refs:
                    seen_refs.add(citation["ref"])
                    tool_citations.append(citation)

            for fact in facts_normalized:
                if not isinstance(fact, dict):
                    continue
                existing = fact.get("citations") or []
                existing_refs = {
                    c.get("ref") for c in existing if isinstance(c, dict)
                }
                for tc in tool_citations:
                    if tc["ref"] not in existing_refs:
                        existing.append(dict(tc))
                fact["citations"] = existing
        
        # Garantir que meta é dict
        meta_raw = llm_response.get("meta", {})
        meta_normalized = {
            "model": model,
            "tokens": meta_raw.get("tokens", 0) if isinstance(meta_raw, dict) else 0,
            "latency_ms": int((time.time() - start_time) * 1000),
            "validation_passed": validation_passed,
        }
        
        # Validar campos obrigatórios antes de criar CopilotResponse
        response_type = llm_response.get("type", "ANSWER")
        if response_type not in ("ANSWER", "RUNBOOK_RESULT", "PROPOSAL", "ERROR"):
            logger.warning(f"Tipo inválido: {response_type}, usando ANSWER")
            response_type = "ANSWER"
        
        response_intent = llm_response.get("intent", "generic")
        # Q.35.1.3 — tem de ser igual ao Literal de `CopilotResponse.intent`
        # (schemas.py) e à lista do system prompt §3. Antes faltava
        # `diagnostic` aqui → uma resposta diagnóstica perdia o intent
        # (reescrito para "generic" em silêncio).
        valid_intents = (
            "explain_oee", "explain_plan_change", "quality_summary",
            "data_integrity", "diagnostic", "generic",
        )
        if response_intent not in valid_intents:
            logger.warning(f"Intent inválido: {response_intent}, usando generic")
            response_intent = "generic"
        
        response_summary = str(llm_response.get("summary", "")) if llm_response.get("summary") else ""
        if not response_summary:
            # Se não há summary, tentar gerar a partir dos facts
            if facts_normalized:
                response_summary = facts_normalized[0].get("text", "")[:500] if facts_normalized else "Resposta do COPILOT"
            else:
                response_summary = "Resposta do COPILOT"
        
        # Warnings já estão validados e normalizados no passo 6.5
        
        # Tentar criar CopilotResponse, capturando ValidationError do Pydantic
        try:
            response = CopilotResponse(
                suggestion_id=suggestion_id,
                correlation_id=correlation_id,
                type=response_type,
                intent=response_intent,
                summary=response_summary,
                facts=facts_normalized,
                actions=actions_normalized,  # Já normalizadas no passo 6
                warnings=warnings_normalized,
                meta=meta_normalized,
            )
        except ValidationError as e:
            # Capturar erro de validação do Pydantic e normalizar
            validation_errors_detailed = []
            for error in e.errors():
                field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
                error_msg = error.get("msg", "Validation error")
                error_input = error.get("input", "")
                validation_errors_detailed.append(f"{field_path}: {error_msg} (input: {str(error_input)[:100]})")
            
            logger.error(
                f"Pydantic ValidationError ao criar CopilotResponse. "
                f"Correlation: {correlation_id}. Erros: {validation_errors_detailed}"
            )
            logger.error("Dados que causaram erro:")
            logger.error(f"  type: {response_type} (valid: ANSWER, RUNBOOK_RESULT, PROPOSAL, ERROR)")
            logger.error(f"  intent: {response_intent} (valid: explain_oee, explain_plan_change, quality_summary, data_integrity, diagnostic, generic)")
            logger.error(f"  summary length: {len(response_summary)} (must be 1-500)")
            logger.error(f"  facts count: {len(facts_normalized)}")
            logger.error(f"  actions count: {len(actions_normalized)}")
            logger.error(f"  warnings count: {len(warnings_normalized)}")
            
            # Validar cada fact individualmente
            for i, fact in enumerate(facts_normalized[:3]):  # Apenas primeiros 3
                if isinstance(fact, dict):
                    fact_text = fact.get("text", "")
                    citations = fact.get("citations", [])
                    logger.error(f"  Fact {i}: text_len={len(fact_text)}, citations_count={len(citations)}")
                    if citations:
                        for j, cit in enumerate(citations[:2]):  # Apenas primeiras 2
                            if isinstance(cit, dict):
                                logger.error(f"    Citation {j}: {json.dumps(cit, default=str)[:200]}")
            
            # Validar cada warning individualmente
            for i, warning in enumerate(warnings_normalized):
                if isinstance(warning, dict):
                    logger.error(f"  Warning {i}: {json.dumps(warning, default=str)}")
            
            logger.debug(f"LLM response completo: {json.dumps(llm_response, indent=2, default=str)}")
            
            # Retornar resposta de erro normalizada
            return self._create_validation_error_response(
                correlation_id,
                validation_errors_detailed,
            ), {}
        
        # 8. Redact se necessário
        employee_names = extract_employee_names_from_context(context_facts)
        response_dict = response.model_dump()
        response_dict = redact_response(response_dict, employee_names, self.has_hr_role)
        
        # 9. Store audit
        perf_metrics["total_ms"] = int((time.time() - start_time) * 1000)
        audit_data = await self._store_audit(
            correlation_id,
            suggestion_id,
            request,
            prompt,
            llm_response,
            response_dict,
            validation_passed,
            validation_errors,
            perf_metrics["total_ms"],
        )
        audit_data["perf_metrics"] = perf_metrics

        # Persist conversation turn for multi-turn context
        if request.conversation_id:
            try:
                await ConversationStore.append_turn(
                    self.tenant_id,
                    request.conversation_id,
                    request.user_query,
                    response_summary,
                )
            except Exception as e:
                logger.warning(f"Failed to persist conversation turn: {e}")

        # Log performance com detalhes de prompt size
        logger.info(
            f"COPILOT performance. Correlation: {correlation_id}. "
            f"Intent: {intent}. Total: {perf_metrics['total_ms']}ms. "
            f"Breakdown: intent={perf_metrics['intent_detection_ms']}ms, "
            f"context={perf_metrics['context_build_ms']}ms, "
            f"rag={perf_metrics['rag_retrieval_ms']}ms, "
            f"prompt={perf_metrics['prompt_render_ms']}ms "
            f"(size: {perf_metrics.get('prompt_size_chars', 0)} chars / ~{perf_metrics.get('prompt_size_tokens_est', 0)} tokens), "
            f"llm={perf_metrics['llm_call_ms']}ms"
        )
        
        # Alertar se p95 > 5s para intents simples
        if intent == "kpi_current" and perf_metrics["total_ms"] > 5000:
            logger.warning(
                f"PERFORMANCE ALERT: KPI query demorou {perf_metrics['total_ms']}ms "
                f"(threshold: 5000ms). Correlation: {correlation_id}"
            )
        
        # 10. Retornar resposta (já redigida)
        try:
            return CopilotResponse(**response_dict), audit_data
        except ValidationError:
            # Se redaction causar erro, retornar sem redaction
            logger.warning(f"Erro ao validar resposta após redaction. Correlation: {correlation_id}")
            return response, audit_data
    
    def _detect_intent(self, user_query: str) -> str:
        """
        Detetar intent da pergunta do utilizador.

        Sprint Q.15.0 — added "diagnostic" intent for causal questions
        (porque caiu, porque atrasou, o que mudou, investigar). When
        diagnostic, the service tries tool-calling first
        (`investigate_quality_drop` / `find_common_cause` / `what_changed`)
        and falls back to free-form LLM with an explicit "improvising"
        warning when no diagnostic capability is Wired for the tenant.

        Returns:
            "kpi_current", "quality_summary", "plan_summary", "hr_summary",
            "diagnostic", or "generic"
        """
        query_lower = user_query.lower().strip()

        # Smalltalk / saudações — resposta fixa, sem LLM. Avaliado primeiro:
        # uma saudação curta nunca é diagnóstico nem pergunta de KPI. Match
        # exacto sobre a query limpa de pontuação, por isso "ola" entra mas
        # "ola, qual o OEE?" não — não rouba perguntas reais.
        smalltalk_triggers = {
            "ola", "olá", "oi", "bom dia", "boa tarde", "boa noite",
            "obrigado", "obrigada", "tudo bem", "como estas", "como estás",
            "bom trabalho", "adeus", "ate logo", "até logo", "hello", "hi",
        }
        if query_lower.strip(" !?.,") in smalltalk_triggers:
            return "smalltalk"

        # Sprint Q.15.0 — Diagnostic intent: causal / "why" questions.
        # Checked BEFORE kpi_current because "porque caiu o OEE?"
        # contains "oee" but is fundamentally a diagnostic question, not
        # a fact lookup. The keyword list maps to the v2.2 prompt's
        # §10 ERRO-TREE / Reichenbach / Mill's vocabulary.
        diagnostic_triggers = (
            "porque ", "porquê", "por que ", "investigar", "investiga",
            "o que mudou", "que mudou", "what changed",
            "causa", "raiz", "diagnosticar", "diagnostico", "diagnóstico",
        )
        diagnostic_kpi_drop = (
            "caiu", "desceu", "baixou", "subiu", "aumentou", "atrasou",
            "atrasaram", "drift", "spike",
        )
        if any(trigger in query_lower for trigger in diagnostic_triggers):
            return "diagnostic"
        # "Porque is implicit" patterns: "throughput desceu" / "OEE caiu"
        # treat as diagnostic when paired with a drop verb + KPI noun.
        kpi_nouns = ("oee", "fpy", "rework", "throughput", "qualidade",
                     "lead time", "tempo", "barcos")
        if any(verb in query_lower for verb in diagnostic_kpi_drop):
            if any(noun in query_lower for noun in kpi_nouns):
                return "diagnostic"

        # Fast detection: perguntas muito curtas sobre KPIs devem ser kpi_current.
        # Q.35.2.3 — só dispara com um NOME de métrica real. Antes a lista
        # tinha "quanto" e "qual o/é": "Quantos erros de qualidade tivemos?"
        # contém "quanto" → caía no fast-path de KPI (intent errado,
        # explain_oee) em vez de ser uma pergunta de qualidade. "throughput"
        # fica na lista — é nome de métrica, não apanha perguntas de qualidade.
        query_words = query_lower.split()
        if len(query_words) <= 5:
            kpi_keywords_short = [
                "oee", "fpy", "rework", "availability", "performance",
                "throughput",
            ]
            if any(kw in query_lower for kw in kpi_keywords_short):
                return "kpi_current"
        
        # KPI current: perguntas sobre KPIs atuais
        kpi_keywords = ["oee", "fpy", "rework", "availability", "performance", "quality"]
        kpi_question_patterns = ["qual é", "qual o", "quanto é", "atual", "current", "agora"]
        
        has_kpi_keyword = any(keyword in query_lower for keyword in kpi_keywords)
        has_kpi_question = any(pattern in query_lower for pattern in kpi_question_patterns)
        
        if has_kpi_keyword or (has_kpi_question and any(kw in query_lower for kw in ["oee", "fpy", "rework", "taxa", "rate", "percentagem", "%"])):
            return "kpi_current"
        
        # Quality summary
        if any(word in query_lower for word in ["qualidade", "quality", "erros", "errors", "defeitos", "defects"]):
            if any(word in query_lower for word in ["resumo", "summary", "overview", "visão"]):
                return "quality_summary"
        
        # Plan summary
        if any(word in query_lower for word in ["plano", "plan", "planeamento", "scheduling", "agendamento"]):
            if any(word in query_lower for word in ["resumo", "summary", "overview", "visão"]):
                return "plan_summary"
        
        # HR summary
        if any(word in query_lower for word in ["hr", "recursos humanos", "funcionários", "employees", "alocações", "allocations"]):
            if any(word in query_lower for word in ["resumo", "summary", "overview", "visão"]):
                return "hr_summary"
        
        return "generic"
    
    async def _fetch_kpi_snapshot(self) -> Optional[Dict[str, Any]]:
        """Compute the KPI snapshot for ``self.tenant_id``.

        Sprint Q.12 Onda 0.5 — was an in-process HTTP roundtrip to
        ``/v1/profit/kpis/snapshot-dev`` (the dev endpoint, hardcoded in
        prod paths). That had two problems: (1) the dev endpoint returns
        404 in production once ``settings.debug`` is off, silently
        nulling the KPI fact pack; (2) the round-trip wasted a connection
        and bypassed our own session/transaction. We now call
        :func:`calculate_kpis` directly so the snapshot is real, scoped
        to the actual tenant, and free.
        """
        try:
            from src.profit.api.kpis import calculate_kpis

            kpis = await calculate_kpis(self.session, self.tenant_id)
            # ``calculate_kpis`` returns a dict of KPIMetric pydantic
            # models; the prompt builder expects plain dicts (so the
            # JSON dump in service.py:832 doesn't choke).
            return {
                key: (
                    value.model_dump()
                    if hasattr(value, "model_dump") else value
                )
                for key, value in kpis.items()
            }
        except Exception as e:
            logger.warning(f"Erro ao buscar KPI snapshot: {e}")
            return None
    
    async def _handle_fast_path_kpi(
        self,
        request: CopilotAskRequest,
        correlation_id: UUID,
        start_time: float,
    ) -> Tuple[Optional[CopilotResponse], Dict[str, Any]]:
        """
        Fast path para perguntas simples de KPIs (sem LLM).
        
        Responde diretamente com dados do snapshot, em < 500ms.
        """
        try:
            # Buscar snapshot
            kpi_snapshot = await self._fetch_kpi_snapshot()
            if not kpi_snapshot:
                return None, {}  # Fallback para LLM
            
            query_lower = request.user_query.lower()
            suggestion_id = uuid4()
            
            # Detectar qual KPI está a ser perguntado
            facts = []
            summary_parts = []
            
            from src.copilot.utils.citations import create_system_data_citation
            
            # Mapear perguntas para KPIs
            kpi_mappings = {
                "oee": ("oee", "OEE", "Overall Equipment Effectiveness"),
                "availability": ("availability", "Disponibilidade", "Availability"),
                "performance": ("performance", "Performance", "Performance"),
                "fpy": ("quality_fpy", "FPY", "First Pass Yield"),
                "quality": ("quality_fpy", "FPY", "First Pass Yield"),
                "rework": ("rework_rate", "Taxa de Retrabalho", "Rework Rate"),
                "retrabalho": ("rework_rate", "Taxa de Retrabalho", "Rework Rate"),
                "orders": ("orders_total", "Ordens", "Orders"),
                "ordens": ("orders_total", "Ordens", "Orders"),
            }
            
            # Detectar KPI específico na pergunta
            detected_kpi = None
            for keyword, (kpi_key, kpi_label_pt, kpi_label_en) in kpi_mappings.items():
                if keyword in query_lower:
                    detected_kpi = (kpi_key, kpi_label_pt, kpi_label_en)
                    break
            
            # Se não detectou KPI específico, retornar todos os principais
            if not detected_kpi:
                # Resposta genérica com todos os KPIs principais
                main_kpis = ["oee", "availability", "performance", "quality_fpy", "rework_rate"]
                for kpi_key in main_kpis:
                    kpi_data = kpi_snapshot.get(kpi_key, {})
                    if isinstance(kpi_data, dict):
                        value = kpi_data.get("value")
                        if value is not None:
                            kpi_label = {
                                "oee": "OEE",
                                "availability": "Disponibilidade",
                                "performance": "Performance",
                                "quality_fpy": "FPY",
                                "rework_rate": "Taxa de Retrabalho",
                            }.get(kpi_key, kpi_key.upper())
                            
                            fact_text = f"{kpi_label}: {value:.2f}%"
                            citation = create_system_data_citation(
                                data_source="kpi_snapshot",
                                data_id=kpi_key,
                                label=f"KPI {kpi_label}",
                                confidence=0.95,
                                trust_index=0.90,
                            )
                            facts.append({
                                "text": fact_text,
                                "citations": [citation],
                            })
                            summary_parts.append(fact_text)
            else:
                # Resposta específica para um KPI
                kpi_key, kpi_label_pt, kpi_label_en = detected_kpi
                kpi_data = kpi_snapshot.get(kpi_key, {})
                
                if isinstance(kpi_data, dict):
                    value = kpi_data.get("value")
                    reason = kpi_data.get("reason")
                    
                    if value is not None:
                        fact_text = f"{kpi_label_pt}: {value:.2f}%"
                        citation = create_system_data_citation(
                            data_source="kpi_snapshot",
                            data_id=kpi_key,
                            label=f"KPI {kpi_label_pt}",
                            confidence=0.95,
                            trust_index=0.90,
                        )
                        facts.append({
                            "text": fact_text,
                            "citations": [citation],
                        })
                        summary_parts.append(fact_text)
                    elif reason:
                        fact_text = f"{kpi_label_pt}: Não disponível ({reason})"
                        facts.append({
                            "text": fact_text,
                            "citations": [],
                        })
                        summary_parts.append(fact_text)
            
            if not facts:
                return None, {}  # Sem dados, fallback para LLM
            
            # Construir resposta
            summary = ". ".join(summary_parts) if summary_parts else "KPIs atuais"
            latency_ms = int((time.time() - start_time) * 1000)
            
            response = CopilotResponse(
                suggestion_id=suggestion_id,
                correlation_id=correlation_id,
                type="ANSWER",
                intent="explain_oee",  # Usar intent padrão
                summary=summary,
                facts=facts,
                actions=[],
                warnings=[],
                meta={
                    "model": "fast_path",
                    "tokens": 0,
                    "latency_ms": latency_ms,
                    "validation_passed": True,
                    "fast_path": True,
                },
            )
            
            # Audit data mínimo
            audit_data = {
                "latency_ms": latency_ms,
                "fast_path": True,
                "intent": "kpi_current",
            }
            
            logger.info(f"Fast path KPI: {len(facts)} facts, {latency_ms}ms")
            return response, audit_data
            
        except Exception as e:
            logger.error(f"Erro no fast path KPI: {e}", exc_info=True)
            return None, {}  # Fallback para LLM

    def _handle_fast_path_smalltalk(
        self,
        request: CopilotAskRequest,
        correlation_id: UUID,
        start_time: float,
    ) -> Tuple[Optional[CopilotResponse], Dict[str, Any]]:
        """Fast path para saudações / smalltalk — resposta fixa, sem LLM.

        Uma saudação não precisa do modelo: responde em <50ms em vez dos
        ~22s de uma geração JSON completa. Espelha _handle_fast_path_kpi.
        """
        try:
            from src.copilot.utils.citations import create_system_data_citation

            latency_ms = int((time.time() - start_time) * 1000)
            summary = (
                "Olá! Sou o copiloto de produção da NELO. Em que te posso "
                "ajudar — KPIs, plano, qualidade ou atribuições?"
            )
            citation = create_system_data_citation(
                data_source="copilot",
                data_id="greeting",
                label="Copiloto de produção NELO",
                confidence=1.0,
                trust_index=1.0,
            )
            response = CopilotResponse(
                suggestion_id=uuid4(),
                correlation_id=correlation_id,
                type="ANSWER",
                intent="generic",
                summary=summary,
                facts=[{"text": summary, "citations": [citation]}],
                actions=[],
                warnings=[],
                meta={
                    "model": "fast_path",
                    "tokens": 0,
                    "latency_ms": latency_ms,
                    "validation_passed": True,
                    "fast_path": True,
                },
            )
            audit_data = {
                "latency_ms": latency_ms,
                "fast_path": True,
                "intent": "smalltalk",
            }
            logger.info(f"Fast path smalltalk: {latency_ms}ms")
            return response, audit_data
        except Exception as e:
            logger.error(f"Erro no fast path smalltalk: {e}", exc_info=True)
            return None, {}  # Fallback para LLM

    @staticmethod
    def _hypothesis_to_dict(hypothesis: Any) -> Optional[Dict[str, Any]]:
        """Serializa uma `Hypothesis` dos detectores para dict JSON-safe."""
        if hypothesis is None:
            return None
        ci: Optional[List[float]] = None
        try:
            low, high = hypothesis.credible_interval()
            ci = [round(float(low), 3), round(float(high), 3)]
        except Exception:
            ci = None
        return {
            "type": hypothesis.type,
            "entity": hypothesis.entity,
            "confidence": round(float(hypothesis.confidence), 3),
            "credible_interval": ci,
            "evidence": list(hypothesis.evidence or []),
        }

    async def _dispatch_diagnostic_detector(
        self, tool_name: str, params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Corre o detector certo in-process e devolve o resultado em dict.

        Async, com a própria `self.session` — sem HTTP. Devolve ``None``
        quando os parâmetros não chegam ou o detector não produz nada de
        útil (o chamador cai no fallback).
        """
        from datetime import date as _date

        try:
            if tool_name == "investigate_quality_drop":
                from src.explain.diagnostics.erro_tree import ErroTreeDetector
                from src.explain.diagnostics.types import TriggerType

                trigger = TriggerType(params.get("trigger", "quality_drop"))
                detector = ErroTreeDetector(self.session, self.tenant_id)
                result = await detector.investigate(
                    trigger=trigger,
                    period_days=int(params.get("period_days", 7)),
                    phase_id=params.get("phase_id"),
                )
                return {
                    "detector": "erro_tree",
                    "root_cause": self._hypothesis_to_dict(result.root_cause),
                    "chain": list(result.chain or []),
                    "steps_checked": list(result.steps_checked or []),
                    "recommendation": dict(result.recommendation or {}),
                }

            if tool_name == "find_common_cause":
                from src.explain.diagnostics.reichenbach import ReichenbachDetector

                phases = [str(p) for p in (params.get("deviating_phases") or [])]
                if len(phases) < 2:
                    return None
                detector = ReichenbachDetector(self.session, self.tenant_id)
                result = await detector.find_common_cause(
                    deviating_phases=phases,
                    period_days=int(params.get("period_days", 7)),
                )
                return {
                    "detector": "reichenbach",
                    "verdict": result.verdict,
                    "common_causes": [
                        self._hypothesis_to_dict(h) for h in result.common_causes
                    ],
                    "independent_causes": [
                        self._hypothesis_to_dict(h) for h in result.independent_causes
                    ],
                    "checks_run": list(result.checks_run or []),
                }

            if tool_name == "what_changed":
                from src.explain.diagnostics.mill_diff import MillDiffDetector

                detector = MillDiffDetector(self.session, self.tenant_id)
                result = await detector.what_changed(
                    good_start=_date.fromisoformat(params["good_period_start"]),
                    good_end=_date.fromisoformat(params["good_period_end"]),
                    bad_start=_date.fromisoformat(params["bad_period_start"]),
                    bad_end=_date.fromisoformat(params["bad_period_end"]),
                    metric=params.get("metric", "error_rate"),
                    phase_id=params.get("phase_id"),
                )
                out = result.to_dict()
                out["detector"] = "mill_diff"
                return out
        except Exception as exc:
            logger.warning(
                f"diagnostic detector '{tool_name}' falhou: {exc}"
            )
            return None
        return None

    async def _handle_diagnostic_dispatch(
        self,
        request: CopilotAskRequest,
        correlation_id: UUID,
        start_time: float,
    ) -> Optional[Tuple[CopilotResponse, Dict[str, Any]]]:
        """Q.33.A.2 — corre um dos 3 detectores de causa raiz in-process.

        Os detectores (`src/explain/diagnostics/{erro_tree,reichenbach,
        mill_diff}.py`) já existiam mas o copiloto não tinha caminho para
        os chamar — o RLM agent não os conhece. Este handler fecha a
        lacuna:

          1. lê as capability flags do tenant; se nenhuma estiver wired,
             devolve ``None`` (cai no RLM / LLM normal).
          2. uma chamada LLM escolhe a tool + params (`format="json"`
             devolve o dict já parseado — contrato Q.32.A.3).
          3. despacha in-process para o detector certo.
          4. uma segunda chamada LLM compõe a resposta PT-PT a partir do
             `DiagnosticResult`, com citação `calculation` real.

        Qualquer falha → ``None`` → o comportamento anterior preservado.
        """
        from datetime import date as _date

        from src.copilot.prompts.capabilities import fetch_capability_flags
        from src.copilot.tools.diagnostic_tools import (
            TOOL_CAPABILITY_MAP,
            tools_for_wired_capabilities,
        )

        flags = await fetch_capability_flags(self.session, self.tenant_id)
        wired_tools = tools_for_wired_capabilities(flags)
        if not wired_tools:
            # Nenhuma capability wired — deixa o RLM / LLM tentar.
            return None

        model = settings.ollama_model
        ollama_client = get_ollama_client()

        # --- 1. Selecção da tool ------------------------------------------
        selection_prompt = (
            "És o despachante de diagnósticos do copiloto de produção da "
            "NELO. O gestor fez esta pergunta:\n\n"
            f"\"{request.user_query}\"\n\n"
            "Tens estas ferramentas de diagnóstico de causa raiz "
            "disponíveis (JSON Schema):\n\n"
            f"{json.dumps(wired_tools, ensure_ascii=False, indent=2)}\n\n"
            f"Hoje é {_date.today().isoformat()}. Escolhe UMA ferramenta e "
            "preenche os parâmetros respeitando os campos `required` e os "
            "`enum`. Responde APENAS com JSON:\n"
            '{"tool": "<nome da ferramenta>", "params": { ... }}\n'
            'Se nenhuma ferramenta servir a pergunta, responde {"tool": null}.'
        )
        selection = await ollama_client.chat(
            selection_prompt, model, format="json",
        )
        if not isinstance(selection, dict):
            return None
        tool_name = selection.get("tool")
        params = selection.get("params") or {}
        if not tool_name or not isinstance(params, dict):
            return None
        if tool_name not in TOOL_CAPABILITY_MAP:
            logger.info(f"diagnostic dispatch: tool desconhecida '{tool_name}'")
            return None
        if not flags.get(TOOL_CAPABILITY_MAP[tool_name], False):
            # Capability não wired para este tenant — fallback honesto.
            logger.info(
                f"diagnostic dispatch: '{tool_name}' não wired neste tenant"
            )
            return None

        # --- 2. Dispatch in-process ---------------------------------------
        result_dict = await self._dispatch_diagnostic_detector(tool_name, params)
        if result_dict is None:
            return None

        # --- 3. Composição da resposta PT-PT ------------------------------
        composition_prompt = (
            "És o copiloto de produção da NELO (fábrica de kayaks, Vila do "
            "Conde). Corri o diagnóstico `" + tool_name + "` sobre os dados "
            "reais da fábrica e obtive este resultado estruturado:\n\n"
            f"{json.dumps(result_dict, ensure_ascii=False, indent=2, default=str)}\n\n"
            f"Pergunta do gestor: \"{request.user_query}\"\n\n"
            "Compõe uma resposta curta em PT-PT informal (tu, números "
            "concretos, sem rodeios) que explique a causa raiz encontrada, "
            "a confiança, e a recomendação. Se o diagnóstico não encontrou "
            "causa clara, di-lo honestamente. Responde APENAS com JSON:\n"
            '{"summary": "<1 frase>", "answer": "<resposta completa>"}'
        )
        composed = await ollama_client.chat(
            composition_prompt, model, format="json",
        )
        if not isinstance(composed, dict):
            return None
        answer = (composed.get("answer") or composed.get("summary") or "").strip()
        if not answer:
            return None
        summary = (composed.get("summary") or answer[:200]).strip()

        # --- 4. Citação + resposta ----------------------------------------
        from src.copilot.utils.citations import create_calculation_citation

        root = result_dict.get("root_cause")
        if root is None:
            common = result_dict.get("common_causes") or []
            root = common[0] if common else None
        confidence = 0.75
        if isinstance(root, dict) and root.get("confidence"):
            try:
                confidence = float(root["confidence"])
            except (TypeError, ValueError):
                confidence = 0.75

        citation = create_calculation_citation(
            calculation_type=f"diagnostic:{tool_name}",
            inputs=params,
            label=(
                f"Diagnóstico `{tool_name}` — cascata determinística sobre "
                "dados reais da fábrica"
            ),
            confidence=confidence,
            trust_index=min(confidence, 0.85),
        )

        suggestion_id = uuid4()
        response = CopilotResponse(
            suggestion_id=suggestion_id,
            correlation_id=correlation_id,
            type="ANSWER",
            intent="generic",
            summary=summary[:500],
            facts=[{"text": answer, "citations": [citation]}],
            actions=[],
            warnings=[],
            meta={
                "model": model,
                "tokens": 0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "validation_passed": True,
                "diagnostic_tool": tool_name,
                "diagnostic_params": params,
                "diagnostic_detector": result_dict.get("detector"),
            },
        )

        response_dict = response.model_dump()
        audit_data = await self._store_audit(
            correlation_id,
            suggestion_id,
            request,
            f"[diagnostic:{tool_name}] {request.user_query}",
            {"diagnostic_result": result_dict},
            response_dict,
            True,
            [],
            int((time.time() - start_time) * 1000),
        )
        return response, audit_data

    async def _handle_rlm_diagnostic(
        self,
        request: CopilotAskRequest,
        correlation_id: UUID,
        start_time: float,
    ) -> Optional[Tuple[CopilotResponse, Dict[str, Any]]]:
        """Q.31.H — corre o RLM agent para uma pergunta diagnóstica.

        O agente faz think→query→observe sobre o `FactoryStateQuery`
        (sub-queries tipadas servidas pelo semantic layer), em vez de
        receber um dump de 200k tokens do estado da fábrica. Devolve
        ``None`` quando o agente não chega a uma resposta, para o
        chamador cair no caminho LLM normal.
        """
        from src.copilot.rlm.agent import AgentTurn, run_rlm_agent
        from src.copilot.rlm.factory_state_query import FactoryStateQuery

        state_query = FactoryStateQuery(
            state=None, queries=self._resolve_semantic_queries()
        )

        model = settings.ollama_model
        ollama_client = get_ollama_client()

        async def _rlm_llm(turns: List[AgentTurn]) -> str:
            """Adapta o transcript do RLM ao OllamaClient.chat (texto cru).

            O RLM faz o seu próprio parsing de JSON, por isso pedimos
            ``format=None``: a última turn é o prompt, as anteriores
            (sem a system) viram history.
            """
            system_prompt = next(
                (t.content for t in turns if t.role == "system"), None
            )
            body = [t for t in turns if t.role != "system"]
            prompt = body[-1].content if body else request.user_query
            history = [
                {
                    "role": "assistant" if t.role == "assistant" else "user",
                    "content": t.content,
                }
                for t in body[:-1]
            ]
            resp = await ollama_client.chat(
                prompt,
                model,
                format=None,
                history=history or None,
                system_prompt=system_prompt,
            )
            if isinstance(resp, dict):
                return str(resp.get("content", ""))
            return str(resp)

        trace = await run_rlm_agent(
            question=request.user_query,
            state_query=state_query,
            llm=_rlm_llm,
            max_steps=6,
        )

        if not trace.answer:
            # O agente não produziu resposta — deixa o caminho LLM tentar.
            return None

        from src.copilot.utils.citations import create_system_data_citation

        answer = trace.answer
        citation = create_system_data_citation(
            data_source="rlm_agent",
            data_id=f"queries:{len(trace.queries_run)}",
            label=(
                f"RLM agent — {len(trace.queries_run)} sub-queries "
                "ao estado da fábrica"
            ),
            confidence=0.8,
            trust_index=0.8,
        )

        suggestion_id = uuid4()
        response = CopilotResponse(
            suggestion_id=suggestion_id,
            correlation_id=correlation_id,
            type="ANSWER",
            intent="generic",
            summary=answer[:500],
            facts=[{"text": answer, "citations": [citation]}],
            actions=[],
            warnings=[],
            meta={
                "model": model,
                "tokens": 0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "validation_passed": True,
                "rlm": True,
                "rlm_steps": trace.steps_used,
                "rlm_queries": [q.get("name") for q in trace.queries_run],
                "rlm_terminated": trace.terminated_reason,
            },
        )

        response_dict = response.model_dump()
        audit_data = await self._store_audit(
            correlation_id,
            suggestion_id,
            request,
            f"[RLM diagnostic] {request.user_query}",
            {"rlm_trace": trace.as_dict()},
            response_dict,
            True,
            [],
            int((time.time() - start_time) * 1000),
        )
        return response, audit_data

    def _resolve_semantic_queries(self):
        """`SemanticQueriesInMemory` sobre o IngestEngine global, ou None.

        Mesmo padrão best-effort do `AlertsEngine._get_semantic_queries`.
        ``None`` é aceitável — o `FactoryStateQuery` degrada cada
        sub-query para um dict "não disponível" que o LLM sabe ler.
        """
        try:
            from src.factory_data_product.api.endpoints import get_engine
            from src.factory_data_product.services.semantic_queries_inmemory import (
                SemanticQueriesInMemory,
            )
            engine = get_engine()
            if engine is None:
                return None
            return SemanticQueriesInMemory(engine)
        except Exception as exc:
            logger.warning(f"RLM: semantic layer indisponível ({exc})")
            return None

    async def _render_system_prompt(self) -> str:
        """Renderiza só o system prompt (system_prompt.md + capabilities).

        Q.37.E — extraído de `_render_prompt` para que o loop agêntico
        possa passar este system prompt ao passo de síntese final
        separado do user_query (o `system_prompt.md` é o que define o
        schema CopilotResponse).
        """
        prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
        system_prompt = prompt_path.read_text(encoding="utf-8")

        # Sprint Q.15.0 — inject the dynamic Capabilities block.
        try:
            from src.copilot.prompts.capabilities import (
                fetch_capability_flags,
                render_capabilities_block,
            )
            flags = await fetch_capability_flags(self.session, self.tenant_id)
            capabilities_block = render_capabilities_block(flags)
        except Exception as exc:
            logger.warning(
                "capabilities injection failed (%s) — defaulting to "
                "all-aspirational block", exc,
            )
            from src.copilot.prompts.capabilities import (
                render_capabilities_block,
            )
            capabilities_block = render_capabilities_block({})

        if "<!-- CAPABILITIES_PLACEHOLDER -->" in system_prompt:
            system_prompt = system_prompt.replace(
                "<!-- CAPABILITIES_PLACEHOLDER -->", capabilities_block,
            )
        else:
            system_prompt = capabilities_block + "\n\n---\n\n" + system_prompt
        return system_prompt

    async def _render_prompt(
        self,
        user_query: str,
        context_facts: Dict[str, Any],
        rag_chunks: List[Dict[str, Any]],
        kpi_snapshot: Optional[Dict[str, Any]] = None,
        intent: str = "generic",
        learned_signal: str = "",
    ) -> str:
        """Renderizar prompt completo."""
        # Carregar system prompt (system_prompt.md + capabilities block).
        system_prompt = await self._render_system_prompt()

        # Q.35.1.4 — o `context_str` (dump JSON do contexto) é construído
        # mais abaixo, DEPOIS do fact pack, para se poder remover o que já
        # foi renderizado de forma legível e não duplicar tokens no prompt.

        # Construir RAG chunks
        rag_str = ""
        if rag_chunks:
            rag_str = "\n## RAG Chunks (Base de Conhecimento)\n\n"
            for i, chunk in enumerate(rag_chunks, 1):
                rag_str += f"### Chunk {i} (Score: {chunk.get('score', 0):.2f})\n"
                rag_str += f"Source: {chunk.get('source_type')}:{chunk.get('source_id')}\n"
                rag_str += f"Text: {chunk.get('chunk_text', '')[:500]}...\n\n"
        
        # Construir fact pack de KPIs se disponível
        fact_pack_str = ""
        if kpi_snapshot and intent == "kpi_current":
            fact_pack_str = "\n## FACT PACK (KPIs Atuais - Source of Truth)\n\n"
            fact_pack_str += "Estes são os valores REAIS dos KPIs calculados da base de dados:\n\n"
            
            for kpi_name, kpi_data in kpi_snapshot.items():
                if kpi_name == "updated_at":
                    continue
                if isinstance(kpi_data, dict):
                    value = kpi_data.get("value")
                    reason = kpi_data.get("reason")
                    citations = kpi_data.get("citations", [])
                    
                    if value is not None:
                        fact_pack_str += f"- **{kpi_name.upper()}**: {value}"
                        if kpi_name in ["oee", "availability", "performance", "quality_fpy", "rework_rate"]:
                            fact_pack_str += "%"
                        fact_pack_str += "\n"
                        if citations:
                            fact_pack_str += f"  Citations: {', '.join([c.get('label', '') for c in citations])}\n"
                    elif reason:
                        fact_pack_str += f"- **{kpi_name.upper()}**: Não disponível ({reason})\n"
            
            fact_pack_str += "\n**IMPORTANTE**: Usa APENAS estes valores do FACT PACK. Se um KPI tem valor, usa-o. Se tem reason='NO_SOURCE_DATA', então não há dados disponíveis.\n\n"

        # Q.34.A.4 — FACT PACK de produção + qualidade (dados reais de
        # plan.production_orders / quality.rework_entry, via os readers do
        # context_builder). Renderizado para os intents que NÃO são o
        # fast-path de KPI, para o copiloto responder a "estado da fábrica"
        # / "dados de produção" com números concretos e citação real, em vez
        # de INSUFFICIENT_EVIDENCE.
        prod_rendered = False
        qual_rendered = False
        if intent in ("generic", "quality_summary", "plan_summary", "diagnostic"):
            prod_block = _render_production_fact_pack(
                context_facts.get("production") or {}
            )
            qual_block = _render_quality_fact_pack(
                context_facts.get("quality") or {}
            )
            if prod_block or qual_block:
                fact_pack_str += (
                    "\n## FACT PACK (Produção & Qualidade — Source of Truth)\n\n"
                    "Valores REAIS da base de dados. Responde com estes números "
                    "e cita-os; não inventes nem digas que não tens dados.\n\n"
                )
                fact_pack_str += prod_block + qual_block
                prod_rendered = bool(prod_block)
                qual_rendered = bool(qual_block)

        # Q.35.1.4 — contexto estruturado: emagrecer o prompt removendo o que
        # já foi para o FACT PACK de forma legível (produção/qualidade), em
        # vez de o duplicar no dump JSON. `default=str` é uma rede de
        # segurança caso algo não-serializável escape para o contexto.
        context_for_dump = dict(context_facts)
        if prod_rendered:
            context_for_dump.pop("production", None)
        if qual_rendered:
            context_for_dump.pop("quality", None)
        context_str = json.dumps(
            context_for_dump, indent=2, ensure_ascii=False, default=str,
        )

        # Schema JSON esperado
        schema_example = {
            "suggestion_id": "uuid",
            "correlation_id": "uuid",
            "type": "ANSWER",
            "intent": "explain_oee",
            "summary": "Resumo curto",
            "facts": [
                {
                    "text": "Facto",
                    "citations": [
                        {
                            "source_type": "db",
                            "ref": "table:orders;query_hash:abc",
                            "label": "Estatísticas",
                            "confidence": 0.95,
                            "trust_index": 0.88,
                        }
                    ],
                }
            ],
            "actions": [
                {
                    "action_type": "CREATE_DECISION_PR",
                    "label": "Criar PR de melhoria",
                    "entity_type": "recommendation",
                    "entity_id": "rec-1"
                }
            ],
            "warnings": [],
            "meta": {"model": "llama3.2", "tokens": 0, "latency_ms": 0, "validation_passed": True},
        }
        
        # Ajustar instruções baseado no tipo de entidade
        entity_instructions = ""
        if intent == "kpi_current" or "recommendations" in user_query.lower():
            entity_instructions = """
## INSTRUÇÕES ESPECIAIS PARA RECOMENDAÇÕES

Se estás a explicar recomendações, DEVES seguir este PADRÃO CANÓNICO OBRIGATÓRIO:

### REGRA CRÍTICA: NUNCA expliques apenas com valores isolados
❌ INCORRETO: "OEE atual é 18.7%"
✅ CORRETO: "O OEE atual é de 18.7%, o que indica perdas significativas de eficiência. Este valor reforça a necessidade de melhorias estruturais, mas NÃO é a causa direta desta recomendação específica. A recomendação baseia-se em [origem: heurística/boas práticas/dados específicos]."

### PADRÃO CANÓNICO DE EXPLICAÇÃO (OBRIGATÓRIO):

1) CONTEXTO DO DADO
   - Indica o KPI ou facto relevante (ex.: OEE atual = 18.7%)
   - Explica o que esse valor significa operacionalmente

2) INTERPRETAÇÃO
   - O que esse valor significa no contexto operacional
   - É bom/mau/crítico? Porquê?

3) RELAÇÃO COM A RECOMENDAÇÃO (OBRIGATÓRIO - DEVE mencionar explicitamente):
   
   ⚠️ REGRA CRÍTICA: Se ORIGENS NÃO incluir SYSTEM_DATA:
   - NÃO podes usar: "para melhorar OEE", "devido a OEE baixo", "porque o OEE é baixo"
   - DEVES usar: "Este KPI fornece CONTEXTO sobre o desempenho global, mas NÃO é a causa direta desta recomendação."
   - DEVES mencionar explicitamente a origem real: "baseia-se em heurística", "boas práticas", "ausência de dados específicos"
   
   Se ORIGENS incluir SYSTEM_DATA:
   a) "Este dado suporta diretamente esta recomendação porque [causa direta]"
   
   Se ORIGENS NÃO incluir SYSTEM_DATA:
   b) "Este dado fornece contexto geral sobre a operação, MAS não é a causa direta desta recomendação. A recomendação baseia-se em [origem real: heurística/boas práticas/ausência de dados]"
   c) "Este dado é independente desta recomendação. A recomendação deriva de [origem]"
   
   IMPORTANTE: DEVE usar palavras como: "porque", "devido", "baseia-se", "reforça", "origem", "deriva", "suporta", "justifica", "motivo", "razão", "relacionado", "conexão", "baseado", "fundado", "apoiado", "sustentado", "indica", "sugere", "mostra", "demonstra", "evidencia", "portanto", "assim", "deste modo", "consequentemente", "não está relacionado", "não provém", "não resulta", "fornece contexto", "não é a causa direta"

4) LIMITE DA INFERÊNCIA (quando aplicável)
   - Declara explicitamente o que NÃO pode ser concluído a partir deste dado
   - Se origem != SYSTEM_DATA, DEVE mencionar que não há dados diretos

### EXEMPLO CORRETO (ORIGENS = BEST_PRACTICE):

Para recomendação "Manutenção Moldes" com ORIGENS = ["BEST_PRACTICE", "HEURISTIC_REASONING"]:

"O OEE atual é de 18.7%, o que indica perdas significativas de eficiência na operação como um todo. Este valor fornece contexto geral sobre o desempenho global, mas NÃO é a causa direta desta recomendação específica. A recomendação de manutenção de moldes baseia-se em heurística industrial e boas práticas, dado que o sistema não dispõe atualmente de dados estruturados sobre estado de moldes ou histórico de manutenção, sendo portanto uma sugestão preventiva e exploratória."

NOTA CRÍTICA: 
- Repara que NÃO usa "para melhorar OEE" ou "devido a OEE baixo"
- Usa explicitamente "fornece contexto, mas NÃO é a causa direta"
- Menciona a origem real: "baseia-se em heurística e boas práticas"
- Declara ausência de dados: "não dispõe de dados estruturados"
- Usa "sugestão preventiva e exploratória" para deixar claro que não é causal

### VALIDAÇÃO AUTOMÁTICA:
- Se a explicação contiver apenas "X é Y%" ou valores numéricos isolados → REJEITADA
- Se origem != SYSTEM_DATA → DEVE conter frase explícita sobre não-derivação direta de dados
- Se origem == SYSTEM_DATA → DEVE conter ligação causal clara

### CITATIONS:
- Para citations de recomendações, usa source_type="recommendation" e ref="rec:{id}"
- Se não houver dados operacionais, cria citations baseadas nos metadados (origins, confidence, etc.)

"""
        
        prompt = f"""{system_prompt}

{fact_pack_str}

{learned_signal}

## CONTEXTO OPERACIONAL

{context_str}

{rag_str}

{entity_instructions}

## PERGUNTA DO UTILIZADOR

{user_query}

## INSTRUÇÕES CRÍTICAS

1. **PRIORIDADE FACT PACK**: Se há FACT PACK acima com valores de KPIs, USA ESSES VALORES. Eles são a fonte de verdade.
2. **VERIFICA DADOS DISPONÍVEIS**: O contexto acima pode conter valores vazios (0, 0.0, [], null) ou o status "NO_DATA_AVAILABLE".
3. **NÃO INVENTES VALORES**: Se o FACT PACK não tem um KPI (value=null, reason="NO_SOURCE_DATA") E o contexto também não tem dados, NÃO inventes valores. Devolve INSUFFICIENT_EVIDENCE.
4. **USA APENAS FACTOS COM CITATIONS**: Só podes usar factos que tenham citations válidas no FACT PACK ou contexto fornecido.
5. **INSUFFICIENT_EVIDENCE OBRIGATÓRIO**: Se não houver dados suficientes para responder, DEVE incluir warning com code="INSUFFICIENT_EVIDENCE" e message explicando que não há dados disponíveis.
6. **EXEMPLO CORRETO**: Se perguntarem "Qual é o OEE atual?":
   - Se FACT PACK tem oee.value=18.7: devolve summary="OEE atual é 18.7%" com fact e citation do FACT PACK
   - Se FACT PACK tem oee.value=null, reason="NO_SOURCE_DATA": devolve INSUFFICIENT_EVIDENCE
7. **FORMATO OBRIGATÓRIO**: Devolve APENAS JSON válido. Cada fact DEVE ter citations[] não vazio (exceto se INSUFFICIENT_EVIDENCE).
8. **ACTIONS FORMATO**: Se incluires actions[], cada action DEVE ser um objeto dict com:
   - "action_type": string (ex: "CREATE_DECISION_PR", "RUN_RUNBOOK")
   - "label": string (ex: "Criar PR", "Executar diagnóstico")
   - NUNCA uses strings simples em actions[], sempre objetos dict

## SCHEMA JSON

{json.dumps(schema_example, indent=2, ensure_ascii=False)}

IMPORTANTE: 
- Devolve APENAS o JSON, sem markdown, sem explicações adicionais
- NUNCA inventes valores numéricos se não estiverem no FACT PACK ou contexto
- actions[] deve ser uma lista de objetos dict, NUNCA strings
"""
        
        return prompt
    
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
        """Guardar registo de audit."""
        prompt_hash = sha256_hash(prompt)
        llm_response_str = json.dumps(llm_response, ensure_ascii=False)
        llm_response_hash = sha256_hash(llm_response_str)
        
        # Extrair citations
        citations = []
        for fact in response_dict.get("facts", []):
            citations.extend(fact.get("citations", []))
        
        # Converter UUIDs para strings no response_dict para JSON serialization
        def convert_uuids_to_str(obj):
            """Converter UUIDs para strings recursivamente."""
            if isinstance(obj, UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_uuids_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids_to_str(item) for item in obj]
            return obj
        
        response_dict_serialized = convert_uuids_to_str(response_dict)
        
        suggestion = CopilotSuggestion(
            id=suggestion_id,
            tenant_id=self.tenant_id,
            correlation_id=correlation_id,
            prompt_rendered=prompt,
            prompt_hash=prompt_hash,
            llm_raw_response=llm_response_str,
            llm_response_hash=llm_response_hash,
            user_query=request.user_query,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            response_json=response_dict_serialized,
            validation_passed=validation_passed,
            validation_errors={"errors": validation_errors} if validation_errors else None,
            citations={"citations": citations},
            model=settings.ollama_model,
            tokens=llm_response.get("meta", {}).get("tokens"),
            latency_ms=latency_ms,
            actor_id=self.actor_id,
            actor_role=self.actor_role,
        )
        
        self.session.add(suggestion)
        await self.session.flush()
        
        return {
            "suggestion_id": str(suggestion_id),
            "correlation_id": str(correlation_id),
            "prompt_hash": prompt_hash,
            "llm_response_hash": llm_response_hash,
        }
    
    def _create_security_flag_response(
        self,
        correlation_id: UUID,
    ) -> CopilotResponse:
        """Criar resposta para SECURITY_FLAG."""
        return CopilotResponse(
            suggestion_id=uuid4(),
            correlation_id=correlation_id,
            type="ERROR",
            intent="generic",
            summary="Query bloqueada por segurança",
            facts=[],
            actions=[],
            warnings=[
                {
                    "code": "SECURITY_FLAG",
                    "message": "Query detetada como tentativa de prompt injection. Operação bloqueada.",
                }
            ],
            meta={
                "model": "none",
                "tokens": 0,
                "latency_ms": 0,
                "validation_passed": False,
            },
        )
    
    def _create_model_offline_response(
        self,
        correlation_id: UUID,
    ) -> CopilotResponse:
        """Criar resposta para MODEL_OFFLINE."""
        return CopilotResponse(
            suggestion_id=uuid4(),
            correlation_id=correlation_id,
            type="ERROR",
            intent="generic",
            summary="Modelo LLM indisponível",
            facts=[],
            actions=[],
            warnings=[
                {
                    "code": "MODEL_OFFLINE",
                    "message": "Ollama não está disponível. Não foi possível gerar resposta.",
                }
            ],
            meta={
                "model": "offline",
                "tokens": 0,
                "latency_ms": 0,
                "validation_passed": False,
            },
        )
    
    def _validate_explanation_quality(
        self,
        llm_response: Dict[str, Any],
        user_query: str,
        recommendation_origins: Optional[List[List[str]]] = None,
    ) -> List[str]:
        """
        Validar qualidade da explicação para recomendações.
        
        Rejeita explicações superficiais que apenas repetem KPIs.
        
        Args:
            llm_response: Resposta do LLM
            user_query: Query do utilizador
            recommendation_origins: Lista de origins das recomendações (para validação de causalidade)
        """
        import re
        errors = []
        
        summary = llm_response.get("summary", "") if isinstance(llm_response, dict) else str(llm_response)
        facts = llm_response.get("facts", []) if isinstance(llm_response, dict) else []
        
        # Garantir que summary é string
        if not isinstance(summary, str):
            summary = str(summary)
        
        # Garantir que facts é lista
        if not isinstance(facts, list):
            facts = []
        
        # Verificar se summary é apenas um valor numérico isolado
        # Padrão: apenas "X é Y%" ou valores numéricos isolados
        shallow_patterns = [
            r'^[A-Za-z\s]+é\s+\d+\.?\d*%\.?$',  # "OEE é 18.7%"
            r'^\d+\.?\d*%\.?$',  # "18.7%"
            r'^[A-Za-z\s]+\s+\d+\.?\d*%\.?$',  # "OEE atual 18.7%"
        ]
        
        summary_clean = summary.strip()
        is_shallow = False
        for pattern in shallow_patterns:
            if re.match(pattern, summary_clean, re.IGNORECASE):
                is_shallow = True
                break
        
        # Verificar se summary tem menos de 50 caracteres e contém apenas valores
        if len(summary_clean) < 50 and re.search(r'\d+\.?\d*%', summary_clean) and not re.search(r'(porque|devido|baseia|reforça|causa|relação|não|mas|contudo)', summary_clean, re.IGNORECASE):
            is_shallow = True
        
        if is_shallow:
            errors.append(
                "EXPLANATION_TOO_SHALLOW: A explicação não pode ser apenas um valor numérico isolado. "
                "Deve incluir contexto, interpretação e relação com a recomendação."
            )
        
        # Verificar se facts têm explicações superficiais
        for i, fact in enumerate(facts):
            # Garantir que fact é dict
            if not isinstance(fact, dict):
                continue
            fact_text = fact.get("text", "")
            # Se fact é apenas "X é Y%"
            if re.match(r'^[A-Za-z\s]+é\s+\d+\.?\d*%\.?$', fact_text.strip(), re.IGNORECASE):
                errors.append(
                    f"EXPLANATION_TOO_SHALLOW: Fact {i} é apenas um valor isolado. "
                    "Deve incluir interpretação e relação com a recomendação."
                )
        
        # Verificar se há relação causal explícita (para recomendações)
        if "recomendação" in user_query.lower() or "recommendation" in user_query.lower():
            # Extrair textos de facts de forma segura
            fact_texts = []
            for f in facts:
                if isinstance(f, dict):
                    fact_texts.append(f.get("text", ""))
                elif isinstance(f, str):
                    fact_texts.append(f)
            combined_text = summary + " " + " ".join(fact_texts)
            
            # Verificar se menciona relação causal ou não-causal (padrões mais flexíveis)
            has_causal_link = re.search(
                r'(porque|devido|baseia|reforça|causa|relação|não é a causa|não deriva|independente|'
                r'origem|deriva|suporta|justifica|motivo|razão|relacionado|conexão|'
                r'baseado|fundado|fundamentado|apoiado|sustentado|'
                r'não está relacionado|não está ligado|não provém|não resulta|'
                r'portanto|assim|deste modo|desta forma|consequentemente|'
                r'indica|sugere|mostra|demonstra|evidencia)',
                combined_text,
                re.IGNORECASE
            )
            
            # Verificar também se há explicação contextual suficiente (mais de 150 caracteres com contexto)
            has_sufficient_context = (
                len(combined_text) > 150 and 
                re.search(
                    r'(valor|dado|métrica|kpi|indicador|situação|estado|condição|contexto|'
                    r'operacional|produção|sistema|processo|recomendação|melhoria|'
                    r'necessidade|importante|relevante|significativo)',
                    combined_text,
                    re.IGNORECASE
                ) and
                not is_shallow  # Não é uma explicação superficial
            )
            
            # Se não tem link causal explícito, mas tem contexto suficiente, não é erro crítico
            if not has_causal_link and not has_sufficient_context:
                errors.append(
                    "EXPLANATION_MISSING_CAUSAL_LINK: A explicação deve conter relação causal explícita "
                    "(porque, devido, baseia-se, reforça, origem, deriva, suporta, indica, sugere) ou declaração de não-causalidade."
                )
        
        # VALIDAÇÃO CRÍTICA: Bloquear causalidade falsa quando origins não inclui SYSTEM_DATA
        if recommendation_origins is not None and recommendation_origins:
            # Verificar se alguma recomendação tem origins que NÃO incluem SYSTEM_DATA
            has_non_system_data_origin = False
            for origins_list in recommendation_origins:
                if isinstance(origins_list, list):
                    if "SYSTEM_DATA" not in origins_list:
                        has_non_system_data_origin = True
                        break
                elif isinstance(origins_list, str):
                    if origins_list != "SYSTEM_DATA":
                        has_non_system_data_origin = True
                        break
            
            if has_non_system_data_origin:
                # Padrões de causalidade falsa a bloquear
                false_causality_patterns = [
                    r'para melhorar\s+\w+',  # "para melhorar OEE"
                    r'com o objetivo de melhorar\s+\w+',  # "com o objetivo de melhorar OEE"
                    r'devido a\s+\w+\s+(baixo|alto|baixa|alta)',  # "devido a OEE baixo"
                    r'porque\s+o\s+\w+\s+(é|está)\s+(baixo|alto|baixa|alta)',  # "porque o OEE é baixo"
                    r'devido ao\s+\w+\s+(baixo|alto|baixa|alta)',  # "devido ao OEE baixo"
                    r'por causa do\s+\w+\s+(baixo|alto|baixa|alta)',  # "por causa do OEE baixo"
                    r'para aumentar\s+\w+',  # "para aumentar OEE"
                    r'para reduzir\s+\w+',  # "para reduzir rework"
                    r'com vista a melhorar\s+\w+',  # "com vista a melhorar OEE"
                    r'visando melhorar\s+\w+',  # "visando melhorar OEE"
                ]
                
                combined_text_lower = combined_text.lower()
                for pattern in false_causality_patterns:
                    if re.search(pattern, combined_text_lower, re.IGNORECASE):
                        errors.append(
                            "EXPLANATION_FALSE_CAUSALITY: A explicação não pode criar causalidade falsa entre KPIs e recomendações "
                            "quando a origem não é SYSTEM_DATA. Use: 'Este KPI fornece contexto, mas NÃO é a causa direta desta recomendação.'"
                        )
                        break
                
                # Verificar se menciona explicitamente que NÃO é causa direta (obrigatório)
                has_explicit_non_causal = re.search(
                    r'(não é a causa|não deriva|não provém|não resulta|não está relacionado|'
                    r'fornece contexto|contexto geral|não é a causa direta|'
                    r'baseada em|baseia-se em|heurística|boas práticas|'
                    r'ausência de dados|não dispõe de dados)',
                    combined_text,
                    re.IGNORECASE
                )
                
                if not has_explicit_non_causal:
                    errors.append(
                        "EXPLANATION_FALSE_CAUSALITY: Quando a origem não é SYSTEM_DATA, a explicação DEVE mencionar explicitamente "
                        "que o KPI fornece contexto mas NÃO é a causa direta da recomendação."
                    )
        
        return errors
    
    def _create_validation_error_response(
        self,
        correlation_id: UUID,
        validation_errors: List[str],
    ) -> CopilotResponse:
        """Criar resposta para erro de validação (mensagem humana, sem stacktraces)."""
        # Mensagem humana para o utilizador (sem detalhes técnicos)
        user_message = "Não consegui validar a resposta do COPILOT. Tenta novamente."
        
        # Log detalhado (não enviado ao utilizador)
        logger.error(
            f"Validação falhou. Correlation: {correlation_id}. "
            f"Erros técnicos: {validation_errors}"
        )
        
        return CopilotResponse(
            suggestion_id=uuid4(),
            correlation_id=correlation_id,
            type="ERROR",
            intent="generic",
            summary=user_message,
            facts=[],
            actions=[],
            warnings=[
                {
                    "code": "VALIDATION_FAILED",
                    "message": user_message,
                }
            ],
            meta={
                "model": settings.ollama_model,
                "tokens": 0,
                "latency_ms": 0,
                "validation_passed": False,
                "correlation_id": str(correlation_id),  # Para debugging
            },
        )


# ─────────────────────────────────────────────────────────────────────────
# Q.18 fix-workforce — entity-aware context helpers
# ─────────────────────────────────────────────────────────────────────────

async def _build_employee_facts(session, tenant_id, employee_id):
    """Construir bloco employee_context para o LLM quando entity_type='employee'.

    Devolve quality_score, derived_level (1-3, 1=melhor), label, descrição,
    barcos recomendados e até 10 skills aptos do operador. O Copilot Nelinho
    usa estes factos para responder perguntas como "que barcos posso atribuir
    ao {nome}?" sem inventar dados.
    """
    from src.workforce.employee_extras_service import EmployeeExtrasService
    from src.workforce.levels import level_summary_payload

    svc = EmployeeExtrasService(session, tenant_id)
    quality = await svc.quality_score(employee_id)
    skills = await svc.skill_matrix(employee_id)
    skills_apt_names = [r.phase_name or r.phase_id for r in skills if r.can_do]
    payload = level_summary_payload(quality.score, skills_apt_names)
    payload["employee_id"] = str(employee_id)
    return payload

