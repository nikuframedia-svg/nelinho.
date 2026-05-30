"""Q.108.W3 — view `marts.v_etl_freshness_dia`.

ETL freshness: para cada `source`, idade da última execução com sucesso
em horas. Source: core.etl_run.

Snapshot diário — re-corre para refletir runs recentes. Linhas com
status='OK' definem o "última sync" canónica; falhas (status='FAILED')
não contam para freshness mas são contadas separadamente.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_etl_freshness_dia AS
WITH last_per_source AS (
    SELECT DISTINCT ON (source)
        source,
        status,
        started_at,
        finished_at
    FROM core.etl_run
    ORDER BY source, started_at DESC
),
counts AS (
    SELECT
        source,
        COUNT(*) FILTER (WHERE status = 'FAILED')   AS n_failed,
        COUNT(*) FILTER (WHERE status = 'OK')       AS n_ok,
        MAX(started_at) FILTER (WHERE status = 'OK') AS last_ok_at
    FROM core.etl_run
    WHERE started_at >= NOW() - INTERVAL '30 days'
    GROUP BY 1
)
SELECT
    CURRENT_DATE                                          AS data,
    lps.source                                            AS source,
    EXTRACT(EPOCH FROM (NOW() - COALESCE(c.last_ok_at, lps.started_at))) / 3600.0 AS freshness_h,
    COALESCE(c.n_failed, 0)                               AS n_failed_30d,
    COALESCE(c.n_ok, 0)                                   AS n_ok_30d
FROM last_per_source lps
LEFT JOIN counts c USING (source)
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_etl_freshness_dia")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_etl_freshness_dia"
        )
        print(f"  OK view criada — {n_rows} sources distintas.")

        if n_rows == 0:
            print("  AVISO: 0 etl_runs históricos.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                AVG(freshness_h)              AS avg_h,
                MAX(freshness_h)              AS oldest_h,
                SUM(n_failed_30d)             AS failed_30d,
                SUM(n_ok_30d)                 AS ok_30d
            FROM marts.v_etl_freshness_dia
            """
        )
        print(
            f"  Idade média = {edge['avg_h']:.1f}h  pior = {edge['oldest_h']:.1f}h  "
            f"OK 30d = {edge['ok_30d']}  FAILED 30d = {edge['failed_30d']}"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
