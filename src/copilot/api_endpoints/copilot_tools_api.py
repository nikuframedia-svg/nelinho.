"""Q.68.1.A — HTTP wrappers para `src/copilot/tools/` (sql_runner + schema_introspection).

Auditoria C1 (Q.68.1): as funções nativas Python em
`src.copilot.tools.sql_runner.run_sql` e
`src.copilot.tools.schema_introspection.{list_database_tables,describe_table}`
existem desde Q.67.4 mas são órfãs — não há referência nelas em
`src/copilot/tool_registry.py`, logo o LLM nunca as chama. O Q.68.A live
smoke confirmou: das 14 "hits" registadas, ZERO foram tool calls; foram
todas o LLM a ler o context_builder snapshot.

Fix (Opção A do design Phase 1): expor cada função como um endpoint HTTP
neste módulo. O `tool_registry` (Q.67.6.x) faz parse do OpenAPI da app
em runtime e descobre automaticamente novos endpoints — sem mudanças ao
`tool_executor`, sem mudanças ao registry. O LLM passa a vê-las como
tools "run_sql" / "list_database_tables" / "describe_table" via
function-calling normal.

Naming
------
O ficheiro chama-se ``copilot_tools_api.py`` (não ``tools_api.py``)
porque já existe um ``api_endpoints/tools_api.py`` que expõe
``/v1/tools/*`` (registry browsing endpoints). Diferentes prefixes,
mesmo nome de ficheiro seria um conflito de import — separamos.

Segurança
---------
Todos os endpoints exigem ``X-Tenant-Id`` via
:func:`require_tenant_header` (Q.12 Onda 0.1). O ``sql_runner`` já tem 3
camadas de defesa internas (regex SELECT-only + statement_timeout + LIMIT
cap); aqui só validamos input shape e re-empacotamos o
:class:`SqlRunnerError` num 400 limpo.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.copilot.tools.schema_introspection import (
    describe_table as _describe_table,
)
from src.copilot.tools.schema_introspection import (
    list_database_tables as _list_tables,
)
from src.copilot.tools.sql_runner import SqlRunnerError, run_sql as _run_sql
from src.shared.auth.headers import require_tenant_header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/copilot/tools", tags=["copilot-tools"])


# ---------------------------------------------------------------------------
# /run_sql — execute SELECT/WITH
# ---------------------------------------------------------------------------


class RunSqlRequest(BaseModel):
    """Input para :func:`run_sql_endpoint`.

    ``max_rows`` é capped a 10 000 mesmo que o caller peça mais — o
    sql_runner já injecta LIMIT, mas validamos aqui também para falhar
    early com 422 em vez de truncar silenciosamente.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="SELECT or WITH (CTE) SQL query. INSERT/UPDATE/DELETE/DDL rejected.",
    )
    max_rows: int = Field(
        default=200,
        ge=1,
        le=10_000,
        description="Cap on rows returned. LIMIT injected if absent.",
    )


class RunSqlResponse(BaseModel):
    sql: str = Field(..., description="Final executed query (with LIMIT injected).")
    rows: list[dict[str, Any]]
    rows_returned: int
    elapsed_ms: float
    status: str


@router.post(
    "/run_sql",
    response_model=RunSqlResponse,
    summary="Execute a read-only SQL query",
    description=(
        "Execute SELECT or WITH (CTE) against the live DB. Defense-in-depth: "
        "regex SELECT-only + statement_timeout + LIMIT cap. INSERT/UPDATE/DELETE/DDL "
        "rejected with 400."
    ),
)
async def run_sql_endpoint(
    request: RunSqlRequest,
    tenant_id: UUID = Depends(require_tenant_header),
) -> RunSqlResponse:
    """Run a SELECT/WITH query via the sql_runner tool."""
    try:
        result = await _run_sql(request.query, request.max_rows)
    except SqlRunnerError as exc:
        # SELECT-only rejection or execution failure — 400, not 500.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunSqlResponse(**result)


# ---------------------------------------------------------------------------
# /list_tables — discover schema
# ---------------------------------------------------------------------------


class TableInfo(BaseModel):
    # ``schema_`` instead of ``schema`` to avoid shadowing the Pydantic
    # built-in attribute. ``alias="schema"`` keeps the JSON shape stable
    # for the LLM (it sees the key it expects).
    schema_: str = Field(..., alias="schema")
    name: str
    row_count: int
    comment: Optional[str] = None

    model_config = {"populate_by_name": True}


@router.get(
    "/list_tables",
    response_model=list[TableInfo],
    summary="List database tables",
    description=(
        "List user tables with row count estimates and ``COMMENT ON TABLE``. "
        "Filter by schema name with ``?schema=plan``. Cached 1h."
    ),
)
async def list_tables_endpoint(
    schema: Optional[str] = None,
    tenant_id: UUID = Depends(require_tenant_header),
) -> list[TableInfo]:
    """List tables via :func:`list_database_tables`."""
    rows = await _list_tables(schema)
    return [TableInfo(**row) for row in rows]


# ---------------------------------------------------------------------------
# /describe/{schema}/{name} — column-level introspection
# ---------------------------------------------------------------------------


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None
    comment: Optional[str] = None


class ForeignKeyInfo(BaseModel):
    column: str
    ref_schema: str
    ref_table: str
    ref_column: str


class TableDescription(BaseModel):
    schema_: str = Field(..., alias="schema")
    name: str
    exists: bool
    comment: Optional[str] = None
    columns: list[ColumnInfo] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)
    sample: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


@router.get(
    "/describe/{schema}/{name}",
    response_model=TableDescription,
    summary="Describe a table",
    description=(
        "Return columns + types + PK + FKs + 3-row sample. PII columns "
        "(``COMMENT`` containing 'sensitive' or 'pii') are masked in the sample."
    ),
)
async def describe_table_endpoint(
    schema: str,
    name: str,
    tenant_id: UUID = Depends(require_tenant_header),
) -> TableDescription:
    """Describe a single table via :func:`describe_table`."""
    result = await _describe_table(schema, name)
    return TableDescription(**result)


__all__ = ["router"]
