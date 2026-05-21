"""
ProdPlan ONE — COPILOT intent router
====================================

Q.66.D.2 — extraído de ``src/copilot/service.py`` (god-file 1708L) durante
a Fase 7 de decomposição. Responsabilidade única: dado o ``user_query`` em
texto cru, devolver o intent canónico que orquestra o fluxo do
:class:`CopilotService.process_ask`.

Os intents são literais usados como chaves de fast-path (kpi_current),
RLM diagnostic (diagnostic) ou caminho LLM normal (generic/quality_summary/
plan_summary/hr_summary). Mudanças aqui partem characterization tests em
``tests/copilot/test_copilot_service_characterization_q66_d.py``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vocabulário de detecção — pinned aqui (não promover para top-level de
# ``service.py``: as constantes vivem onde são usadas).
# ---------------------------------------------------------------------------

# Sprint Q.15.0 — Diagnostic intent: causal / "why" questions.
# Checked BEFORE kpi_current because "porque caiu o OEE?" contains "oee"
# but is fundamentally a diagnostic question, not a fact lookup. The
# keyword list maps to the v2.2 prompt's §10 ERRO-TREE / Reichenbach /
# Mill's vocabulary.
_DIAGNOSTIC_TRIGGERS = (
    "porque ", "porquê", "por que ", "investigar", "investiga",
    "o que mudou", "que mudou", "what changed",
    "causa", "raiz", "diagnosticar", "diagnostico", "diagnóstico",
    # Q.55.B.2 — vocabulário PT-PT de fábrica que faltava: o "gargalo"
    # é a pergunta de diagnóstico mais comum do chefe de turno e não
    # estava na lista.
    "gargalo", "gargalos", "estrangula", "estrangular",
    "bottleneck", "estrangulamento",
)

_DIAGNOSTIC_KPI_DROP = (
    "caiu", "desceu", "baixou", "subiu", "aumentou", "atrasou",
    "atrasaram", "drift", "spike", "disparou", "piorou",
)

_DIAGNOSTIC_KPI_NOUNS = (
    "oee", "fpy", "rework", "retrabalho", "throughput",
    "qualidade", "defeito", "defeitos", "lead time",
    "tempo", "barcos",
)

_KPI_KEYWORDS_SHORT = (
    "oee", "fpy", "rework", "availability", "performance",
    "qual é", "qual o", "quanto",
)

_KPI_KEYWORDS = ("oee", "fpy", "rework", "availability", "performance", "quality")

_KPI_QUESTION_PATTERNS = ("qual é", "qual o", "quanto é", "atual", "current", "agora")

_KPI_FOLLOWUPS = ("oee", "fpy", "rework", "taxa", "rate", "percentagem", "%")


def detect_intent(user_query: str) -> str:
    """Detetar intent da pergunta do utilizador.

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

    if any(trigger in query_lower for trigger in _DIAGNOSTIC_TRIGGERS):
        return "diagnostic"

    # "Porque is implicit" patterns: "throughput desceu" / "OEE caiu"
    # treat as diagnostic when paired with a drop verb + KPI noun.
    if any(verb in query_lower for verb in _DIAGNOSTIC_KPI_DROP):
        if any(noun in query_lower for noun in _DIAGNOSTIC_KPI_NOUNS):
            return "diagnostic"

    # Fast detection: perguntas muito curtas sobre KPIs devem ser kpi_current
    query_words = query_lower.split()
    if len(query_words) <= 5:
        if any(kw in query_lower for kw in _KPI_KEYWORDS_SHORT):
            return "kpi_current"

    has_kpi_keyword = any(keyword in query_lower for keyword in _KPI_KEYWORDS)
    has_kpi_question = any(pattern in query_lower for pattern in _KPI_QUESTION_PATTERNS)

    if has_kpi_keyword or (
        has_kpi_question and any(kw in query_lower for kw in _KPI_FOLLOWUPS)
    ):
        return "kpi_current"

    # Quality summary
    if any(
        word in query_lower
        for word in ("qualidade", "quality", "erros", "errors", "defeitos", "defects")
    ):
        if any(
            word in query_lower
            for word in ("resumo", "summary", "overview", "visão")
        ):
            return "quality_summary"

    # Plan summary
    if any(
        word in query_lower
        for word in ("plano", "plan", "planeamento", "scheduling", "agendamento")
    ):
        if any(
            word in query_lower
            for word in ("resumo", "summary", "overview", "visão")
        ):
            return "plan_summary"

    # HR summary
    if any(
        word in query_lower
        for word in (
            "hr", "recursos humanos", "funcionários", "employees",
            "alocações", "allocations",
        )
    ):
        if any(
            word in query_lower
            for word in ("resumo", "summary", "overview", "visão")
        ):
            return "hr_summary"

    return "generic"
