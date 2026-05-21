"""
ProdPlan ONE — COPILOT fact pack builder
========================================

Q.66.D.2 — extraído de ``src/copilot/service.py`` (god-file 1708L) durante
a Fase 7 de decomposição. Responsabilidade única: montar o "fact pack"
que vai dentro do prompt do LLM (snapshot KPIs + capabilities + RAG
chunks) e variantes alternativas que produzem CopilotResponse sem passar
pelo LLM — fast-path KPI e RLM diagnostic agent.

Mantemos imports lazy (import dentro de funções) para não pagar custo de
startup quando o RLM/factory_data_product/workforce/profit não são tocados.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.models import CopilotSuggestion
from src.copilot.schemas import CopilotAskRequest, CopilotResponse
from src.copilot.utils.hashing import sha256_hash
from src.shared.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Semantic layer access (RLM diagnostic)
# ---------------------------------------------------------------------------

def resolve_semantic_queries():
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


# ---------------------------------------------------------------------------
# KPI fact pack block (goes into the LLM prompt)
# ---------------------------------------------------------------------------

def build_kpi_fact_pack_str(
    kpi_snapshot: Optional[Dict[str, Any]],
    intent: str,
) -> str:
    """Render the FACT PACK block para ir dentro do prompt LLM.

    Só emite o bloco quando ``intent == 'kpi_current'`` e há snapshot.
    Os KPIs com ``value is None`` mostram a ``reason`` (``NO_SOURCE_DATA``);
    o LLM já está instruído a devolver ``INSUFFICIENT_EVIDENCE`` nesse caso.
    """
    if not kpi_snapshot or intent != "kpi_current":
        return ""

    fact_pack_str = "\n## FACT PACK (KPIs Atuais - Source of Truth)\n\n"
    fact_pack_str += (
        "Estes são os valores REAIS dos KPIs calculados da base de dados:\n\n"
    )

    for kpi_name, kpi_data in kpi_snapshot.items():
        if kpi_name == "updated_at":
            continue
        if isinstance(kpi_data, dict):
            value = kpi_data.get("value")
            reason = kpi_data.get("reason")
            citations = kpi_data.get("citations", [])

            if value is not None:
                fact_pack_str += f"- **{kpi_name.upper()}**: {value}"
                if kpi_name in (
                    "oee", "availability", "performance",
                    "quality_fpy", "rework_rate",
                ):
                    fact_pack_str += "%"
                fact_pack_str += "\n"
                if citations:
                    fact_pack_str += (
                        f"  Citations: "
                        f"{', '.join([c.get('label', '') for c in citations])}\n"
                    )
            elif reason:
                fact_pack_str += (
                    f"- **{kpi_name.upper()}**: Não disponível ({reason})\n"
                )

    fact_pack_str += (
        "\n**IMPORTANTE**: Usa APENAS estes valores do FACT PACK. "
        "Se um KPI tem valor, usa-o. Se tem reason='NO_SOURCE_DATA', "
        "então não há dados disponíveis.\n\n"
    )

    return fact_pack_str


# ---------------------------------------------------------------------------
# Entity-aware fact helpers (Q.18 workforce)
# ---------------------------------------------------------------------------

async def build_employee_facts(session, tenant_id: UUID, employee_id):
    """Construir bloco employee_context para o LLM quando entity_type='employee'.

    Devolve quality_score, derived_level (1-3, 1=melhor), label, descrição,
    barcos recomendados e até 10 skills aptos do operador. O Copilot Nelinho
    usa estes factos para responder perguntas como "que barcos posso atribuir
    ao {nome}?" sem inventar dados.

    Q.66.D.2 — antes vivia em ``service.py`` como ``_build_employee_facts``
    top-level. Movido para aqui porque é fact-pack assembly (Q.18 entity-aware).
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


# ---------------------------------------------------------------------------
# KPI snapshot — entrada dos fluxos kpi_current + fast-path
# ---------------------------------------------------------------------------

