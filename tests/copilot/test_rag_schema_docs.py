"""Q.67.4.E — `src.copilot.rag.ingest_schema_docs` indexa schema docs PT-PT.

Cobre:
  * Smoke: ingest_schema_docs() devolve >0 chunks para um conjunto fake
    de tabelas (intercepta information_schema queries).
  * Idempotência: ingest_schema_docs(force=True) emite um DELETE antes
    de adicionar novos chunks; sem force apenas adiciona.
  * Retrieval: lexical search por "molde" devolve chunks que mencionam
    molde (validamos que o glossário PT-PT está embebido no chunk text).

Mantemos os testes auto-contidos via FakeSchemaDocsSession que:
  - Responde aos 2 templates de queries do `_list_schema_tables` /
    `_list_table_columns` (detectados por substring "information_schema.tables"
    vs "information_schema.columns") com fixtures determinísticas.
  - Captura chamadas a `delete()` (statement objects do SQLAlchemy core).
  - Captura `add()` para introspecção das linhas `CopilotRAGChunk` criadas.

`get_embeddings` é monkey-patched para devolver um vector dummy de
dimensão 768 — evita dependência de Ollama em CI.
"""

from __future__ import annotations

from typing import Any, List, Tuple
from uuid import UUID

import pytest
from sqlalchemy.sql import Delete

from src.copilot import rag as rag_module
from src.copilot.models import CopilotRAGChunk
from src.copilot.rag import (
    SCHEMA_DOCS_SOURCE_TYPE,
    _build_schema_chunk_text,
    _matching_glossary_terms,
    ingest_schema_docs,
)

_TENANT = UUID("00000000-0000-0000-0000-000000000001")

# Fixtures de tabelas — usamos schemas reais do nelinho para que os
# termos do glossário batam (ex.: "molde" em quality.molde_health).
FAKE_TABLES: List[Tuple[str, str, str | None]] = [
    ("plan", "production_order", "Ordem de fabrico (OF) — 14.7/dia média NELO"),
    ("quality", "molde_health", "Saúde de cada molde de laminagem"),
    ("supply", "warehouse_stock", "Stock real espelhado da ERP"),
]

FAKE_COLUMNS: dict[Tuple[str, str], List[Tuple[str, str, str | None]]] = {
    ("plan", "production_order"): [
        ("id", "uuid", "PK"),
        ("tenant_id", "uuid", "multi-tenant"),
        ("phase", "varchar", "fase de produção (41 fases NELO)"),
    ],
    ("quality", "molde_health"): [
        ("molde_id", "uuid", "FK para o molde de laminagem"),
        ("pocket_count", "integer", "número de barcos em paralelo"),
        ("trust", "float", "trust_index 0-1 do molde"),
    ],
    ("supply", "warehouse_stock"): [
        ("sku", "varchar", "código de material"),
        ("qty", "numeric", "quantidade em armazém"),
    ],
}


class _FakeResult:
    def __init__(self, rows: List[Tuple[Any, ...]]) -> None:
        self._rows = rows

    def all(self) -> List[Tuple[Any, ...]]:
        return list(self._rows)


class FakeSchemaDocsSession:
    """Fake AsyncSession que serve as 2 queries SQL + captura add/delete.

    Permite testar `ingest_schema_docs` sem Postgres real.
    """

    def __init__(self) -> None:
        self.added: List[Any] = []
        self.deletes_issued: List[Delete] = []
        self.flush_calls = 0
        self.commit_calls = 0

    async def execute(self, stmt: Any, params: dict | None = None) -> Any:
        # 1) DELETE — capturamos para verificar idempotência.
        if isinstance(stmt, Delete):
            self.deletes_issued.append(stmt)
            return _FakeResult([])

        # 2) text() para information_schema. Inspeccionamos o SQL.
        sql_str = str(stmt).lower()
        if "information_schema.tables" in sql_str:
            return _FakeResult(FAKE_TABLES)
        if "information_schema.columns" in sql_str:
            schema = (params or {}).get("schema")
            table = (params or {}).get("table")
            cols = FAKE_COLUMNS.get((schema, table), [])
            return _FakeResult(cols)

        return _FakeResult([])

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


