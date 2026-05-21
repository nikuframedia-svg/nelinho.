"""Schema introspection tools — Q.67.4.B.

Two tools that the copilot LLM calls to discover the live database schema:

  * :func:`list_database_tables` — lists tables in the current DB (with row
    estimates and ``COMMENT ON TABLE``), optionally filtered by schema.
  * :func:`describe_table` — returns columns + types + nullable + defaults
    + PK + FKs + a 3-row sample for a given table.

Design notes
------------

* **No new engine** — we reuse :data:`src.shared.database.engine` (the
  module-level ``AsyncEngine``). The Q.67.4.B spec called this
  ``get_engine()`` but the canonical export in ``src/shared/database.py``
  is the engine instance itself; importing it lazily avoids loading the
  whole settings chain at module import time (useful for tests that
  monkeypatch the engine).

* **PII masking** — if a column's ``COMMENT ON COLUMN`` contains the
  substring ``sensitive`` or ``pii`` (case-insensitive), the sample rows
  emit ``"***"`` instead of the real value. The column metadata still
  surfaces so the LLM knows the column exists — only the values are
  redacted. ``COMMENT`` is the policy carrier; no separate registry.

* **Cache** — :func:`list_database_tables` caches per-``schema`` key for
  1 hour (TTL ``_CACHE_TTL_SECONDS``). The cache is a simple in-process
  dict keyed by the ``schema`` argument (``""`` when ``None``). Cache
  invalidation is purely time-based: schemas don't churn in nelinho
  (Alembic migrations on deploy), and a 1h staleness window is
  acceptable for the LLM use case (it sees a schema list with at most 1h
  of lag — operator can always call again to force a fresh read if
  they suspect drift, but only after expiry).

* **Errors** — :func:`describe_table` on an unknown table returns a
  dict with ``exists=False`` and empty collections rather than raising.
  Raising would force the LLM dispatcher to wrap every call in a
  try/except; the dict shape is easier to reason about from the
  prompt side ("if exists is False, the table is gone").
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache (process-local, 1h TTL)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 3600  # 1h
_table_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}

# Schemas that we expose to the LLM. ``pg_catalog`` and
# ``information_schema`` are infrastructure — listing them would only
# add noise.
_HIDDEN_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")


def _cache_key(schema: Optional[str]) -> str:
    return schema or "__all__"


def _cache_clear() -> None:
    """Clear the internal cache. Exported for tests; not part of the
    LLM-visible surface."""
    _table_cache.clear()


# ---------------------------------------------------------------------------
# Tool 1 — list_database_tables
# ---------------------------------------------------------------------------


async def list_database_tables(
    schema: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List user tables in the database with row estimates and table
    comments.

    Parameters
    ----------
    schema:
        Restrict to a single Postgres schema (e.g. ``"plan"``). When
        ``None`` (the default) all non-system schemas are returned.

    Returns
    -------
    list of dict
        Each dict has the shape::

            {
                "schema": "plan",
                "name":   "production_orders",
                "row_count": 123456,   # pg_class.reltuples estimate
                "comment": "Production orders fact table",  # or None
            }

    The result is cached per ``schema`` argument for 1 hour.
    """
    key = _cache_key(schema)
    now = time.monotonic()
    cached = _table_cache.get(key)
    if cached is not None:
        cached_at, rows = cached
        if (now - cached_at) < _CACHE_TTL_SECONDS:
            return rows

    # Lazy import — avoids loading settings at module import time, which
    # is what lets tests monkeypatch the engine before the first call.
    from src.shared.database import engine

    # `_HIDDEN_SCHEMAS` is a constant — interpolating it directly into
    # the SQL string keeps the query plan trivial; ``:schema`` is the
    # only user-influenced parameter and is bound safely.
    hidden_sql = ", ".join(f"'{s}'" for s in _HIDDEN_SCHEMAS)
    sql = text(
        f"""
        SELECT
            s.nspname                        AS schema,
            c.relname                        AS name,
            c.reltuples::bigint              AS row_count,
            d.description                    AS comment
        FROM pg_class c
        JOIN pg_namespace s ON c.relnamespace = s.oid
        LEFT JOIN pg_description d
               ON d.objoid = c.oid AND d.objsubid = 0
        WHERE c.relkind = 'r'
          AND s.nspname NOT IN ({hidden_sql})
          AND (CAST(:schema AS TEXT) IS NULL OR s.nspname = :schema)
        ORDER BY s.nspname, c.relname
        """
    )

    async with engine.connect() as conn:
        result = await conn.execute(sql, {"schema": schema})
        rows = [
            {
                "schema": row.schema,
                "name": row.name,
                "row_count": int(row.row_count or 0),
                "comment": row.comment,
            }
            for row in result
        ]

    _table_cache[key] = (now, rows)
    return rows


