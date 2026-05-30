"""Q.108.W2 — view `marts.v_lead_time_entrega_mes`.

Lead time entrega = dias entre fim da OF (MAX(OFFP_DATAFIM)) e expedição
(TR_DATA do transporte associado). Mede o tempo de "OF pronta no chão →
cliente recebe".

Source path:
  factory_raw.of_fp (close date per OF)
    → factory_raw.transp_of (TROF_OF_ID + TROF_TR_ID + TROF_ENVIADO)
    → factory_raw.transporte (TR_ID + TR_DATA)

Granularidade: mês de expedição (TR_DATA) × destino_id (categoria
DEST_NOME quando disponível; null caso contrário).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_lead_time_entrega_mes AS
WITH of_close AS (
    SELECT
        "OFFP_OF_ID"                                                AS of_id,
        MAX(CAST(NULLIF("OFFP_DATAFIM", '') AS timestamp))         AS data_fim_of
    FROM factory_raw.of_fp
    WHERE NULLIF("OFFP_DATAFIM", '') IS NOT NULL
    GROUP BY 1
),
lead_times AS (
    SELECT
        DATE_TRUNC('month', CAST(NULLIF(tr."TR_DATA", '') AS timestamp))::date  AS data,
        tof."TROF_OF_ID"                                                          AS of_id,
        EXTRACT(EPOCH FROM (
            CAST(NULLIF(tr."TR_DATA", '') AS timestamp) - oc.data_fim_of
        )) / 86400.0                                                              AS lead_time_dias
    FROM factory_raw.transp_of tof
    JOIN factory_raw.transporte tr
      ON tr."TR_ID" = tof."TROF_TR_ID"
    JOIN of_close oc
      ON oc.of_id = tof."TROF_OF_ID"
    WHERE tof."TROF_ENVIADO" = TRUE
      AND NULLIF(tr."TR_DATA", '') IS NOT NULL
      AND CAST(NULLIF(tr."TR_DATA", '') AS timestamp) > oc.data_fim_of
)
SELECT
    data,
    COUNT(*)                                                       AS n_entregas,
    AVG(lead_time_dias)                                            AS lead_time_dias_avg,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lead_time_dias)    AS lead_time_dias_p50,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY lead_time_dias)    AS lead_time_dias_p90
FROM lead_times
GROUP BY 1
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_lead_time_entrega_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_lead_time_entrega_mes"
        )
        print(f"  OK view criada — {n_rows:,} meses.")

        if n_rows == 0:
            print("  AVISO: 0 linhas. transp_of pode estar vazio.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_entregas)             AS total_entregas,
                AVG(lead_time_dias_avg)     AS overall_avg,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_lead_time_entrega_mes
            """
        )
        print(
            f"  Total entregas={edge['total_entregas']:,}  "
            f"AVG lead time entrega = {edge['overall_avg']:.1f} dias  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
