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
    normalize_charts,
    validate_response_structure,
)
from src.copilot.utils.hashing import sha256_hash
from src.copilot.utils.redaction import redact_response, extract_employee_names_from_context
from src.shared.config import settings
from src.shared.auth.rbac import Role

logger = logging.getLogger(__name__)


# Regex para extrair blocos <chart>...JSON...</chart> que o LLM possa emitir
# dentro de campos de texto (summary, facts) em vez do campo charts[].
import re as _re

_CHART_BLOCK_RE = _re.compile(r"<chart>\s*(.*?)\s*</chart>", _re.DOTALL | _re.IGNORECASE)


def extract_chart_blocks(llm_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recolher gráficos da resposta do LLM.

    O LLM tem duas formas de emitir gráficos:
      1. campo ``charts[]`` no JSON (forma preferida);
      2. blocos ``<chart>{...}</chart>`` embebidos em texto (summary/facts).

    Esta função reúne ambas as fontes e devolve uma lista de dicts brutos
    — a validação Pydantic acontece em :func:`normalize_charts`. Os blocos
    ``<chart>`` extraídos são removidos do texto para não aparecerem crus.
    """
    charts: List[Dict[str, Any]] = []

    raw_charts = llm_response.get("charts")
    if isinstance(raw_charts, list):
        charts.extend(c for c in raw_charts if isinstance(c, dict))

    def _harvest_from_text(text: str) -> str:
        if not isinstance(text, str) or "<chart>" not in text.lower():
            return text
        for match in _CHART_BLOCK_RE.finditer(text):
            payload = match.group(1).strip()
            try:
                parsed = json.loads(payload)
            except (ValueError, TypeError):
                logger.warning("Bloco <chart> com JSON inválido — ignorado")
                continue
            if isinstance(parsed, dict):
                charts.append(parsed)
            elif isinstance(parsed, list):
                charts.extend(c for c in parsed if isinstance(c, dict))
        return _CHART_BLOCK_RE.sub("", text).strip()

    summary = llm_response.get("summary")
    if isinstance(summary, str):
        llm_response["summary"] = _harvest_from_text(summary)

    facts = llm_response.get("facts")
    if isinstance(facts, list):
        for fact in facts:
            if isinstance(fact, dict) and isinstance(fact.get("text"), str):
                fact["text"] = _harvest_from_text(fact["text"])

    return charts


class CopilotService:
    """Service para orquestração do COPILOT."""
    
    def __init__(self, session: AsyncSession, tenant_id: UUID, actor_id: UUID, actor_role: str):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.actor_role = actor_role
        self.has_hr_role = actor_role in (Role.HR_MANAGER.value, Role.ADMIN_PLATFORM.value)
    
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

        # 1.5. Load conversation history for multi-turn context
        conversation_history: List[Dict[str, str]] = []
        if request.conversation_id:
            try:
                conversation_history = await ConversationStore.get_history(
                    self.tenant_id, request.conversation_id
                )
            except Exception as e:
                logger.warning(f"Failed to load conversation history: {e}")
        
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
        
        # 2.6. Q.31.H — DIAGNOSTIC: o RLM agent corre think→query→observe
        # sobre o estado da fábrica (sub-queries tipadas, sem dump de 200k
        # tokens). Isolado e com fallback: se levanta, cai no caminho LLM
        # normal abaixo — os outros intents nunca passam por aqui.
        if intent == "diagnostic":
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
                # Q.55.B.2.1 — uma falha no RAG (ex.: a tabela
                # `copilot_rag_chunk` não existe quando o pgvector não
                # está instalado) aborta a transação asyncpg. Sem
                # rollback, TODAS as queries seguintes da mesma sessão
                # falham com InFailedSQLTransactionError. O RAG é
                # opcional — recuperar a sessão para o resto do pedido.
                try:
                    await self.session.rollback()
                except Exception:  # noqa: S110  Q.61.06: rollback during recovery; nothing else to do
                    pass

        # 6. Render prompt (com fact pack se kpi_snapshot disponível)
        # Limitar contexto para perguntas simples (reduzir prompt size = resposta mais rápida)
        prompt_start = time.time()
        # Para perguntas curtas, limitar contexto a apenas KPIs essenciais
        limited_context = context_facts
        if intent == "kpi_current" or len(request.user_query.split()) <= 5:
            # Manter apenas KPIs e métricas essenciais, remover detalhes operacionais
            limited_context = {
                "operational_snapshot": context_facts.get("operational_snapshot", {}),
                "kpis": context_facts.get("kpis", {}),
            }
            # Limitar RAG chunks também
            rag_chunks = rag_chunks[:2] if len(rag_chunks) > 2 else rag_chunks
        
        prompt = await self._render_prompt(
            request.user_query,
            limited_context,
            rag_chunks,
            kpi_snapshot=kpi_snapshot,
            intent=intent,
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
        
        try:
            llm_start = time.time()
            # For generic intents with tool registry loaded, use agentic tool loop
            # so the LLM can call factory data tools (backlog, WIP, bottlenecks, etc.)
            from src.copilot.tool_registry import get_tool_registry_sync
            registry = get_tool_registry_sync()
            if intent == "generic" and registry and registry.tools:
                executor = ToolExecutor(registry)
                llm_response, tool_log = await executor.execute_with_tools(
                    user_query=prompt,
                    model=model,
                    history=conversation_history or None,
                    format="json",
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
                # Só adicionar se tiver action_type válido
                if action.get("action_type"):
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
                        code = "VALIDATION_FAILED"
                        logger.warning(f"Warning code inválido: {warning.get('code')}, usando VALIDATION_FAILED")
                    
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
                                # BEST_PRACTICE ou outros inválidos -> usar 'recommendation' ou 'rag'
                                if "BEST_PRACTICE" in str(source_type).upper() or "PRACTICE" in str(source_type).upper():
                                    source_type = "recommendation"
                                elif "HEURISTIC" in str(source_type).upper() or "REASONING" in str(source_type).upper():
                                    source_type = "rag"
                                else:
                                    source_type = "system_data"  # Fallback seguro
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
                    
                    # Evidence enforcement: facts without real citations
                    if not normalized_citations and not has_insufficient_evidence:
                        if intent in ("kpi_current", "quality_summary", "plan_summary"):
                            # KPI/data queries: downgrade confidence and flag as ungrounded
                            normalized_citations = [{
                                "source_type": "system_data",
                                "ref": "system:copilot:ungrounded",
                                "label": "Sem evidência direta — valor não verificado",
                                "confidence": 0.3,
                                "trust_index": 0.3,
                            }]
                            if not any(w.get("code") == "INSUFFICIENT_EVIDENCE" for w in llm_response.get("warnings", [])):
                                warnings_list = llm_response.get("warnings", [])
                                warnings_list.append({
                                    "code": "INSUFFICIENT_EVIDENCE",
                                    "message": f"Fact sem citation real: '{fact_text[:80]}...' — confiança reduzida",
                                })
                                llm_response["warnings"] = warnings_list
                        else:
                            # Generic queries: still allow but mark as copilot-generated
                            normalized_citations = [{
                                "source_type": "system_data",
                                "ref": "system:copilot:generated",
                                "label": "Resposta do COPILOT (sem fonte de dados)",
                                "confidence": 0.5,
                                "trust_index": 0.5,
                            }]
                    
                    fact_normalized = {
                        "text": fact_text,
                        "citations": normalized_citations,
                    }
                    normalized_facts.append(fact_normalized)
                elif isinstance(fact, str):
                    # String fact — no real citations possible
                    if has_insufficient_evidence:
                        normalized_facts.append({"text": fact, "citations": []})
                    else:
                        confidence = 0.3 if intent in ("kpi_current", "quality_summary", "plan_summary") else 0.5
                        normalized_facts.append({
                            "text": fact,
                            "citations": [{
                                "source_type": "system_data",
                                "ref": "system:copilot:generated",
                                "label": "Resposta do COPILOT (sem fonte de dados)",
                                "confidence": confidence,
                                "trust_index": confidence,
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

        # 8.1. Gráficos (Q.53.F) — recolher do campo charts[] e de blocos
        # <chart> embebidos em texto, depois validar com Pydantic. Gráficos
        # malformados são descartados (mesmo princípio de actions): nunca
        # rebentam a resposta. extract_chart_blocks também limpa os blocos
        # <chart> do summary/facts in-place, por isso corre ANTES de ler o
        # summary abaixo.
        raw_charts = extract_chart_blocks(llm_response)
        charts_normalized, chart_warnings = normalize_charts(raw_charts)
        for cw in chart_warnings:
            logger.warning(f"Gráfico descartado: {cw}")
        # facts_normalized aponta para a mesma lista que llm_response["facts"];
        # extract_chart_blocks mutou os textos in-place, nada a re-ler.

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
        valid_intents = ("explain_oee", "explain_plan_change", "quality_summary", "data_integrity", "generic")
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
                charts=charts_normalized,  # Q.53.F — validados no passo 8.1
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
            logger.error(f"  intent: {response_intent} (valid: explain_oee, explain_plan_change, quality_summary, data_integrity, generic)")
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

        # Sprint Q.15.0 — Diagnostic intent: causal / "why" questions.
        # Checked BEFORE kpi_current because "porque caiu o OEE?"
        # contains "oee" but is fundamentally a diagnostic question, not
        # a fact lookup. The keyword list maps to the v2.2 prompt's
        # §10 ERRO-TREE / Reichenbach / Mill's vocabulary.
        diagnostic_triggers = (
            "porque ", "porquê", "por que ", "investigar", "investiga",
            "o que mudou", "que mudou", "what changed",
            "causa", "raiz", "diagnosticar", "diagnostico", "diagnóstico",
            # Q.55.B.2 — vocabulário PT-PT de fábrica que faltava: o
            # "gargalo" é a pergunta de diagnóstico mais comum do chefe
            # de turno e não estava na lista.
            "gargalo", "gargalos", "estrangula", "estrangular",
            "bottleneck", "estrangulamento",
        )
        diagnostic_kpi_drop = (
            "caiu", "desceu", "baixou", "subiu", "aumentou", "atrasou",
            "atrasaram", "drift", "spike", "disparou", "piorou",
        )
        if any(trigger in query_lower for trigger in diagnostic_triggers):
            return "diagnostic"
        # "Porque is implicit" patterns: "throughput desceu" / "OEE caiu"
        # treat as diagnostic when paired with a drop verb + KPI noun.
        kpi_nouns = ("oee", "fpy", "rework", "retrabalho", "throughput",
                     "qualidade", "defeito", "defeitos", "lead time",
                     "tempo", "barcos")
        if any(verb in query_lower for verb in diagnostic_kpi_drop):
            if any(noun in query_lower for noun in kpi_nouns):
                return "diagnostic"

        # Fast detection: perguntas muito curtas sobre KPIs devem ser kpi_current
        query_words = query_lower.split()
        if len(query_words) <= 5:
            # Perguntas curtas: verificar se mencionam KPIs
            kpi_keywords_short = ["oee", "fpy", "rework", "availability", "performance", "qual é", "qual o", "quanto"]
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

        # Q.55.B.2 — o RLM lê o `SemanticQueriesInMemory` (IngestEngine
        # in-memory). Quando esse motor está vazio (o caso normal hoje),
        # o agente só consegue responder "não tenho dados" — e ao devolver
        # uma resposta não-vazia rouba a pergunta ao caminho LLM normal,
        # que pós-Q.55.B.1 TEM os dados operacionais reais. Se a camada
        # semântica não resolve, salta já para esse caminho.
        semantic_queries = self._resolve_semantic_queries()
        if semantic_queries is None:
            logger.info(
                "RLM: camada semântica indisponível — a cair no caminho "
                "LLM (contexto operacional real)."
            )
            return None

        state_query = FactoryStateQuery(
            state=None, queries=semantic_queries
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
            # Q.55.B.2 — o `IngestEngine` é in-memory e arranca sem
            # ingestões. Um engine sem `active_run` não tem dados; devolver
            # um `SemanticQueriesInMemory` por cima dele só produz respostas
            # "não disponível". Tratar como indisponível (None) — o chamador
            # cai no caminho com os dados reais de Postgres.
            if engine.get_active_run() is None:
                return None
            return SemanticQueriesInMemory(engine)
        except Exception as exc:
            logger.warning(f"RLM: semantic layer indisponível ({exc})")
            return None

    async def _render_prompt(
        self,
        user_query: str,
        context_facts: Dict[str, Any],
        rag_chunks: List[Dict[str, Any]],
        kpi_snapshot: Optional[Dict[str, Any]] = None,
        intent: str = "generic",
    ) -> str:
        """Renderizar prompt completo."""
        # Carregar system prompt
        prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
        system_prompt = prompt_path.read_text(encoding="utf-8")

        # Sprint Q.15.0 — inject the dynamic Capabilities block. This
        # tells the LLM exactly which diagnostic tools are Wired vs
        # aspirational on this tenant, so it doesn't pretend to follow
        # the §10 framework without a real handler. Best-effort: if the
        # config lookup fails the placeholder gets stripped and the LLM
        # treats all capabilities as aspirational (the safe default).
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
            # Older prompt without the placeholder — prepend the block
            # at the top so it's always visible to the model.
            system_prompt = capabilities_block + "\n\n---\n\n" + system_prompt
        
        # Construir contexto estruturado
        context_str = json.dumps(context_facts, indent=2, ensure_ascii=False)
        
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
            "charts": [
                {
                    "type": "line",
                    "title": "Throughput por dia",
                    "data": [{"x": "Seg", "y": 31200}, {"x": "Ter", "y": 28400}],
                    "config": {"x_label": "Dia", "y_label": "Throughput", "unit": "€"},
                }
            ],
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
        
        # Q.66.B.3: CopilotSuggestion e proposta do LLM (texto + citations
        # + validation) para o utilizador agir — quando vira CopilotDecisionPR
        # ou rule firing, esse e que gera audit em governance.
        self.session.add(suggestion)  # noqa: audit_coverage  # LLM suggestion, not gov state
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

