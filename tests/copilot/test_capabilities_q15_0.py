"""Sprint Q.15.0 — Capabilities + diagnostic tool specs tests.

Tests pin three contracts:

  1. Capabilities block renders the right "Wired vs aspirational" split
     based on per-tenant flags.
  2. Diagnostic tool specs are well-formed (name + JSON Schema params)
     so Ollama tool-calling won't reject them at runtime.
  3. `tools_for_wired_capabilities` filters correctly so the LLM only
     sees tools it can actually invoke.
  4. Diagnostic intent detection picks up "porque caiu", "investigar",
     "o que mudou", etc. without misclassifying simple KPI questions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.copilot.prompts.capabilities import (
    KNOWN_CAPABILITIES,
    fetch_capability_flags,
    is_diagnostic_capability_wired,
    render_capabilities_block,
)
from src.copilot.tools.diagnostic_tools import (
    ALL_DIAGNOSTIC_TOOLS,
    FIND_COMMON_CAUSE,
    INVESTIGATE_QUALITY_DROP,
    TOOL_CAPABILITY_MAP,
    WHAT_CHANGED,
    tools_for_wired_capabilities,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ───────────────────────────────────────────────────────────────────────────
# Capability rendering
# ───────────────────────────────────────────────────────────────────────────


def test_block_marks_all_aspirational_when_no_flags():
    block = render_capabilities_block({})
    assert "Não wired ainda" in block
    # All 3 known caps appear under aspiracional.
    for cap in KNOWN_CAPABILITIES:
        assert cap.tool_name in block
    # And the "improvising" fallback wording is present.
    # Q.33.C — wording made honest: "existe no sistema mas não está
    # activada para este tenant" (em vez de soar a handler inexistente).
    assert "não está activada para este tenant" in block


def test_block_promotes_one_capability_when_flag_set():
    flags = {"diagnostics.erro_tree.enabled": True}
    block = render_capabilities_block(flags)
    # erro_tree is now Wired
    wired_section = block.split("Não wired")[0]
    assert "investigate_quality_drop" in wired_section
    # Other 2 stay aspirational
    assert "find_common_cause" in block
    assert "what_changed" in block
    # Aspiracional header still appears (since 2 are unset)
    assert "Não wired" in block


def test_block_no_aspirational_section_when_all_wired():
    flags = {cap.config_key: True for cap in KNOWN_CAPABILITIES}
    block = render_capabilities_block(flags)
    assert "Todos os handlers de diagnóstico estão activos" in block
    assert "Não wired ainda" not in block


def test_always_wired_block_present_regardless_of_flags():
    """The foundational capabilities are always Wired and must appear
    even when no diagnostic flags are set.

    Q.33.C — `cenário: simulação CPO via POETIQ` was dropped from the
    always-wired list: POETIQ isn't invoked from the `/ask` flow, so
    advertising it here over-promised an end-to-end simulation."""
    block = render_capabilities_block({})
    assert "facto:" in block
    assert "tools de leitura:" in block
    # POETIQ já não é prometido como always-wired no fluxo de /ask.
    assert "simulação CPO via POETIQ" not in block


def test_is_diagnostic_capability_wired_returns_false_when_empty():
    assert is_diagnostic_capability_wired({}) is False


def test_is_diagnostic_capability_wired_returns_true_when_any_flag_set():
    assert is_diagnostic_capability_wired(
        {"diagnostics.erro_tree.enabled": True}
    ) is True
    assert is_diagnostic_capability_wired(
        {"diagnostics.mill_diff.enabled": True}
    ) is True


# ───────────────────────────────────────────────────────────────────────────
# fetch_capability_flags — best-effort against TenantConfigService
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_capability_flags_returns_empty_on_lookup_failure(monkeypatch):
    """When TenantConfigService.get raises, all capabilities default to
    False — the safe fail mode for the LLM."""
    class _Svc:
        def __init__(self, *a, **kw): pass
        async def get(self, *a, **kw): raise RuntimeError("DB down")

    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService", _Svc,
    )
    flags = await fetch_capability_flags(MagicMock(), _TENANT)
    assert flags == {} or all(v is False for v in flags.values())


@pytest.mark.asyncio
async def test_fetch_capability_flags_returns_each_known_key():
    """When the service answers, the returned dict has one entry per
    known capability — even if every value is False."""
    flag_storage = {}

    class _Svc:
        def __init__(self, *a, **kw): pass
        async def get(self, _category, key, default=False):
            return flag_storage.get(key, default)

    import src.copilot.prompts.capabilities as caps_mod
    import src.core.services.tenant_config_service as tcs

    original = tcs.TenantConfigService
    try:
        tcs.TenantConfigService = _Svc  # type: ignore[assignment]
        flags = await fetch_capability_flags(MagicMock(), _TENANT)
        assert set(flags.keys()) == {cap.config_key for cap in KNOWN_CAPABILITIES}
        assert all(v is False for v in flags.values())
    finally:
        tcs.TenantConfigService = original


# ───────────────────────────────────────────────────────────────────────────
# Tool spec well-formedness
# ───────────────────────────────────────────────────────────────────────────


def test_three_diagnostic_tools_registered():
    assert len(ALL_DIAGNOSTIC_TOOLS) == 3
    names = {t["name"] for t in ALL_DIAGNOSTIC_TOOLS}
    assert names == {
        "investigate_quality_drop", "find_common_cause", "what_changed",
    }


@pytest.mark.parametrize("tool", ALL_DIAGNOSTIC_TOOLS)
def test_each_tool_has_required_function_calling_fields(tool):
    # OpenAI / Ollama function-calling shape.
    assert "name" in tool
    assert "description" in tool
    assert "parameters" in tool
    params = tool["parameters"]
    assert params["type"] == "object"
    assert "properties" in params
    assert "required" in params
    # Description must mention the capability gate so the LLM knows
    # NOT to call when aspirational.
    assert "capability" in tool["description"].lower() or "wired" in tool["description"].lower()


def test_investigate_quality_drop_required_args_minimal():
    """Only `trigger` is required — `period_days` and `phase_id` have
    sensible defaults so the LLM can call with one arg."""
    assert INVESTIGATE_QUALITY_DROP["parameters"]["required"] == ["trigger"]


def test_find_common_cause_requires_at_least_two_phases():
    schema = FIND_COMMON_CAUSE["parameters"]["properties"]["deviating_phases"]
    assert schema["minItems"] == 2


def test_what_changed_requires_both_periods():
    required = WHAT_CHANGED["parameters"]["required"]
    for field in (
        "good_period_start", "good_period_end",
        "bad_period_start", "bad_period_end",
    ):
        assert field in required


def test_tool_capability_map_covers_all_tools():
    for tool in ALL_DIAGNOSTIC_TOOLS:
        assert tool["name"] in TOOL_CAPABILITY_MAP


# ───────────────────────────────────────────────────────────────────────────
# tools_for_wired_capabilities — filter
# ───────────────────────────────────────────────────────────────────────────


def test_no_wired_capabilities_returns_empty_list():
    assert tools_for_wired_capabilities({}) == []


def test_one_wired_returns_one_tool():
    tools = tools_for_wired_capabilities({
        "diagnostics.erro_tree.enabled": True,
    })
    assert len(tools) == 1
    assert tools[0]["name"] == "investigate_quality_drop"


def test_all_wired_returns_all_three():
    tools = tools_for_wired_capabilities({
        "diagnostics.erro_tree.enabled": True,
        "diagnostics.reichenbach.enabled": True,
        "diagnostics.mill_diff.enabled": True,
    })
    assert len(tools) == 3


# ───────────────────────────────────────────────────────────────────────────
# Diagnostic intent detection
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("query", [
    "porque é que o OEE caiu na semana passada?",
    "investigar a fase de Laminagem",
    "o que mudou entre Abril e Maio?",
    "porque caiu o throughput?",
    "diagnóstico da qualidade",
    "qual foi a causa raiz da subida do retrabalho?",
    "throughput desceu",
    "OEE caiu",
])
def test_diagnostic_intent_detected(query):
    """Vocabulary keywords from §10 of the v2.2 prompt should route
    to the diagnostic intent."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)  # bypass __init__
    intent = svc._detect_intent(query)
    assert intent == "diagnostic", (
        f"Expected 'diagnostic' for {query!r}, got {intent!r}"
    )


@pytest.mark.parametrize("query", [
    "qual é o OEE atual?",
    "rework rate",
    "FPY?",
    "quanto é o throughput agora?",
])
def test_simple_kpi_questions_remain_kpi_current(query):
    """Diagnostic detection MUST NOT eat plain KPI lookups. These
    should still route to the fast path."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    intent = svc._detect_intent(query)
    assert intent == "kpi_current", (
        f"Expected 'kpi_current' for {query!r}, got {intent!r}"
    )


def test_generic_intent_for_unrecognised():
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    # Pergunta que não casa com nenhum intent específico → generic.
    assert svc._detect_intent("conta-me sobre os kayaks") == "generic"


def test_smalltalk_intent_for_greetings():
    """Saudações curtas são intent 'smalltalk' (fast-path sem LLM)."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    assert svc._detect_intent("olá") == "smalltalk"
    assert svc._detect_intent("bom dia") == "smalltalk"
    assert svc._detect_intent("obrigado!") == "smalltalk"
    # Saudação + pergunta real NÃO é smalltalk.
    assert svc._detect_intent("olá, qual o OEE?") != "smalltalk"
