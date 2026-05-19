"""
Sprint Q.33.B — testes do tool registry carregado in-process.

O bug: `get_tool_registry()` fazia fetch HTTP a `http://localhost:8000`
(porta errada — o backend serve em :8001) → 0 tools → o loop agêntico
nunca engatava. O fix: carregar o spec da própria app via
`load_from_openapi(openapi_spec=app.openapi())`.

Cobertura:
- `load_from_openapi(openapi_spec=...)` não toca na rede e regista N>0 tools
- paths bloqueados (`/health`, `/openapi.json`, ...) ficam de fora
- a categorização separa leitura de escrita
"""

from __future__ import annotations

import pytest

from src.copilot.tool_registry import ToolCategory, ToolRegistry


def _minimal_spec() -> dict:
    """Um OpenAPI spec mínimo com endpoints de leitura, escrita e bloqueados."""
    return {
        "openapi": "3.0.0",
        "info": {"title": "test", "version": "1.0"},
        "paths": {
            "/v1/factory/wip": {
                "get": {
                    "summary": "Get WIP",
                    "description": "Work-in-progress por fase.",
                    "parameters": [
                        {
                            "name": "phase_id",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {"200": {"description": "ok"}},
                    "tags": ["factory"],
                },
            },
            "/v1/factory/ingest": {
                "post": {
                    "summary": "Ingest factory data",
                    "description": "Carrega dados — operação de escrita.",
                    "responses": {"200": {"description": "ok"}},
                    "tags": ["factory"],
                },
            },
            "/health": {
                "get": {
                    "summary": "Health check",
                    "responses": {"200": {"description": "ok"}},
                },
            },
            "/openapi.json": {
                "get": {
                    "summary": "OpenAPI spec",
                    "responses": {"200": {"description": "ok"}},
                },
            },
        },
    }


async def test_load_from_spec_registers_tools_without_network():
    """`load_from_openapi(openapi_spec=...)` regista tools sem fetch HTTP."""
    registry = ToolRegistry()
    count = await registry.load_from_openapi(openapi_spec=_minimal_spec())

    assert count > 0
    assert len(registry.tools) == count


async def test_blocked_paths_excluded():
    """`/health` e `/openapi.json` não viram tools."""
    registry = ToolRegistry()
    await registry.load_from_openapi(openapi_spec=_minimal_spec())

    paths = {t.path for t in registry.tools.values()}
    assert "/health" not in paths
    assert "/openapi.json" not in paths
    assert "/v1/factory/wip" in paths
    assert "/v1/factory/ingest" in paths


async def test_read_and_write_categorised_distinctly():
    """O GET de leitura e o POST de ingest caem em categorias diferentes."""
    registry = ToolRegistry()
    await registry.load_from_openapi(openapi_spec=_minimal_spec())

    by_path = {t.path: t for t in registry.tools.values()}
    assert by_path["/v1/factory/wip"].category == ToolCategory.DATA_READ
    assert by_path["/v1/factory/ingest"].category == ToolCategory.DATA_WRITE


async def test_base_url_defaults_to_configured_self_url():
    """O `base_url` de execução já não é a porta 8000 hardcoded."""
    registry = ToolRegistry()
    # Default vem de `settings.copilot_tool_api_base_url` (:8001 em dev).
    assert "8000" not in registry.base_url
    assert registry.base_url.startswith("http")


async def test_executor_builds_prompt_with_embedded_json_without_crash(mock_ollama):
    """O loop agêntico engata sem rebentar quando o registry tem tools.

    `TOOL_SYSTEM_PROMPT` embebe JSON literal (`{"tool_call": ...}`); o
    `str.format` antigo lia essas chavetas como campos de formato →
    `KeyError: '"tool_call"'`. O bug estava dormente só porque o
    registry carregava 0 tools e este ramo nunca corria.
    """
    from src.copilot.tool_executor import ToolExecutor

    registry = ToolRegistry()
    await registry.load_from_openapi(openapi_spec=_minimal_spec())
    assert registry.tools  # o ramo do tool-loop só engata com tools

    mock_ollama.queue_chat({"type": "ANSWER", "summary": "ok", "facts": []})
    executor = ToolExecutor(registry)
    response, tool_log = await executor.execute_with_tools(
        user_query="qual é o WIP?", model="mock",
    )
    assert response == {"type": "ANSWER", "summary": "ok", "facts": []}
    assert tool_log == []
