"""Q.39 — exploração SQL read-only para o copiloto.

Dá ao LLM um caminho guardado para consultar a base de dados **toda** —
o Postgres do sistema (`prodplan_one`) E o ERP NELO ao vivo
(`MAR-KAYAKS`, SQL Server) — em vez de só os readers fixos.

Duas bases, um contrato:

* ``postgres`` — a BD do sistema (`factory_curated`, `plan`, `quality`,
  `core`, …). Consultada numa transacção ``READ ONLY`` com
  ``statement_timeout``.
* ``erp`` — o SQL Server MAR-KAYAKS. O login do adaptador é *DataReader*
  (só leitura ao nível do servidor); acrescenta-se ``TOP`` e o timeout
  de query do adaptador.

**Tudo aqui é read-only por construção.** :func:`validate_readonly_sql`
rejeita tudo o que não seja uma única instrução ``SELECT`` / ``WITH`` —
sem ``INSERT``/``UPDATE``/``DELETE``/DDL, sem encadear com ``;``. As
travões de DB (transacção READ ONLY no Postgres, DataReader no ERP) são
a segunda linha de defesa: mesmo que o regex falhasse, a escrita era
recusada pela base.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

# Fontes válidas — o LLM escolhe uma destas.
VALID_SOURCES = ("postgres", "erp")

# Tecto de linhas devolvidas ao LLM. Suficiente para responder a uma
# pergunta sem inundar o contexto; o resto é truncado com aviso.
DEFAULT_MAX_ROWS = 100

# Timeout do Postgres por query (ms). O ERP herda o
# `sqlserver_query_timeout_s` do adaptador.
_PG_STATEMENT_TIMEOUT_MS = 8000

# Schemas internos do Postgres que nunca interessam ao LLM.
_PG_SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")

# Palavras que NÃO podem aparecer numa query read-only. Defense-in-depth:
# o Postgres já corre em transacção READ ONLY e o ERP é DataReader, mas
# uma query que tente escrever é recusada já aqui, com mensagem clara.
# `replace` ficou de fora de propósito — `REPLACE()` é uma função de
# string legítima; `CREATE OR REPLACE` é apanhado pelo `create`.
_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|grant|revoke|"
    r"exec|execute|merge|call|create|copy|into|"
    r"waitfor|shutdown|dbcc|reconfigure|"
    r"sp_\w+|xp_\w+|pg_sleep|pg_read_file|pg_ls_dir"
    r")\b",
    re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    """A query proposta não é um SELECT read-only seguro."""


def _json_safe(value: Any) -> Any:
    """Coage um valor de célula da BD para algo JSON-serializável.

    As linhas devolvidas vão parar a `json.dumps` (prompt de composição
    e audit trail). Datas, `Decimal`, `UUID` e `bytes` rebentavam o dump
    — daí esta coerção no ponto de leitura, para o resultado ser sempre
    seguro a jusante.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return str(value)


def validate_readonly_sql(sql: str) -> str:
    """Valida que ``sql`` é uma única query read-only e devolve-a limpa.

    Levanta :class:`UnsafeQueryError` com uma mensagem em PT-PT quando a
    query escreve, encadeia instruções, ou não começa por
    ``SELECT``/``WITH``.
    """
    if not sql or not sql.strip():
        raise UnsafeQueryError("query vazia")

    # Remover comentários (-- linha  e  /* bloco */) antes de validar —
    # senão escondia-se uma instrução proibida dentro de um comentário.
    cleaned = re.sub(r"--[^\n]*", " ", sql)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().rstrip(";").strip()

    if not cleaned:
        raise UnsafeQueryError("query vazia depois de remover comentários")

    # Uma só instrução — um `;` no meio é encadeamento.
    if ";" in cleaned:
        raise UnsafeQueryError(
            "só é permitida UMA instrução SELECT (sem ';' a encadear)"
        )

    low = cleaned.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise UnsafeQueryError(
            "só são permitidas queries de leitura (SELECT ou WITH … SELECT)"
        )

    match = _FORBIDDEN.search(cleaned)
    if match:
        raise UnsafeQueryError(
            f"palavra proibida numa query read-only: '{match.group(0)}'"
        )

    return cleaned


# ─── catálogo de schema ─────────────────────────────────────────────────


