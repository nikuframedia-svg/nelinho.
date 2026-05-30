"""Q.108.W1.2 — view `marts.v_backlog_dia`.

Backlog = OFs cuja data de entrega prometida (OF_DATAENTREGA) já passou
mas ainda não fecharam (OF_DATAFIM NULL). Snapshot-like — re-corre
diariamente. Source: factory_raw.ordemfabrico.

Decomposição:
  - backlog_count: total de OFs em atraso (hoje)
  - dias_atraso_avg: AVG(now - OF_DATAENTREGA) entre as backlog
  - max_dias_atraso: pior caso

Granularidade: snapshot diário (DATE_TRUNC('day', now())). Pode crescer
indefinidamente sem re-run regular — o consumidor pega na linha mais recente.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_backlog_dia AS
-- Q.108.W1.2: OFs em atraso (snapshot diário).
-- Critério: OF_DATAENTREGA < today AND OF_DATAFIM IS NULL.
WITH backlog_ofs AS (
    SELECT
        of_id,
        delivery_date,
        EXTRACT(EPOCH FROM (NOW() - delivery_date)) / 86400.0 AS dias_atraso
    FROM (
        SELECT
            "OF_ID"::text AS of_id,
            CAST(NULLIF("OF_DATAENTREGA", '') AS timestamp) AS delivery_date,
            NULLIF("OF_DATAFIM", '') AS end_date
        FROM factory_raw.ordemfabrico
    ) parsed
    WHERE delivery_date IS NOT NULL
      AND delivery_date < NOW()
      AND end_date IS NULL
)
SELECT
    CURRENT_DATE                                  AS data,
    COUNT(*)                                      AS backlog_count,
    AVG(dias_atraso)                              AS dias_atraso_avg,
    MAX(dias_atraso)                              AS dias_atraso_max,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dias_atraso) AS dias_atraso_p50
FROM backlog_ofs
WHERE dias_atraso > 0
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_backlog_dia")
        await conn.execute(VIEW_SQL)

        edge = await conn.fetchrow("SELECT * FROM marts.v_backlog_dia")
        if edge is None or edge["backlog_count"] == 0:
            print("  Sem OFs em atraso hoje (ou factory_raw.ordemfabrico vazia).")
            return 0

        print(
            f"  Backlog hoje = {edge['backlog_count']:,} OFs em atraso. "
            f"AVG dias atraso = {edge['dias_atraso_avg']:.1f}  "
            f"P50 = {edge['dias_atraso_p50']:.1f}  "
            f"MAX = {edge['dias_atraso_max']:.0f}"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