async def fetch_kpi_snapshot(
    session: AsyncSession, tenant_id: UUID,
) -> Optional[Dict[str, Any]]:
    """Compute the KPI snapshot para ``tenant_id``.

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

        kpis = await calculate_kpis(session, tenant_id)
        return {
            key: (
                value.model_dump() if hasattr(value, "model_dump") else value
            )
            for key, value in kpis.items()
        }
    except Exception as e:
        logger.warning(f"Erro ao buscar KPI snapshot: {e}")
        return None


# ---------------------------------------------------------------------------
# Fast-path KPI response (skip LLM entirely)
# ---------------------------------------------------------------------------

_KPI_MAPPINGS = {
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

_KPI_PT_LABELS = {
    "oee": "OEE",
    "availability": "Disponibilidade",
    "performance": "Performance",
    "quality_fpy": "FPY",
    "rework_rate": "Taxa de Retrabalho",
}

_KPI_MAIN_KEYS = ("oee", "availability", "performance", "quality_fpy", "rework_rate")


async def build_fast_path_kpi_response(
    session: AsyncSession,
    tenant_id: UUID,
    request: CopilotAskRequest,
    correlation_id: UUID,
    start_time: float,
) -> Tuple[Optional[CopilotResponse], Dict[str, Any]]:
    """Fast path para perguntas simples de KPIs (sem LLM).

    Responde diretamente com dados do snapshot, em < 500ms. Devolve
    ``(None, {})`` se não conseguir produzir resposta — o caller cai
    para o caminho LLM.
    """
    try:
        kpi_snapshot = await fetch_kpi_snapshot(session, tenant_id)
        if not kpi_snapshot:
            return None, {}

        query_lower = request.user_query.lower()
        suggestion_id = uuid4()

        facts: List[Dict[str, Any]] = []
        summary_parts: List[str] = []

        from src.copilot.utils.citations import create_system_data_citation

        # Detectar KPI específico na pergunta
        detected_kpi = None
        for keyword, (kpi_key, kpi_label_pt, kpi_label_en) in _KPI_MAPPINGS.items():
            if keyword in query_lower:
                detected_kpi = (kpi_key, kpi_label_pt, kpi_label_en)
                break

        if not detected_kpi:
            for kpi_key in _KPI_MAIN_KEYS:
                kpi_data = kpi_snapshot.get(kpi_key, {})
                if isinstance(kpi_data, dict):
                    value = kpi_data.get("value")
                    if value is not None:
                        kpi_label = _KPI_PT_LABELS.get(kpi_key, kpi_key.upper())
                        fact_text = f"{kpi_label}: {value:.2f}%"
                        citation = create_system_data_citation(
                            data_source="kpi_snapshot",
                            data_id=kpi_key,
                            label=f"KPI {kpi_label}",
                            confidence=0.95,
                            trust_index=0.90,
                        )
                        facts.append({"text": fact_text, "citations": [citation]})
                        summary_parts.append(fact_text)
        else:
            kpi_key, kpi_label_pt, _ = detected_kpi
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
                    facts.append({"text": fact_text, "citations": [citation]})
                    summary_parts.append(fact_text)
                elif reason:
                    fact_text = f"{kpi_label_pt}: Não disponível ({reason})"
                    facts.append({"text": fact_text, "citations": []})
                    summary_parts.append(fact_text)

        if not facts:
            return None, {}

        summary = ". ".join(summary_parts) if summary_parts else "KPIs atuais"
        latency_ms = int((time.time() - start_time) * 1000)

        response = CopilotResponse(
            suggestion_id=suggestion_id,
            correlation_id=correlation_id,
            type="ANSWER",
            intent="explain_oee",
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

        audit_data = {
            "latency_ms": latency_ms,
            "fast_path": True,
            "intent": "kpi_current",
        }

        logger.info(f"Fast path KPI: {len(facts)} facts, {latency_ms}ms")
        return response, audit_data

    except Exception as e:
        logger.error(f"Erro no fast path KPI: {e}", exc_info=True)
        return None, {}


# ---------------------------------------------------------------------------
# RLM diagnostic agent path
# ---------------------------------------------------------------------------

async def build_rlm_diagnostic_response(
    request: CopilotAskRequest,
    semantic_queries,
    ollama_client,
    correlation_id: UUID,
    start_time: float,
) -> Optional[Tuple[CopilotResponse, Dict[str, Any], Dict[str, Any]]]:
    """Q.31.H — corre o RLM agent para uma pergunta diagnóstica.

    O agente faz think→query→observe sobre o `FactoryStateQuery`
    (sub-queries tipadas servidas pelo semantic layer), em vez de
    receber um dump de 200k tokens do estado da fábrica. Devolve
    ``None`` quando o agente não chega a uma resposta, para o
    chamador cair no caminho LLM normal.

    Returns:
        ``None`` se o agente não produzir resposta; caso contrário
        ``(response, audit_payload, llm_trace)`` onde ``audit_payload``
        já vem pronto para ``_store_audit`` do CopilotService.
    """
    from src.copilot.rlm.agent import AgentTurn, run_rlm_agent
    from src.copilot.rlm.factory_state_query import FactoryStateQuery

    state_query = FactoryStateQuery(state=None, queries=semantic_queries)

    # Q.68.D1: tarefa analítica (fact-pack assembly) — usa override classify.
    model = settings.model_for("classify")

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

    audit_payload = {
        "suggestion_id": suggestion_id,
        "prompt": f"[RLM diagnostic] {request.user_query}",
        "llm_response": {"rlm_trace": trace.as_dict()},
        "latency_ms": int((time.time() - start_time) * 1000),
    }

    return response, audit_payload, {"rlm_trace": trace.as_dict()}


# ---------------------------------------------------------------------------
# Prompt rendering (LLM input assembly)
# ---------------------------------------------------------------------------

_SCHEMA_EXAMPLE = {
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
            "entity_id": "rec-1",
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
    "meta": {
        "model": "llama3.2", "tokens": 0, "latency_ms": 0,
        "validation_passed": True,
    },
}


_RECOMMENDATION_ENTITY_INSTRUCTIONS = """
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


