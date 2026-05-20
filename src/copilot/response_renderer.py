"""
ProdPlan ONE — COPILOT response renderer
========================================

Q.66.D.2 — extraído de ``src/copilot/service.py`` (god-file 1708L) durante
a Fase 7 de decomposição. Responsabilidade única: tudo o que toca na
forma da resposta — extracção de gráficos, normalização de actions/
warnings/citations, builders de erro canónicos (SECURITY_FLAG,
MODEL_OFFLINE, VALIDATION_FAILED) e validação de qualidade de explicação.

Function signatures preservadas a 100% — characterization tests em
``tests/copilot/test_copilot_service_characterization_q66_d.py`` chamam
``CopilotService._create_security_flag_response`` / ``extract_chart_blocks``
/ ``_validate_explanation_quality`` directamente; a façade ``service.py``
re-exporta os símbolos para garantir backwards compat.
"""

from __future__ import annotations

import json
import logging
import re
import re as _re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import ValidationError

from src.copilot.guardrails import normalize_charts, validate_response_structure
from src.copilot.schemas import CopilotResponse
from src.shared.config import settings

logger = logging.getLogger(__name__)


# Regex para extrair blocos <chart>...JSON...</chart> que o LLM possa emitir
# dentro de campos de texto (summary, facts) em vez do campo charts[].
_CHART_BLOCK_RE = _re.compile(r"<chart>\s*(.*?)\s*</chart>", _re.DOTALL | _re.IGNORECASE)


_VALID_WARNING_CODES = (
    "INSUFFICIENT_EVIDENCE",
    "SECURITY_FLAG",
    "LOW_TRUST_INDEX",
    "MODEL_OFFLINE",
    "VALIDATION_FAILED",
    "EXPLANATION_TOO_SHALLOW",
    "EXPLANATION_MISSING_CAUSAL_LINK",
    "EXPLANATION_FALSE_CAUSALITY",
)

_VALID_SOURCE_TYPES = (
    "db", "rag", "event", "calculation", "recommendation", "system_data",
)


# ---------------------------------------------------------------------------
# Chart extraction (was module-level in service.py; preserved signature).
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Normalisations: actions, warnings, citations
# ---------------------------------------------------------------------------

def normalize_actions(actions_raw: Any) -> List[Dict[str, Any]]:
    """Filtra/normaliza ``llm_response['actions']`` antes da validação Pydantic.

    - Strings são descartadas (LLM por vezes devolve `"CREATE_DECISION_PR"`).
    - Dicts com ``type`` em vez de ``action_type`` são renomeados.
    - Garante ``label`` (obrigatório).
    - Dicts sem ``action_type`` válido são descartados.
    """
    actions_normalized: List[Dict[str, Any]] = []

    if not isinstance(actions_raw, list):
        logger.warning(
            f"actions não é uma lista: {type(actions_raw).__name__}, convertendo..."
        )
        return actions_normalized

    for action in actions_raw:
        if isinstance(action, str):
            logger.warning(f"Ação é string: '{action}', ignorando...")
            continue

        if isinstance(action, dict):
            if "type" in action and "action_type" not in action:
                action["action_type"] = action.pop("type")
            if "label" not in action:
                action["label"] = action.get("action_type", "Ação")
            if action.get("action_type"):
                actions_normalized.append(action)
        else:
            logger.warning(
                f"Ação tem tipo inválido: {type(action).__name__}, ignorando..."
            )

    return actions_normalized


def normalize_warnings(warnings_raw: Any) -> List[Dict[str, str]]:
    """Coage warning codes desconhecidos a ``VALIDATION_FAILED`` e garante ``message``."""
    warnings_normalized: List[Dict[str, str]] = []

    if not isinstance(warnings_raw, list):
        return warnings_normalized

    for warning in warnings_raw:
        if isinstance(warning, dict):
            code = warning.get("code", "")
            if code not in _VALID_WARNING_CODES:
                logger.warning(
                    f"Warning code inválido: {warning.get('code')}, "
                    f"usando VALIDATION_FAILED"
                )
                code = "VALIDATION_FAILED"

            message = warning.get("message", "") or code
            warnings_normalized.append({"code": code, "message": message})

    return warnings_normalized


