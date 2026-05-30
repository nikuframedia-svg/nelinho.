"""Q.108.L.2 — view `marts.v_copilot_rag_dia`.

RAG hit rate (% requests com chunks RAG retrieved >0) e citações por
resposta. Source: copilot_request_log.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_copilot_rag_dia AS
SELECT
    DATE_TRUNC('day', created_at)::date                                  AS data,
    route,
    COUNT(*)                                                             AS n_requests,
    COUNT(*) FILTER (WHERE rag_chunks_retrieved > 0)                     AS n_rag_hit,
    AVG(rag_chunks_retrieved)                                            AS chunks_avg,
    AVG(citations_count)                                                 AS citations_avg
FROM copilot_request_log
WHERE created_at IS NOT NULL
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_copilot_rag_dia")
        await conn.execute(VIEW_SQL)
        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_copilot_rag_dia")
        print(f"  OK view criada — {n_rows:,} linhas.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
