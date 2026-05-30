"""Q.108.W2 — view `marts.v_schedule_aderencia_mes`.

Schedule adherence = % OFs fechadas no prazo prometido.

Definição:
  on_time = MAX(OFFP_DATAFIM) <= OF_DATAENTREGA
  taxa = COUNT(on_time) / COUNT(total_fechadas)

Source: factory_raw.ordemfabrico (OF_DATAENTREGA) + factory_raw.of_fp
(MAX(OFFP_DATAFIM) por OF). Mês = mês de fechamento (MAX(OFFP_DATAFIM)).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_schedule_aderencia_mes AS
WITH of_closure AS (
    SELECT
        ofp."OFFP_OF_ID"                                          AS of_id,
        MAX(CAST(NULLIF(ofp."OFFP_DATAFIM", '') AS timestamp))   AS actual_close,
        CAST(NULLIF(o."OF_DATAENTREGA", '') AS timestamp)        AS promised_date
    FROM factory_raw.of_fp ofp
    JOIN factory_raw.ordemfabrico o
      ON o."OF_ID" = ofp."OFFP_OF_ID"
    WHERE NULLIF(ofp."OFFP_DATAFIM", '') IS NOT NULL
    GROUP BY 1, o."OF_DATAENTREGA"
)
SELECT
    DATE_TRUNC('month', actual_close)::date                                                 AS data,
    COUNT(*)                                                                                AS n_ofs_fechadas,
    COUNT(*) FILTER (WHERE promised_date IS NOT NULL AND actual_close <= promised_date)    AS n_on_time,
    COUNT(*) FILTER (WHERE promised_date IS NOT NULL AND actual_close > promised_date)     AS n_late,
    COUNT(*) FILTER (WHERE promised_date IS NULL)                                           AS n_sem_promessa,
    AVG(
        CASE
            WHEN promised_date IS NOT NULL
            THEN EXTRACT(EPOCH FROM (actual_close - promised_date)) / 86400.0
        END
    )                                                                                       AS dias_atraso_avg
FROM of_closure
WHERE actual_close IS NOT NULL
GROUP BY 1
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_schedule_aderencia_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_schedule_aderencia_mes"
        )
        print(f"  OK view criada — {n_rows:,} meses.")

        if n_rows == 0:
            print("  AVISO: 0 linhas.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_ofs_fechadas)         AS total_closed,
                SUM(n_on_time)              AS total_on_time,
                SUM(n_late)                 AS total_late,
                SUM(n_sem_promessa)         AS total_sem_promessa,
                ROUND(100.0 * SUM(n_on_time)::float
                      / NULLIF(SUM(n_on_time) + SUM(n_late), 0)::numeric, 2) AS taxa_global_pct,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_schedule_aderencia_mes
            """
        )
        print(
            f"  Closed={edge['total_closed']:,}  on_time={edge['total_on_time']:,}  "
            f"late={edge['total_late']:,}  sem_promessa={edge['total_sem_promessa']:,}  "
            f"adherence global={edge['taxa_global_pct']}%  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