def _normalize_citation(
    citation: Dict[str, Any], correlation_id: UUID,
) -> Dict[str, Any]:
    source_type = citation.get("source_type", "db")
    if source_type not in _VALID_SOURCE_TYPES:
        # BEST_PRACTICE ou outros inválidos -> usar 'recommendation' ou 'rag'
        if (
            "BEST_PRACTICE" in str(source_type).upper()
            or "PRACTICE" in str(source_type).upper()
        ):
            source_type = "recommendation"
        elif (
            "HEURISTIC" in str(source_type).upper()
            or "REASONING" in str(source_type).upper()
        ):
            source_type = "rag"
        else:
            source_type = "system_data"
        logger.warning(
            f"Citation com source_type inválido '{citation.get('source_type')}' "
            f"convertido para '{source_type}'. Correlation: {correlation_id}"
        )

    ref = citation.get("ref", "")
    label = citation.get("label", "")

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
            citation.get("title")
            or citation.get("source_id")
            or citation.get("chunk_id")
            or citation.get("table")
            or f"Fonte {source_type}"
        )

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

    # max_length da Pydantic Schema
    ref = ref[:500]
    label = label[:200]

    return {
        "source_type": source_type,
        "ref": ref,
        "label": label,
        "confidence": confidence,
        "trust_index": trust_index,
    }


def normalize_facts_with_citations(
    llm_response: Dict[str, Any],
    intent: str,
    correlation_id: UUID,
    has_insufficient_evidence: bool,
) -> List[Dict[str, Any]]:
    """Normaliza facts[] do LLM: corrige citations inválidas, adiciona
    citation de fallback (system_data) quando o fact não tem citation real,
    e propaga ``INSUFFICIENT_EVIDENCE`` para warnings quando aplicável.

    Mutates ``llm_response['warnings']`` in-place quando precisa adicionar
    ``INSUFFICIENT_EVIDENCE`` (comportamento preservado de service.py).
    """
    facts_raw = llm_response.get("facts", [])
    if not isinstance(facts_raw, list):
        return []

    normalized_facts: List[Dict[str, Any]] = []
    for fact in facts_raw:
        if isinstance(fact, dict):
            citations = fact.get("citations", []) or []
            normalized_citations: List[Dict[str, Any]] = []
            for citation in citations:
                if isinstance(citation, dict):
                    normalized_citations.append(
                        _normalize_citation(citation, correlation_id)
                    )

            fact_text = fact.get("text", "")
            if not fact_text:
                fact_text = (
                    fact.get("description")
                    or fact.get("summary")
                    or fact.get("content")
                    or ""
                )

            if not fact_text:
                logger.warning(
                    f"Fact sem texto, ignorando. Correlation: {correlation_id}"
                )
                continue

            # Evidence enforcement: facts without real citations
            if not normalized_citations and not has_insufficient_evidence:
                if intent in ("kpi_current", "quality_summary", "plan_summary"):
                    normalized_citations = [{
                        "source_type": "system_data",
                        "ref": "system:copilot:ungrounded",
                        "label": "Sem evidência direta — valor não verificado",
                        "confidence": 0.3,
                        "trust_index": 0.3,
                    }]
                    if not any(
                        w.get("code") == "INSUFFICIENT_EVIDENCE"
                        for w in llm_response.get("warnings", [])
                    ):
                        warnings_list = llm_response.get("warnings", [])
                        warnings_list.append({
                            "code": "INSUFFICIENT_EVIDENCE",
                            "message": (
                                f"Fact sem citation real: '{fact_text[:80]}...' "
                                "— confiança reduzida"
                            ),
                        })
                        llm_response["warnings"] = warnings_list
                else:
                    normalized_citations = [{
                        "source_type": "system_data",
                        "ref": "system:copilot:generated",
                        "label": "Resposta do COPILOT (sem fonte de dados)",
                        "confidence": 0.5,
                        "trust_index": 0.5,
                    }]

            normalized_facts.append({
                "text": fact_text,
                "citations": normalized_citations,
            })
        elif isinstance(fact, str):
            if has_insufficient_evidence:
                normalized_facts.append({"text": fact, "citations": []})
            else:
                confidence = (
                    0.3
                    if intent in ("kpi_current", "quality_summary", "plan_summary")
                    else 0.5
                )
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

    return normalized_facts


