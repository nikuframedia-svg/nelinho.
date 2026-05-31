"""Q.108.L.2 — view `marts.v_copilot_latency_dia`.

Latency P50/P95/P99 do copilot por dia × route. Source:
copilot_request_log. Status='abstain' incluído (não distorce latency).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_copilot_latency_dia AS
SELECT
    DATE_TRUNC('day', created_at)::date                              AS data,
    route,
    COUNT(*)                                                         AS n_requests,
    COUNT(*) FILTER (WHERE status = 'abstain')                       AS n_abstain,
    COUNT(*) FILTER (WHERE status = 'error')                         AS n_error,
    AVG(latency_ms)                                                  AS latency_avg_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms)          AS latency_p50_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)         AS latency_p95_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms)         AS latency_p99_ms
FROM copilot_request_log
WHERE created_at IS NOT NULL
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_copilot_latency_dia")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_copilot_latency_dia"
        )
        print(f"  OK view criada — {n_rows:,} linhas.")
        if n_rows == 0:
            print("  Sem requests no histórico — view válida vazia.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