async def list_schema(source: str) -> List[Dict[str, Any]]:
    """Catálogo de tabelas de ``source``: ``{schema, table, rows}``.

    É o "mapa" que o LLM lê para saber o que existe antes de escrever
    SQL. Ordenado por nº de linhas desc (as tabelas com mais dados
    primeiro).
    """
    if source == "postgres":
        return await _list_schema_postgres()
    if source == "erp":
        return await _list_schema_erp()
    raise ValueError(f"source inválida: {source!r}")


async def _list_schema_postgres() -> List[Dict[str, Any]]:
    from sqlalchemy import text

    from src.shared.database import async_session_factory

    sql = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           COALESCE(s.n_live_tup, 0) AS rows
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
    WHERE c.relkind IN ('r', 'p')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    ORDER BY rows DESC, schema_name, table_name
    """
    async with async_session_factory() as session:
        result = await session.execute(text(sql))
        return [
            {"schema": r.schema_name, "table": r.table_name, "rows": int(r.rows)}
            for r in result
        ]


async def _list_schema_erp() -> List[Dict[str, Any]]:
    from src.adapters.nelo import services

    sql = """
    SELECT s.name AS schema_name, t.name AS table_name, p.rows AS row_count
    FROM sys.tables t
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    INNER JOIN sys.partitions p
        ON p.object_id = t.object_id AND p.index_id IN (0, 1)
    WHERE t.is_ms_shipped = 0
    ORDER BY p.rows DESC, s.name, t.name
    """
    rows = await services._fetch_all(sql)
    return [
        {
            "schema": r["schema_name"],
            "table": r["table_name"],
            "rows": int(r["row_count"] or 0),
        }
        for r in rows
    ]


def _norm(text: str) -> str:
    """Minúsculas, sem acentos, só alfanumérico separado por espaço."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


def _token_match(a: str, b: str) -> bool:
    """Dois tokens casam por prefixo (≥4 chars) — apanha plurais
    (`batch`↔`batches`, `template`↔`templates`)."""
    if len(a) < 4 or len(b) < 4:
        return a == b
    return a.startswith(b) or b.startswith(a)


async def lexical_table_match(
    question: str,
) -> Tuple[Optional[str], List[str]]:
    """Rede de segurança quando o LLM não consegue escolher tabelas.

    Faz correspondência léxica entre as palavras da pergunta e os nomes
    das tabelas — apanha exactamente o caso em que o utilizador escreve
    o nome técnico da tabela (`production_schedules`, `transport
    batches`). Devolve ``(source, tables)`` ou ``(None, [])``.
    """
    q_tokens = set(_norm(question).split())
    if not q_tokens:
        return None, []
    for source in ("postgres", "erp"):
        hits: List[str] = []
        try:
            catalog = await list_schema(source)
        except Exception:
            continue
        for t in catalog:
            name_tokens = [
                tok for tok in _norm(t["table"]).split() if len(tok) >= 3
            ]
            if not name_tokens:
                continue
            # Casa quando TODOS os tokens do nome da tabela aparecem na
            # pergunta — estrito o suficiente para não casar por acaso.
            if all(
                any(_token_match(nt, qt) for qt in q_tokens)
                for nt in name_tokens
            ):
                hits.append(f"{t['schema']}.{t['table']}")
        if hits:
            return source, hits[:6]
    return None, []


async def describe_tables(
    source: str, tables: List[str],
) -> Dict[str, List[Dict[str, str]]]:
    """Colunas (nome + tipo) das ``tables`` pedidas.

    ``tables`` aceita ``"schema.tabela"`` ou só ``"tabela"``. Devolve
    ``{nome_qualificado: [{"col", "tipo"}, …]}``. Tabelas inexistentes
    saem com lista vazia (o caller decide se isso é fatal).
    """
    if source == "postgres":
        return await _describe_postgres(tables)
    if source == "erp":
        return await _describe_erp(tables)
    raise ValueError(f"source inválida: {source!r}")