# ---------------------------------------------------------------------------
# Error response builders — shapes pinned by characterization tests.
# ---------------------------------------------------------------------------

def create_security_flag_response(correlation_id: UUID) -> CopilotResponse:
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
                "message": (
                    "Query detetada como tentativa de prompt injection. "
                    "Operação bloqueada."
                ),
            }
        ],
        meta={
            "model": "none",
            "tokens": 0,
            "latency_ms": 0,
            "validation_passed": False,
        },
    )


def create_model_offline_response(correlation_id: UUID) -> CopilotResponse:
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
                "message": (
                    "Ollama não está disponível. Não foi possível gerar resposta."
                ),
            }
        ],
        meta={
            "model": "offline",
            "tokens": 0,
            "latency_ms": 0,
            "validation_passed": False,
        },
    )


def create_validation_error_response(
    correlation_id: UUID,
    validation_errors: List[str],
) -> CopilotResponse:
    """Criar resposta para erro de validação (mensagem humana, sem stacktraces)."""
    user_message = "Não consegui validar a resposta do COPILOT. Tenta novamente."

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


# ---------------------------------------------------------------------------
# Explanation quality validator
# ---------------------------------------------------------------------------

# Patterns / vocabulary used in :func:`validate_explanation_quality`.
_SHALLOW_PATTERNS = (
    re.compile(r'^[A-Za-z\s]+é\s+\d+\.?\d*%\.?$', re.IGNORECASE),  # "OEE é 18.7%"
    re.compile(r'^\d+\.?\d*%\.?$', re.IGNORECASE),  # "18.7%"
    re.compile(r'^[A-Za-z\s]+\s+\d+\.?\d*%\.?$', re.IGNORECASE),  # "OEE atual 18.7%"
)
_SHALLOW_PERCENT_RE = re.compile(r'\d+\.?\d*%')
_SHALLOW_CAUSAL_RE = re.compile(
    r'(porque|devido|baseia|reforça|causa|relação|não|mas|contudo)', re.IGNORECASE,
)
_SHALLOW_FACT_RE = re.compile(r'^[A-Za-z\s]+é\s+\d+\.?\d*%\.?$', re.IGNORECASE)
_CAUSAL_LINK_RE = re.compile(
    r'(porque|devido|baseia|reforça|causa|relação|não é a causa|não deriva|'
    r'independente|origem|deriva|suporta|justifica|motivo|razão|relacionado|'
    r'conexão|baseado|fundado|fundamentado|apoiado|sustentado|'
    r'não está relacionado|não está ligado|não provém|não resulta|portanto|'
    r'assim|deste modo|desta forma|consequentemente|indica|sugere|mostra|'
    r'demonstra|evidencia)',
    re.IGNORECASE,
)
_CONTEXT_VOCAB_RE = re.compile(
    r'(valor|dado|métrica|kpi|indicador|situação|estado|condição|contexto|'
    r'operacional|produção|sistema|processo|recomendação|melhoria|necessidade|'
    r'importante|relevante|significativo)',
    re.IGNORECASE,
)
_FALSE_CAUSALITY_RES = tuple(re.compile(p, re.IGNORECASE) for p in (
    r'para melhorar\s+\w+',
    r'com o objetivo de melhorar\s+\w+',
    r'devido a\s+\w+\s+(baixo|alto|baixa|alta)',
    r'porque\s+o\s+\w+\s+(é|está)\s+(baixo|alto|baixa|alta)',
    r'devido ao\s+\w+\s+(baixo|alto|baixa|alta)',
    r'por causa do\s+\w+\s+(baixo|alto|baixa|alta)',
    r'para aumentar\s+\w+',
    r'para reduzir\s+\w+',
    r'com vista a melhorar\s+\w+',
    r'visando melhorar\s+\w+',
))
_EXPLICIT_NON_CAUSAL_RE = re.compile(
    r'(não é a causa|não deriva|não provém|não resulta|não está relacionado|'
    r'fornece contexto|contexto geral|não é a causa direta|baseada em|'
    r'baseia-se em|heurística|boas práticas|ausência de dados|'
    r'não dispõe de dados)',
    re.IGNORECASE,
)


