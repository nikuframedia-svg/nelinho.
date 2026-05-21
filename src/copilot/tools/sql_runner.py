"""SQL runner tool — Q.67.4.C.

Copilot tool que executa SELECT contra a BD e devolve as rows. Permite
ao LLM responder a perguntas como "quantas OFs estão atrasadas?" sem ter
de escrever um endpoint dedicado para cada agregação.

Defense-in-depth — 3 camadas independentes:
    1. **DB role** (`nelinho_copilot`) tem SELECT-only — aplica
       `deploy/postgres/q67_copilot_role.sql` em prod. Em dev, fallback
       para `database_url` (regex protege na mesma).
    2. **Regex SELECT-only** no `run_sql` — rejeita qualquer query que
       não começa por `SELECT` ou `WITH` (CTEs read-only).
    3. **statement_timeout** (5s default) + **LIMIT cap** (200 rows
       default) — bound time + bound memory, mesmo que a query passe
       pelas outras duas camadas.

Telemetria via structured logger (`logging.getLogger(__name__)`) — o
`TraceIdLogFilter` (Q.61.12) anexa `trace_id` automaticamente, dando
forensics se houver prompt injection bem-sucedida. O `core.audit_log`
fica reservado para mudanças de estado autoritativas (Q.66.B.1); cada
SELECT do copiloto NÃO é uma mudança de estado, é telemetria de query.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.config import get_settings

logger = logging.getLogger(__name__)

# Aceita SELECT ou WITH (CTE) com whitespace/comentário leading.
_SELECT_RE = re.compile(r"^\s*(?:SELECT|WITH)\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\bLIMIT\s+\d+\b", re.IGNORECASE)


class SqlRunnerError(Exception):
    """SQL rejeitado (não-SELECT) ou execução falhou."""


async def run_sql(query: str, max_rows: int | None = None) -> dict[str, Any]:
    """Executa um SELECT e devolve resultados.

    Args:
        query: SQL SELECT (pode começar com SELECT ou WITH).
        max_rows: cap de linhas devolvidas; LIMIT injectado se ausente.
            Default vem de `settings.copilot_sql_max_rows` (200).

    Returns:
        dict com:
            sql: str — query final executada (com LIMIT auto-injectado
                se aplicável).
            rows: list[dict] — resultados, com nomes de coluna como keys.
            rows_returned: int — len(rows).
            elapsed_ms: float — tempo de execução em ms.
            status: "ok" — confirmação de sucesso.

    Raises:
        SqlRunnerError: se a query não começa por SELECT/WITH, ou se
            execução falhou (timeout, syntax error, permission denied).
    """
    settings = get_settings()
    cap = max_rows if max_rows is not None else settings.copilot_sql_max_rows

    if not _SELECT_RE.match(query):
        # Não logamos a query completa aqui — pode ter sido prompt
        # injection com payload grande. Truncamos a 50 chars para
        # forensics sem amplificar o ataque.
        snippet = query[:50].replace("\n", " ")
        logger.warning(
            "sql_runner rejected non-SELECT query: %r", snippet,
        )
        raise SqlRunnerError(
            f"Only SELECT/WITH queries allowed. Got: {snippet}...",
        )

    # Auto-inject LIMIT se ausente — bound de memória mesmo que o
    # statement_timeout não dispare (queries rápidas mas com muitos
    # rows).
    final_query = query.rstrip().rstrip(";").rstrip()
    if not _LIMIT_RE.search(final_query):
        final_query = f"{final_query} LIMIT {cap}"

    # Engine separado: usa COPILOT_DATABASE_URL (role SELECT-only) em
    # prod; fallback para database_url em dev. AUTOCOMMIT evita
    # transaction overhead — read-only não precisa de tx.
    db_url = settings.copilot_database_url or settings.database_url
    engine = create_async_engine(db_url, isolation_level="AUTOCOMMIT")

    start = time.monotonic()
    rows: list[dict[str, Any]] = []
    try:
        async with engine.connect() as conn:
            # statement_timeout local à conexão — não polui outros
            # callers porque o engine é descartado a seguir.
            await conn.execute(
                text(
                    f"SET statement_timeout = '{settings.copilot_sql_timeout_s}s'",
                ),
            )
            result = await conn.execute(text(final_query))
            rows = [dict(r._mapping) for r in result]
        elapsed_ms = (time.monotonic() - start) * 1000
    except SqlRunnerError:
        raise
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "sql_runner execution failed after %.1fms: %s",
            elapsed_ms,
            exc,
        )
        raise SqlRunnerError(f"SQL execution failed: {exc}") from exc
    finally:
        await engine.dispose()

    # Telemetria estruturada — trace_id é injectado pelo
    # TraceIdLogFilter (Q.61.12). Não escrevemos em core.audit_log
    # porque isto não é uma mudança de estado autoritativa.
    logger.info(
        "sql_runner ok rows=%d elapsed_ms=%.1f",
        len(rows),
        elapsed_ms,
    )

    return {
        "sql": final_query,
        "rows": rows,
        "rows_returned": len(rows),
        "elapsed_ms": elapsed_ms,
        "status": "ok",
    }


__all__ = ["run_sql", "SqlRunnerError"]