# ---------------------------------------------------------------------------
# Tool 2 — describe_table
# ---------------------------------------------------------------------------


_PII_MARKERS = ("sensitive", "pii")
_PII_PLACEHOLDER = "***"


def _is_pii_comment(comment: Optional[str]) -> bool:
    if not comment:
        return False
    lowered = comment.lower()
    return any(marker in lowered for marker in _PII_MARKERS)


def _mask_sample_row(
    row: Dict[str, Any], pii_columns: set[str],
) -> Dict[str, Any]:
    if not pii_columns:
        return row
    return {
        col: (_PII_PLACEHOLDER if col in pii_columns else val)
        for col, val in row.items()
    }


async def describe_table(schema: str, name: str) -> Dict[str, Any]:
    """Describe a single table: columns, PK, FKs, comment, sample rows.

    Parameters
    ----------
    schema:
        Postgres schema name (e.g. ``"plan"``).
    name:
        Table name (e.g. ``"production_orders"``).

    Returns
    -------
    dict
        ::

            {
                "schema": "plan",
                "name":   "production_orders",
                "exists": True,
                "comment": "...",         # COMMENT ON TABLE or None
                "columns": [
                    {
                        "name":     "id",
                        "type":     "uuid",
                        "nullable": False,
                        "default":  "gen_random_uuid()",
                        "comment":  None,
                    },
                    ...
                ],
                "primary_key": ["id"],
                "foreign_keys": [
                    {"column": "tenant_id",
                     "ref_schema": "public",
                     "ref_table":  "tenants",
                     "ref_column": "id"},
                    ...
                ],
                "sample": [ { ... up to 3 rows ... } ],
            }

        For unknown tables, ``exists`` is ``False`` and ``columns`` /
        ``primary_key`` / ``foreign_keys`` / ``sample`` are empty.

    Sample rows for columns whose ``COMMENT ON COLUMN`` contains
    ``sensitive`` or ``pii`` (case-insensitive) are masked with
    ``"***"`` — the column itself is still listed.
    """
    from src.shared.database import engine

    empty: Dict[str, Any] = {
        "schema": schema,
        "name": name,
        "exists": False,
        "comment": None,
        "columns": [],
        "primary_key": [],
        "foreign_keys": [],
        "sample": [],
    }

    async with engine.connect() as conn:
        # 1. Table existence + table-level comment.
        table_row = (
            await conn.execute(
                text(
                    """
                    SELECT c.oid AS oid, d.description AS comment
                    FROM pg_class c
                    JOIN pg_namespace s ON c.relnamespace = s.oid
                    LEFT JOIN pg_description d
                           ON d.objoid = c.oid AND d.objsubid = 0
                    WHERE c.relkind = 'r'
                      AND s.nspname = :schema
                      AND c.relname = :name
                    """
                ),
                {"schema": schema, "name": name},
            )
        ).first()

        if table_row is None:
            logger.info(
                "describe_table: table %s.%s not found", schema, name,
            )
            return empty

        table_comment = table_row.comment

        # 2. Columns + per-column comment.
        col_result = await conn.execute(
            text(
                """
                SELECT
                    c.column_name                                AS name,
                    c.data_type                                  AS data_type,
                    c.udt_name                                   AS udt,
                    c.is_nullable                                AS is_nullable,
                    c.column_default                             AS default,
                    pgd.description                              AS comment,
                    c.ordinal_position                           AS pos
                FROM information_schema.columns c
                LEFT JOIN pg_catalog.pg_statio_all_tables st
                       ON st.schemaname = c.table_schema
                      AND st.relname    = c.table_name
                LEFT JOIN pg_catalog.pg_description pgd
                       ON pgd.objoid = st.relid
                      AND pgd.objsubid = c.ordinal_position
                WHERE c.table_schema = :schema
                  AND c.table_name   = :name
                ORDER BY c.ordinal_position
                """
            ),
            {"schema": schema, "name": name},
        )
        columns: List[Dict[str, Any]] = []
        pii_columns: set[str] = set()
        for row in col_result:
            # Postgres exposes USER-DEFINED types via ``udt_name``; the
            # ``data_type`` column gives "USER-DEFINED" or "ARRAY" for
            # them which isn't useful to the LLM. Prefer the udt name
            # when ``data_type`` is uninformative.
            dtype = row.data_type
            if dtype in {"USER-DEFINED", "ARRAY"} and row.udt:
                dtype = row.udt
            col_info = {
                "name": row.name,
                "type": dtype,
                "nullable": row.is_nullable == "YES",
                "default": row.default,
                "comment": row.comment,
            }
            if _is_pii_comment(row.comment):
                pii_columns.add(row.name)
            columns.append(col_info)

        # 3. Primary key columns.
        pk_result = await conn.execute(
            text(
                """
                SELECT kcu.column_name AS name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema    = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema    = :schema
                  AND tc.table_name      = :name
                ORDER BY kcu.ordinal_position
                """
            ),
            {"schema": schema, "name": name},
        )
        primary_key = [row.name for row in pk_result]

        # 4. Foreign keys.
        fk_result = await conn.execute(
            text(
                """
                SELECT
                    kcu.column_name    AS column,
                    ccu.table_schema   AS ref_schema,
                    ccu.table_name     AS ref_table,
                    ccu.column_name    AS ref_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema    = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema    = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema    = :schema
                  AND tc.table_name      = :name
                ORDER BY kcu.ordinal_position
                """
            ),
            {"schema": schema, "name": name},
        )
        foreign_keys = [
            {
                "column": row.column,
                "ref_schema": row.ref_schema,
                "ref_table": row.ref_table,
                "ref_column": row.ref_column,
            }
            for row in fk_result
        ]

        # 5. Sample (3 rows). The schema/name pair has already been
        # confirmed to exist in pg_class above, so it's not attacker-
        # supplied junk — but we still hard-escape any embedded double
        # quotes before interpolating into the identifier-quoted SQL.
        safe_schema = schema.replace('"', '""')
        safe_name = name.replace('"', '""')
        sample_sql = (
            f'SELECT * FROM "{safe_schema}"."{safe_name}" LIMIT 3'
        )
        try:
            sample_result = await conn.execute(text(sample_sql))
            raw_rows = [dict(row._mapping) for row in sample_result]
        except Exception as exc:
            # Sampling failures (RLS rejection, exotic types) shouldn't
            # blow up the whole introspection — log and keep going.
            logger.warning(
                "describe_table: sample SELECT failed for %s.%s: %s",
                schema, name, exc,
            )
            raw_rows = []

        sample = [_mask_sample_row(row, pii_columns) for row in raw_rows]

    return {
        "schema": schema,
        "name": name,
        "exists": True,
        "comment": table_comment,
        "columns": columns,
        "primary_key": primary_key,
        "foreign_keys": foreign_keys,
        "sample": sample,
    }


__all__ = [
    "describe_table",
    "list_database_tables",
]