def _is_shallow_summary(summary_clean: str) -> bool:
    for pattern in _SHALLOW_PATTERNS:
        if pattern.match(summary_clean):
            return True
    return (
        len(summary_clean) < 50
        and _SHALLOW_PERCENT_RE.search(summary_clean) is not None
        and _SHALLOW_CAUSAL_RE.search(summary_clean) is None
    )


def _build_combined_text(summary: str, facts: List[Any]) -> str:
    fact_texts: List[str] = []
    for f in facts:
        if isinstance(f, dict):
            fact_texts.append(f.get("text", ""))
        elif isinstance(f, str):
            fact_texts.append(f)
    return summary + " " + " ".join(fact_texts)


def _has_non_system_data_origin(origins: List[Any]) -> bool:
    for entry in origins:
        if isinstance(entry, list) and "SYSTEM_DATA" not in entry:
            return True
        if isinstance(entry, str) and entry != "SYSTEM_DATA":
            return True
    return False


def validate_explanation_quality(
    llm_response: Dict[str, Any],
    user_query: str,
    recommendation_origins: Optional[List[List[str]]] = None,
) -> List[str]:
    """Validar qualidade da explicação para recomendações.

    Rejeita explicações superficiais que apenas repetem KPIs.
    """
    errors: List[str] = []

    if isinstance(llm_response, dict):
        summary = llm_response.get("summary", "")
        facts = llm_response.get("facts", [])
    else:
        summary = str(llm_response)
        facts = []

    if not isinstance(summary, str):
        summary = str(summary)
    if not isinstance(facts, list):
        facts = []

    summary_clean = summary.strip()
    is_shallow = _is_shallow_summary(summary_clean)
    if is_shallow:
        errors.append(
            "EXPLANATION_TOO_SHALLOW: A explicação não pode ser apenas um valor "
            "numérico isolado. Deve incluir contexto, interpretação e relação "
            "com a recomendação."
        )

    for i, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        fact_text = fact.get("text", "")
        if _SHALLOW_FACT_RE.match(fact_text.strip()):
            errors.append(
                f"EXPLANATION_TOO_SHALLOW: Fact {i} é apenas um valor isolado. "
                "Deve incluir interpretação e relação com a recomendação."
            )

    combined_text = ""
    query_lower = user_query.lower()
    if "recomendação" in query_lower or "recommendation" in query_lower:
        combined_text = _build_combined_text(summary, facts)

        has_causal_link = _CAUSAL_LINK_RE.search(combined_text) is not None
        has_sufficient_context = (
            len(combined_text) > 150
            and _CONTEXT_VOCAB_RE.search(combined_text) is not None
            and not is_shallow
        )

        if not has_causal_link and not has_sufficient_context:
            errors.append(
                "EXPLANATION_MISSING_CAUSAL_LINK: A explicação deve conter "
                "relação causal explícita (porque, devido, baseia-se, reforça, "
                "origem, deriva, suporta, indica, sugere) ou declaração de "
                "não-causalidade."
            )

    if (
        recommendation_origins
        and _has_non_system_data_origin(recommendation_origins)
    ):
        # combined_text só foi construído no ramo "recomendação"; se entrámos
        # aqui sem ele, montar agora para garantir cobertura dos patterns.
        if not combined_text:
            combined_text = _build_combined_text(summary, facts)
        combined_lower = combined_text.lower()

        if any(p.search(combined_lower) for p in _FALSE_CAUSALITY_RES):
            errors.append(
                "EXPLANATION_FALSE_CAUSALITY: A explicação não pode criar "
                "causalidade falsa entre KPIs e recomendações quando a origem "
                "não é SYSTEM_DATA. Use: 'Este KPI fornece contexto, mas NÃO "
                "é a causa direta desta recomendação.'"
            )

        if _EXPLICIT_NON_CAUSAL_RE.search(combined_text) is None:
            errors.append(
                "EXPLANATION_FALSE_CAUSALITY: Quando a origem não é "
                "SYSTEM_DATA, a explicação DEVE mencionar explicitamente "
                "que o KPI fornece contexto mas NÃO é a causa direta da "
                "recomendação."
            )

    return errors