async def render_prompt(
    session: AsyncSession,
    tenant_id: UUID,
    user_query: str,
    context_facts: Dict[str, Any],
    rag_chunks: List[Dict[str, Any]],
    kpi_snapshot: Optional[Dict[str, Any]] = None,
    intent: str = "generic",
) -> str:
    """Renderizar prompt completo para o LLM.

    Lê o system prompt do disco, injecta o bloco dinâmico de capabilities
    (Q.15.0), monta o FACT PACK (KPIs), o contexto operacional, os RAG
    chunks e as instruções especiais para recomendações.
    """
    prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    # Sprint Q.15.0 — inject the dynamic Capabilities block. This tells
    # the LLM exactly which diagnostic tools are Wired vs aspirational on
    # this tenant. Best-effort: if the config lookup fails the placeholder
    # gets stripped and the LLM treats all capabilities as aspirational
    # (the safe default).
    try:
        from src.copilot.prompts.capabilities import (
            fetch_capability_flags,
            render_capabilities_block,
        )
        flags = await fetch_capability_flags(session, tenant_id)
        capabilities_block = render_capabilities_block(flags)
    except Exception as exc:
        logger.warning(
            "capabilities injection failed (%s) — defaulting to "
            "all-aspirational block", exc,
        )
        from src.copilot.prompts.capabilities import render_capabilities_block
        capabilities_block = render_capabilities_block({})

    if "<!-- CAPABILITIES_PLACEHOLDER -->" in system_prompt:
        system_prompt = system_prompt.replace(
            "<!-- CAPABILITIES_PLACEHOLDER -->", capabilities_block,
        )
    else:
        system_prompt = capabilities_block + "\n\n---\n\n" + system_prompt

    context_str = json.dumps(context_facts, indent=2, ensure_ascii=False)

    rag_str = ""
    if rag_chunks:
        rag_str = "\n## RAG Chunks (Base de Conhecimento)\n\n"
        for i, chunk in enumerate(rag_chunks, 1):
            rag_str += f"### Chunk {i} (Score: {chunk.get('score', 0):.2f})\n"
            rag_str += (
                f"Source: {chunk.get('source_type')}:{chunk.get('source_id')}\n"
            )
            rag_str += f"Text: {chunk.get('chunk_text', '')[:500]}...\n\n"

    fact_pack_str = build_kpi_fact_pack_str(kpi_snapshot, intent)

    entity_instructions = ""
    if intent == "kpi_current" or "recommendations" in user_query.lower():
        entity_instructions = _RECOMMENDATION_ENTITY_INSTRUCTIONS

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

