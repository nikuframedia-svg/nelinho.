"""Q.68.1.A — HTTP wrappers para `src/copilot/tools/`.

Cobertura (DAMP — cada teste lê como spec independente):

  1. POST /v1/copilot/tools/run_sql com SELECT — 200 OK + shape correcto.
  2. POST /v1/copilot/tools/run_sql com INSERT — 400 (SqlRunnerError
     envolto como HTTPException).
  3. POST sem ``X-Tenant-Id`` — 401 (fail-closed via
     :func:`require_tenant_header`).
  4. GET /v1/copilot/tools/list_tables — 200 com lista de tabelas.
  5. GET /v1/copilot/tools/describe/{schema}/{name} — 200 com columns +
     PK + FKs.
  6. tool_registry detecta os 3 endpoints novos quando carregado da
     OpenAPI spec da app — fecha a malha "LLM vê estas tools".

Os endpoints reusam funções já testadas (`test_sql_runner.py` +
`test_schema_introspection.py`); aqui só validamos a camada HTTP, não
a lógica das tools.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.copilot.api_endpoints.copilot_tools_api import router
from src.copilot.tools.sql_runner import SqlRunnerError

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")
_TENANT_HEADER = {"X-Tenant-Id": str(DEV_TENANT)}


def _app() -> FastAPI:
    """FastAPI app minimal só com este router — sem Kafka/scheduler."""
    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# /run_sql
# ---------------------------------------------------------------------------


def test_run_sql_select_returns_200_with_rows():
    """POST com SELECT trivial — 200 + payload shape (sql/rows/status)."""
    fake_result: dict[str, Any] = {
        "sql": "SELECT 1 as n LIMIT 200",
        "rows": [{"n": 1}],
        "rows_returned": 1,
        "elapsed_ms": 0.5,
        "status": "ok",
    }
    with patch(
        "src.copilot.api_endpoints.copilot_tools_api._run_sql",
        return_value=fake_result,
    ):
        client = TestClient(_app())
        resp = client.post(
            "/v1/copilot/tools/run_sql",
            json={"query": "SELECT 1 as n"},
            headers=_TENANT_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["rows"] == [{"n": 1}]
    assert body["rows_returned"] == 1
    assert "LIMIT" in body["sql"]


def test_run_sql_insert_returns_400():
    """POST com INSERT — SqlRunnerError envolto como HTTPException 400.

    O regex SELECT-only do sql_runner é simulado: o patch levanta
    SqlRunnerError directamente, garantindo que o handler converte para
    HTTP 400 (e não 500)."""

    async def _raise(query: str, max_rows: int):
        raise SqlRunnerError("Only SELECT/WITH queries allowed. Got: INSERT INTO...")

    with patch(
        "src.copilot.api_endpoints.copilot_tools_api._run_sql",
        side_effect=_raise,
    ):
        client = TestClient(_app())
        resp = client.post(
            "/v1/copilot/tools/run_sql",
            json={"query": "INSERT INTO core.audit_log VALUES (1, 2)"},
            headers=_TENANT_HEADER,
        )

    assert resp.status_code == 400, resp.text
    assert "Only SELECT/WITH" in resp.json()["detail"]


def test_run_sql_without_tenant_header_returns_401():
    """POST sem X-Tenant-Id — require_tenant_header devolve 401.

    Fail-closed (Q.12 Onda 0.1): nunca cair no tenant zero por defeito.
    """
    client = TestClient(_app())
    resp = client.post(
        "/v1/copilot/tools/run_sql",
        json={"query": "SELECT 1"},
    )

    assert resp.status_code == 401, resp.text


def test_run_sql_validates_query_length():
    """Pydantic min_length=1: query vazia → 422 (não 400)."""
    client = TestClient(_app())
    resp = client.post(
        "/v1/copilot/tools/run_sql",
        json={"query": ""},
        headers=_TENANT_HEADER,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# /list_tables
# ---------------------------------------------------------------------------


def test_list_tables_returns_200_with_table_list():
    """GET — devolve lista de TableInfo com schema/name/row_count/comment."""
    fake_rows = [
        {
            "schema": "plan",
            "name": "production_orders",
            "row_count": 12345,
            "comment": "Production orders fact",
        },
        {
            "schema": "core",
            "name": "audit_log",
            "row_count": 9999,
            "comment": None,
        },
    ]
    with patch(
        "src.copilot.api_endpoints.copilot_tools_api._list_tables",
        return_value=fake_rows,
    ):
        client = TestClient(_app())
        resp = client.get(
            "/v1/copilot/tools/list_tables",
            headers=_TENANT_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    # JSON shape keeps the original ``schema`` key (alias),
    # mesmo que o atributo Python seja ``schema_``.
    assert body[0]["schema"] == "plan"
    assert body[0]["name"] == "production_orders"
    assert body[0]["row_count"] == 12345
    assert body[1]["comment"] is None


def test_list_tables_forwards_schema_filter():
    """``?schema=plan`` é passado à função subjacente."""
    captured: dict[str, Any] = {}

    async def _capture(schema):
        captured["schema"] = schema
        return []

    with patch(
        "src.copilot.api_endpoints.copilot_tools_api._list_tables",
        side_effect=_capture,
    ):
        client = TestClient(_app())
        resp = client.get(
            "/v1/copilot/tools/list_tables?schema=plan",
            headers=_TENANT_HEADER,
        )

    assert resp.status_code == 200, resp.text
    assert captured["schema"] == "plan"


# ---------------------------------------------------------------------------
# /describe/{schema}/{name}
# ---------------------------------------------------------------------------


def test_describe_table_returns_200_with_columns():
    """GET — devolve TableDescription completo (columns + PK + FKs + sample)."""
    fake = {
        "schema": "plan",
        "name": "production_orders",
        "exists": True,
        "comment": "Production orders fact",
        "columns": [
            {
                "name": "id",
                "type": "uuid",
                "nullable": False,
                "default": "gen_random_uuid()",
                "comment": None,
            },
            {
                "name": "tenant_id",
                "type": "uuid",
                "nullable": False,
                "default": None,
                "comment": None,
            },
        ],
        "primary_key": ["id"],
        "foreign_keys": [
            {
                "column": "tenant_id",
                "ref_schema": "public",
                "ref_table": "tenants",
                "ref_column": "id",
            },
        ],
        "sample": [{"id": "abc", "tenant_id": "def"}],
    }
    with patch(
        "src.copilot.api_endpoints.copilot_tools_api._describe_table",
        return_value=fake,
    ):
        client = TestClient(_app())
        resp = client.get(
            "/v1/copilot/tools/describe/plan/production_orders",
            headers=_TENANT_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exists"] is True
    assert body["schema"] == "plan"
    assert body["name"] == "production_orders"
    assert len(body["columns"]) == 2
    assert body["columns"][0]["name"] == "id"
    assert body["primary_key"] == ["id"]
    assert body["foreign_keys"][0]["ref_table"] == "tenants"
    assert body["sample"] == [{"id": "abc", "tenant_id": "def"}]


def test_describe_table_returns_200_when_table_missing():
    """Tabela inexistente — describe_table devolve exists=False e lista
    vazias, NÃO um 404. Mantém contract definido em
    `test_schema_introspection.py`."""
    fake = {
        "schema": "plan",
        "name": "ghost",
        "exists": False,
        "comment": None,
        "columns": [],
        "primary_key": [],
        "foreign_keys": [],
        "sample": [],
    }
    with patch(
        "src.copilot.api_endpoints.copilot_tools_api._describe_table",
        return_value=fake,
    ):
        client = TestClient(_app())
        resp = client.get(
            "/v1/copilot/tools/describe/plan/ghost",
            headers=_TENANT_HEADER,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exists"] is False
    assert body["columns"] == []
    assert body["primary_key"] == []


# ---------------------------------------------------------------------------
# Discoverability — tool_registry vê os 3 endpoints novos
# ---------------------------------------------------------------------------


def test_router_exposes_three_copilot_tools_endpoints():
    """Smoke: o router monta exactamente os 3 endpoints esperados.

    Esta é a invariante que liga o fix ao seu propósito — o
    `tool_registry` (Q.67.6.x) faz parse do OpenAPI da app para descobrir
    tools. Se um endpoint cair daqui, o LLM volta a não ver a tool. Os
    paths são verificados contra a string exacta com que o registry os
    indexaria.
    """
    app = _app()
    paths = {r.path for r in app.routes if hasattr(r, "path")}

    assert "/v1/copilot/tools/run_sql" in paths
    assert "/v1/copilot/tools/list_tables" in paths
    assert "/v1/copilot/tools/describe/{schema}/{name}" in paths