# ---------------------------------------------------------------------------
# Pydantic ValidationError → diagnostic logging helper
# ---------------------------------------------------------------------------

_VALID_RESPONSE_TYPES = ("ANSWER", "RUNBOOK_RESULT", "PROPOSAL", "ERROR")
_VALID_RESPONSE_INTENTS = (
    "explain_oee", "explain_plan_change", "quality_summary",
    "data_integrity", "generic",
)


def _log_pydantic_validation_failure(
    error: ValidationError,
    correlation_id: UUID,
    response_type: str,
    response_intent: str,
    response_summary: str,
    facts_normalized: List[Dict[str, Any]],
    actions_normalized: List[Dict[str, Any]],
    warnings_normalized: List[Dict[str, Any]],
    llm_response: Dict[str, Any],
) -> List[str]:
    """Capturar erro de validação do Pydantic com diagnóstico detalhado.

    Devolve a lista normalizada (campo → mensagem) que o caller passa a
    :func:`create_validation_error_response`.
    """
    detailed: List[str] = []
    for err in error.errors():
        field_path = " -> ".join(str(loc) for loc in err.get("loc", []))
        error_msg = err.get("msg", "Validation error")
        error_input = err.get("input", "")
        detailed.append(
            f"{field_path}: {error_msg} (input: {str(error_input)[:100]})"
        )

    logger.error(
        f"Pydantic ValidationError ao criar CopilotResponse. "
        f"Correlation: {correlation_id}. Erros: {detailed}"
    )
    logger.error(
        f"Dados: type={response_type} intent={response_intent} "
        f"summary_len={len(response_summary)} "
        f"facts={len(facts_normalized)} actions={len(actions_normalized)} "
        f"warnings={len(warnings_normalized)}"
    )
    logger.debug(
        f"LLM response completo: {json.dumps(llm_response, indent=2, default=str)}"
    )
    return detailed


