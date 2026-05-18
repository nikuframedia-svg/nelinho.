"""
Q.37.E — testes do loop agêntico de tools.

Verifica:
  * a síntese final dedicada usa o `final_system_prompt` (não o
    TOOL_SYSTEM_PROMPT);
  * o loop devolve a resposta final e o tool_log;
  * `create_tool_citation` é determinística.

Ollama mockado por AsyncMock — sem rede, sem Postgres.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.copilot.tool_executor import ToolExecutor
from src.copilot.tool_registry import Tool, ToolCategory
from src.copilot.utils.citations import create_tool_citation


# ─────────────────────────────────────────────────────────────────────
# Fakes
# ─────────────────────────────────────────────────────────────────────

def _make_tool(tool_id="get_backlog"):
    return Tool(
        id=tool_id,
        name=tool_id,
        description="lê o backlog da fábrica",
        category=ToolCategory.DATA_READ,
        method="GET",
        path=f"/v1/{tool_id}",
    )


class _FakeRegistry:
    def __init__(self, tools=None):
        self.tools = {t.id: t for t in (tools or [])}

    def get_tool(self, tool_id):
        return self.tools.get(tool_id)

    def get_tools_summary(self, categories=None, include_dangerous=False):
        return "\n".join(f"- {t.id}: {t.description}" for t in self.tools.values())

    async def execute_tool(self, tool_id, params, headers=None):
        return {"tool_id": tool_id, "rows": [{"fase": "CORTE", "backlog": 42}]}


def _fake_ollama(responses):
    """Cliente Ollama fake: `chat` devolve `responses` em sequência."""
    client = AsyncMock()
    client.chat = AsyncMock(side_effect=list(responses))
    return client


# ─────────────────────────────────────────────────────────────────────
# create_tool_citation — determinística
# ─────────────────────────────────────────────────────────────────────

def test_create_tool_citation_e_determinista():
    c1 = create_tool_citation("get_backlog", {"phase": "CORTE"})
    c2 = create_tool_citation("get_backlog", {"phase": "CORTE"})
    assert c1 == c2
    assert c1["source_type"] == "calculation"
    assert c1["ref"].startswith("tool:get_backlog;params_hash:")


def test_create_tool_citation_params_diferentes_hash_diferente():
    c1 = create_tool_citation("get_backlog", {"phase": "CORTE"})
    c2 = create_tool_citation("get_backlog", {"phase": "LAMINAGEM"})
    assert c1["ref"] != c2["ref"]


def test_create_tool_citation_ordem_de_params_nao_importa():
    c1 = create_tool_citation("t", {"a": 1, "b": 2})
    c2 = create_tool_citation("t", {"b": 2, "a": 1})
    assert c1["ref"] == c2["ref"]


# ─────────────────────────────────────────────────────────────────────
# ToolExecutor — loop agêntico
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sem_registry_usa_final_system_prompt(monkeypatch):
    """Sem tools carregadas, a chamada única usa o final_system_prompt."""
    client = _fake_ollama([
        {"type": "ANSWER", "summary": "ok", "facts": []},
    ])
    monkeypatch.setattr(
        "src.copilot.tool_executor.get_ollama_client", lambda: client
    )

    executor = ToolExecutor(registry=_FakeRegistry(tools=[]))
    response, tool_log = await executor.execute_with_tools(
        user_query="qual o backlog?",
        model="gemma4:e4b",
        final_system_prompt="SYSTEM_PROMPT_MD_REAL",
    )
    assert response["type"] == "ANSWER"
    assert tool_log == []
    # A chamada usou o system prompt real, não vazio.
    assert client.chat.call_args.kwargs["system_prompt"] == "SYSTEM_PROMPT_MD_REAL"


@pytest.mark.asyncio
async def test_loop_com_tool_call_faz_sintese_final_dedicada(monkeypatch):
    """LLM pede tool → executa → síntese final usa system_prompt.md."""
    # 1ª resposta: pede uma tool. 2ª: sem tool (fim do loop).
    # 3ª: síntese final dedicada → CopilotResponse estruturado.
    client = _fake_ollama([
        {"tool_call": {"tool_id": "get_backlog", "params": {"phase": "CORTE"}}},
        {"summary": "vou responder"},  # sem tool_call → fim do loop
        {
            "type": "ANSWER",
            "intent": "generic",
            "summary": "Backlog de CORTE é 42h.",
            "facts": [
                {"text": "CORTE tem 42h de backlog", "citations": []}
            ],
        },
    ])
    monkeypatch.setattr(
        "src.copilot.tool_executor.get_ollama_client", lambda: client
    )

    executor = ToolExecutor(registry=_FakeRegistry(tools=[_make_tool()]))
    response, tool_log = await executor.execute_with_tools(
        user_query="qual o backlog de CORTE?",
        model="gemma4:e4b",
        final_system_prompt="SYSTEM_PROMPT_MD_REAL",
    )

    # A tool correu.
    assert len(tool_log) == 1
    assert tool_log[0]["tool_id"] == "get_backlog"
    # A resposta final é o CopilotResponse estruturado da síntese.
    assert response["type"] == "ANSWER"
    assert response["summary"] == "Backlog de CORTE é 42h."
    # Houve 3 chamadas: pedir tool, fim-de-loop, síntese final.
    assert client.chat.await_count == 3
    # A última chamada (síntese) usou o system_prompt.md real.
    assert client.chat.await_args.kwargs["system_prompt"] == "SYSTEM_PROMPT_MD_REAL"


@pytest.mark.asyncio
async def test_sem_tool_call_nao_refaz_sintese(monkeypatch):
    """Se o LLM responde logo sem tool, não há síntese extra."""
    client = _fake_ollama([
        {"type": "ANSWER", "intent": "generic", "summary": "resposta directa",
         "facts": [{"text": "x", "citations": [{"source_type": "db",
                    "ref": "t", "label": "l", "confidence": 1, "trust_index": 1}]}]},
    ])
    monkeypatch.setattr(
        "src.copilot.tool_executor.get_ollama_client", lambda: client
    )

    executor = ToolExecutor(registry=_FakeRegistry(tools=[_make_tool()]))
    response, tool_log = await executor.execute_with_tools(
        user_query="olá",
        model="gemma4:e4b",
        final_system_prompt="SYSTEM_PROMPT_MD_REAL",
    )
    assert tool_log == []
    assert response["summary"] == "resposta directa"
    # Só 1 chamada — sem tool_log não há síntese dedicada.
    assert client.chat.await_count == 1
