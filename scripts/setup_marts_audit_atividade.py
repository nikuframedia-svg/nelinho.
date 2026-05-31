"""Q.108.W3 — view `marts.v_audit_atividade_dia`.

Actividade auditada por dia: entries de audit_log + DAU (Daily Active Users).
MAU é derivada no Cube via agregação por month.

Source: core.audit_log. Distinct actors por dia = DAU; por 30 dias = MAU.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_audit_atividade_dia AS
SELECT
    DATE_TRUNC('day', created_at)::date                    AS data,
    entity_type,
    action,
    COUNT(*)                                               AS n_entries,
    COUNT(DISTINCT actor_id) FILTER (WHERE actor_id IS NOT NULL)  AS n_actors
FROM core.audit_log
WHERE created_at IS NOT NULL
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_audit_atividade_dia")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_audit_atividade_dia"
        )
        print(f"  OK view criada — {n_rows:,} linhas (dia × entity × action).")

        if n_rows == 0:
            print("  AVISO: 0 audit_log entries.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_entries)               AS total_entries,
                MAX(n_actors)                AS peak_dau,
                COUNT(DISTINCT data)         AS n_dias,
                MIN(data) AS min_dia,
                MAX(data) AS max_dia
            FROM marts.v_audit_atividade_dia
            """
        )
        print(
            f"  Total entries = {edge['total_entries']:,}  "
            f"peak DAU = {edge['peak_dau']}  "
            f"{edge['n_dias']} dias ({edge['min_dia']} → {edge['max_dia']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