def assemble_copilot_response(
    llm_response: Dict[str, Any],
    *,
    request_user_query: str,
    request_entity_type: Optional[str],
    request_recommendation_origins: Optional[List[List[str]]],
    intent: str,
    correlation_id: UUID,
    suggestion_id: UUID,
    model: str,
    latency_ms: int,
) -> Tuple[Optional[CopilotResponse], List[str], bool]:
    """Pipeline completa de normalização + validação + Pydantic build.

    Q.66.D.2 — extraído de ``CopilotService.process_ask`` para evitar que a
    façade exceda 250 linhas. Executa, por ordem:

      1. Normalização in-place do ``llm_response`` (actions/warnings/facts).
      2. ``validate_response_structure`` (estrutura básica),
      3. ``validate_explanation_quality`` quando aplicável,
      4. Coerção defensiva de ``type``/``intent``/``summary``,
      5. ``extract_chart_blocks`` + ``normalize_charts``,
      6. construção do ``CopilotResponse`` Pydantic.

    Devolve ``(response | None, errors, validation_passed)``. Quando
    ``response`` é ``None`` o caller deve emitir
    :func:`create_validation_error_response` com os erros devolvidos.
    """
    # 1. Normalização in-place (delegado a coerce_actions via escalation_router
    # para o caller; aqui aceitamos que o llm_response já tem actions/warnings/
    # facts canonicalizados).
    from src.copilot.escalation_router import coerce_actions

    actions_normalized = coerce_actions(llm_response.get("actions", []))
    llm_response["actions"] = actions_normalized

    warnings_normalized = normalize_warnings(llm_response.get("warnings", []))
    llm_response["warnings"] = warnings_normalized

    has_insufficient_evidence = any(
        w.get("code") == "INSUFFICIENT_EVIDENCE" for w in warnings_normalized
    )

    facts_normalized = normalize_facts_with_citations(
        llm_response, intent, correlation_id, has_insufficient_evidence,
    )
    llm_response["facts"] = facts_normalized

    validation_passed, validation_errors = validate_response_structure(llm_response)

    if (
        "recommendations" in request_user_query.lower()
        or request_entity_type == "recommendations"
    ):
        origins = request_recommendation_origins or []
        explanation_errors = validate_explanation_quality(
            llm_response, request_user_query, recommendation_origins=origins,
        )
        if explanation_errors:
            validation_errors.extend(explanation_errors)
            validation_passed = False

    if not validation_passed:
        logger.error(f"Validação falhou: {validation_errors}")
        logger.debug(f"LLM response que falhou validação: {llm_response}")
        return None, validation_errors, False

    raw_charts = extract_chart_blocks(llm_response)
    charts_normalized, chart_warnings = normalize_charts(raw_charts)
    for cw in chart_warnings:
        logger.warning(f"Gráfico descartado: {cw}")

    meta_raw = llm_response.get("meta", {})
    meta_normalized = {
        "model": model,
        "tokens": meta_raw.get("tokens", 0) if isinstance(meta_raw, dict) else 0,
        "latency_ms": latency_ms,
        "validation_passed": validation_passed,
    }

    response_type = llm_response.get("type", "ANSWER")
    if response_type not in _VALID_RESPONSE_TYPES:
        logger.warning(f"Tipo inválido: {response_type}, usando ANSWER")
        response_type = "ANSWER"

    response_intent = llm_response.get("intent", "generic")
    if response_intent not in _VALID_RESPONSE_INTENTS:
        logger.warning(f"Intent inválido: {response_intent}, usando generic")
        response_intent = "generic"

    response_summary = (
        str(llm_response.get("summary", ""))
        if llm_response.get("summary") else ""
    )
    if not response_summary:
        if facts_normalized:
            response_summary = (
                facts_normalized[0].get("text", "")[:500]
                if facts_normalized else "Resposta do COPILOT"
            )
        else:
            response_summary = "Resposta do COPILOT"

    try:
        response = CopilotResponse(
            suggestion_id=suggestion_id,
            correlation_id=correlation_id,
            type=response_type,
            intent=response_intent,
            summary=response_summary,
            facts=facts_normalized,
            actions=actions_normalized,
            warnings=warnings_normalized,
            charts=charts_normalized,
            meta=meta_normalized,
        )
    except ValidationError as e:
        detailed = _log_pydantic_validation_failure(
            e, correlation_id, response_type, response_intent,
            response_summary, facts_normalized, actions_normalized,
            warnings_normalized, llm_response,
        )
        return None, detailed, False

    return response, validation_errors, validation_passed