async def _describe_postgres(
    tables: List[str],
) -> Dict[str, List[Dict[str, str]]]:
    from sqlalchemy import text

    from src.shared.database import async_session_factory

    out: Dict[str, List[Dict[str, str]]] = {}
    async with async_session_factory() as session:
        for raw in tables:
            schema, _, table = raw.rpartition(".")
            params: Dict[str, Any] = {"table": table}
            schema_clause = ""
            if schema:
                schema_clause = "AND table_schema = :schema"
                params["schema"] = schema
            sql = text(
                f"""
                SELECT table_schema, column_name, data_type
                FROM information_schema.columns
                WHERE table_name = :table {schema_clause}
                ORDER BY ordinal_position
                """
            )
            result = await session.execute(sql, params)
            out[raw] = [
                {"col": r.column_name, "tipo": r.data_type}
                for r in result
            ]
    return out


async def _describe_erp(
    tables: List[str],
) -> Dict[str, List[Dict[str, str]]]:
    from src.adapters.nelo import services

    out: Dict[str, List[Dict[str, str]]] = {}
    for raw in tables:
        schema, _, table = raw.rpartition(".")
        obj = f"{schema}.{table}" if schema else f"dbo.{table}"
        rows = await services._fetch_all(
            """
            SELECT c.name AS col, ty.name AS tipo
            FROM sys.columns c
            INNER JOIN sys.types ty
                ON ty.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(:obj)
            ORDER BY c.column_id
            """,
            {"obj": obj},
        )
        out[raw] = [{"col": r["col"], "tipo": r["tipo"]} for r in rows]
    return out


# ─── execução ───────────────────────────────────────────────────────────


async def run_query(
    source: str,
    sql: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> Dict[str, Any]:
    """Executa uma query read-only e devolve as linhas.

    Devolve ``{"columns": [...], "rows": [[...], ...], "row_count": int,
    "truncated": bool}``. ``sql`` é validado por
    :func:`validate_readonly_sql` antes de tocar na base.
    """
    cleaned = validate_readonly_sql(sql)
    if source == "postgres":
        return await _run_postgres(cleaned, max_rows)
    if source == "erp":
        return await _run_erp(cleaned, max_rows)
    raise ValueError(f"source inválida: {source!r}")


async def _run_postgres(sql: str, max_rows: int) -> Dict[str, Any]:
    from src.shared.database import engine

    # Ligação dedicada — uma query do LLM que rebente não pode envenenar
    # a sessão do copiloto (o audit é escrito a seguir, noutra sessão).
    async with engine.connect() as conn:
        # READ ONLY na transacção: a base recusa qualquer escrita mesmo
        # que o regex de validação tivesse falhado.
        await conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        await conn.exec_driver_sql(
            f"SET statement_timeout = {_PG_STATEMENT_TIMEOUT_MS}"
        )
        result = await conn.exec_driver_sql(sql)
        columns = list(result.keys())
        fetched = result.fetchmany(max_rows + 1)

    truncated = len(fetched) > max_rows
    rows = [[_json_safe(c) for c in r] for r in fetched[:max_rows]]
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }


async def _run_erp(sql: str, max_rows: int) -> Dict[str, Any]:
    from src.adapters.nelo import services

    # Forçar um tecto de linhas no servidor: injectar `TOP n` logo a
    # seguir ao `SELECT` inicial. MAS só quando a query ainda não tem um
    # `TOP` — senão ficava `SELECT TOP 101 TOP 5 …` (SQL inválido). Se o
    # LLM já pôs o seu `TOP`, respeita-se; o tecto real é garantido na
    # leitura (`rows[:max_rows]`). Queries `WITH` não são tocadas — ficam
    # limitadas pelo `fetchmany` + o timeout de 30s do adaptador.
    already_capped = re.match(
        r"(?is)\s*select\s+(distinct\s+|all\s+)?top\s", sql,
    )
    if already_capped:
        capped = sql
    else:
        capped = re.sub(
            r"(?is)^\s*select\s+(distinct\s+|all\s+)?",
            lambda m: m.group(0) + f"TOP {max_rows + 1} ",
            sql,
            count=1,
        )
    rows = await services._fetch_all(capped)
    columns = list(rows[0].keys()) if rows else []
    truncated = len(rows) > max_rows
    data = [
        [_json_safe(row[c]) for c in columns] for row in rows[:max_rows]
    ]
    return {
        "columns": columns,
        "rows": data,
        "row_count": len(data),
        "truncated": truncated,
    }


__all__ = [
    "DEFAULT_MAX_ROWS",
    "VALID_SOURCES",
    "UnsafeQueryError",
    "describe_tables",
    "lexical_table_match",
    "list_schema",
    "run_query",
    "validate_readonly_sql",
]