@pytest.fixture
def patch_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Substitui get_embeddings por um stub que devolve vector dummy."""

    async def _fake_embeddings(text: str, model: str | None = None) -> List[float]:
        return [0.1] * 768

    monkeypatch.setattr(rag_module, "get_embeddings", _fake_embeddings)


# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------


def _chunks_added(session: FakeSchemaDocsSession) -> List[CopilotRAGChunk]:
    return [obj for obj in session.added if isinstance(obj, CopilotRAGChunk)]


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_schema_docs_returns_positive_chunk_count(
    patch_embeddings: None,
) -> None:
    """Smoke: ingest_schema_docs devolve >0 chunks e cria 1 por tabela."""
    session = FakeSchemaDocsSession()
    n = await ingest_schema_docs(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        force=False,
    )

    assert n > 0, "esperava pelo menos 1 chunk indexado"
    assert n == len(FAKE_TABLES), (
        f"1 chunk por tabela: esperava {len(FAKE_TABLES)}, obtive {n}"
    )

    chunks = _chunks_added(session)
    assert len(chunks) == len(FAKE_TABLES)
    for chunk in chunks:
        assert chunk.tenant_id == _TENANT
        assert chunk.source_type == SCHEMA_DOCS_SOURCE_TYPE
        assert chunk.source_id  # "schema.table"
        assert "." in chunk.source_id
        assert chunk.chunk_text  # não vazio


@pytest.mark.asyncio
async def test_ingest_schema_docs_force_emits_delete_first(
    patch_embeddings: None,
) -> None:
    """force=True apaga chunks anteriores antes de reingerir."""
    # 1ª passagem — sem force, nenhum delete.
    session1 = FakeSchemaDocsSession()
    await ingest_schema_docs(
        session=session1,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        force=False,
    )
    assert session1.deletes_issued == []

    # 2ª passagem — com force, 1 delete antes dos novos chunks.
    session2 = FakeSchemaDocsSession()
    await ingest_schema_docs(
        session=session2,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        force=True,
    )
    assert len(session2.deletes_issued) == 1, (
        "force=True deve emitir exactamente 1 DELETE"
    )

    # Os chunks novos foram adicionados depois do DELETE.
    chunks = _chunks_added(session2)
    assert len(chunks) == len(FAKE_TABLES)
    for chunk in chunks:
        assert chunk.source_type == SCHEMA_DOCS_SOURCE_TYPE


@pytest.mark.asyncio
async def test_chunk_text_for_molde_mentions_glossary_term(
    patch_embeddings: None,
) -> None:
    """Search lexical por "molde" devolve chunks que mencionam molde.

    Validamos:
      1. O builder `_build_schema_chunk_text` injecta termos do glossário
         quando o nome de tabela/coluna bate.
      2. O chunk gravado para `quality.molde_health` menciona "molde" no
         texto (lexical search recuperaria via ILIKE %molde%).
    """
    # (1) Termos do glossário detectados directamente.
    terms = _matching_glossary_terms("quality molde_health molde_id pocket_count")
    assert any("molde" in t.lower() for t in terms), terms

    # (2) Texto gravado contém "molde" — fim a fim via ingest.
    session = FakeSchemaDocsSession()
    await ingest_schema_docs(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        force=False,
    )
    chunks = _chunks_added(session)
    molde_chunks = [c for c in chunks if "molde" in c.chunk_text.lower()]
    assert molde_chunks, "esperava pelo menos 1 chunk a mencionar 'molde'"

    # E o chunk da tabela quality.molde_health deve estar lá com o
    # template PT-PT esperado.
    assert any(c.source_id == "quality.molde_health" for c in molde_chunks)
    target = next(c for c in molde_chunks if c.source_id == "quality.molde_health")
    # Template "<schema>.<table> — <descrição>. Colunas: ...".
    assert target.chunk_text.startswith("quality.molde_health — ")
    assert "Colunas:" in target.chunk_text
    assert "Termos:" in target.chunk_text


@pytest.mark.asyncio
async def test_chunk_text_builder_handles_missing_comments() -> None:
    """Builder PT-PT é resiliente a colunas/tabelas sem comment.

    Defesa: as 17 schemas em dev nem sempre têm `COMMENT ON TABLE` —
    o chunk continua a ser válido com placeholder.
    """
    body = _build_schema_chunk_text(
        schema="dqa",
        table="empty_table",
        table_comment=None,
        columns=[("id", "uuid", None)],
    )
    assert "dqa.empty_table" in body
    assert "sem descrição" in body
    assert "id: uuid" in body
    # Nenhum termo aplicável → "n/a"
    assert "Termos: n/a" in body