{json.dumps(_SCHEMA_EXAMPLE, indent=2, ensure_ascii=False)}

IMPORTANTE:
- Devolve APENAS o JSON, sem markdown, sem explicações adicionais
- NUNCA inventes valores numéricos se não estiverem no FACT PACK ou contexto
- actions[] deve ser uma lista de objetos dict, NUNCA strings
"""

    return prompt


# ---------------------------------------------------------------------------
# LLM call helper (with tool-loop fallback for generic intent)
# ---------------------------------------------------------------------------

async def call_llm_for_intent(
    prompt: str,
    intent: str,
    model: str,
    ollama_client,
    conversation_history: Optional[List[Dict[str, str]]],
) -> Tuple[Any, int]:
    """Chamar Ollama com o caminho certo para o intent.

    Para ``generic``, se existir tool_registry, usa o ToolExecutor (loop
    agentic com tool calls). Para todos os outros, chamada directa.

    Returns ``(llm_response, tool_calls_count)`` — ``tool_calls_count`` é
    ``0`` no caminho directo.
    """
    from src.copilot.tool_executor import ToolExecutor
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
        return llm_response, len(tool_log)

    llm_response = await ollama_client.chat(
        prompt, model, format="json",
        history=conversation_history or None,
    )
    return llm_response, 0


# ---------------------------------------------------------------------------
# Audit persistence (CopilotSuggestion row)
# ---------------------------------------------------------------------------

def _convert_uuids_to_str(obj):
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _convert_uuids_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_uuids_to_str(item) for item in obj]
    return obj


async def store_copilot_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    actor_role: str,
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
    """Guardar registo de audit (CopilotSuggestion row).

    Q.66.D.2 — extraído de ``CopilotService._store_audit``. O service mantém
    o método público como wrapper para tests que monkeypatcham via classe.
    """
    prompt_hash = sha256_hash(prompt)
    llm_response_str = json.dumps(llm_response, ensure_ascii=False)
    llm_response_hash = sha256_hash(llm_response_str)

    citations: List[Dict[str, Any]] = []
    for fact in response_dict.get("facts", []):
        citations.extend(fact.get("citations", []))

    response_dict_serialized = _convert_uuids_to_str(response_dict)

    suggestion = CopilotSuggestion(
        id=suggestion_id,
        tenant_id=tenant_id,
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
        validation_errors=(
            {"errors": validation_errors} if validation_errors else None
        ),
        citations={"citations": citations},
        model=settings.model_for("classify"),
        tokens=llm_response.get("meta", {}).get("tokens"),
        latency_ms=latency_ms,
        actor_id=actor_id,
        actor_role=actor_role,
    )

    # Q.66.B.3: CopilotSuggestion e proposta do LLM (texto + citations
    # + validation) para o utilizador agir — quando vira CopilotDecisionPR
    # ou rule firing, esse e que gera audit em governance.
    session.add(suggestion)  # noqa: audit_coverage  # LLM suggestion, not gov state
    await session.flush()

    return {
        "suggestion_id": str(suggestion_id),
        "correlation_id": str(correlation_id),
        "prompt_hash": prompt_hash,
        "llm_response_hash": llm_response_hash,
    }
