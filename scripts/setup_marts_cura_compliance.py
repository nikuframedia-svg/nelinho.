"""Q.108.W1 — view `marts.v_cura_compliance_mes`.

Compliance % de ciclos de cura: dos ciclos que ATINGIRAM o threshold mínimo
do alarme da estufa (T>=45°C — SENSOR_ALARM SA_MIN), quantos cumprem o
critério canónico de cura química NELO (T>=65°C E duração>=1h).

Diferença vs `marts.v_ciclos_cura`:
  - `v_ciclos_cura` já filtra na origem T>=65°C E duracao>=1h → 100%
    compliance por construção (não informativo).
  - `v_cura_compliance_mes` baixa o filtro para T>=45°C (universo dos
    ciclos "tentados") e marca cada ciclo como compliant/não-compliant.

Compliance = COUNT(compliant=true) / COUNT(*) por (mês, estufa).

Q.108.W1 destrava `corr_temp_avg_vs_compliance_cura`. Anchor expected:
Estufa 60 = ~100% (overnight estável); Peças = baixo (raramente atinge 65°C).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_cura_compliance_mes AS
-- Q.108.W1: compliance de cura química NELO.
-- Universo: ciclos que atingiram threshold do alarme (T>=45°C).
-- Compliance: T_max>=65°C E duracao_h>=1h (critério Q.100).
WITH leituras AS (
    SELECT
        d."SD_SENSOR_ID"             AS sensor_id,
        s."SENSOR_NAME"              AS estufa,
        d."SD_DATE"::timestamp       AS ts,
        d."SD_TEMPERATURE"::numeric  AS temp
    FROM factory_raw.iot_sensor_data d
    JOIN factory_raw.iot_sensor s
      ON s."SENSOR_ID" = d."SD_SENSOR_ID"
    WHERE s."SENSOR_TEMP" = TRUE
      AND (s."SENSOR_NAME" ILIKE '%estufa%' OR s."SENSOR_LOCATION" ILIKE '%estufa%')
      AND d."SD_TEMPERATURE" IS NOT NULL
      AND d."SD_TEMPERATURE"::numeric >= 45  -- threshold alarme (universo de tentativas)
),
flagged AS (
    SELECT
        sensor_id, estufa, ts, temp,
        CASE
            WHEN LAG(ts) OVER (PARTITION BY sensor_id ORDER BY ts) IS NULL
              OR (ts - LAG(ts) OVER (PARTITION BY sensor_id ORDER BY ts)) > INTERVAL '60 minutes'
            THEN 1 ELSE 0
        END AS new_cycle
    FROM leituras
),
numbered AS (
    SELECT
        sensor_id, estufa, ts, temp,
        SUM(new_cycle) OVER (PARTITION BY sensor_id ORDER BY ts) AS cycle_local_id
    FROM flagged
),
ciclos AS (
    SELECT
        sensor_id,
        estufa,
        cycle_local_id,
        MIN(ts)                                                  AS ts_inicio,
        MAX(ts)                                                  AS ts_fim,
        EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts))) / 3600.0         AS duracao_h,
        MAX(temp)                                                AS temp_max
    FROM numbered
    GROUP BY 1, 2, 3
)
SELECT
    DATE_TRUNC('month', ts_inicio)::date              AS data,
    sensor_id,
    estufa,
    COUNT(*)                                          AS total_ciclos,
    COUNT(*) FILTER (
        WHERE temp_max >= 65 AND duracao_h >= 1.0
    )                                                 AS ciclos_compliant
FROM ciclos
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_cura_compliance_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_cura_compliance_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × estufa).")

        if n_rows == 0:
            print("  AVISO: 0 linhas. factory_raw.iot_sensor_data pode estar vazia.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(total_ciclos)              AS sum_total,
                SUM(ciclos_compliant)          AS sum_compliant,
                ROUND(100.0 * SUM(ciclos_compliant)::float
                      / NULLIF(SUM(total_ciclos), 0)::numeric, 2) AS pct_global,
                COUNT(DISTINCT estufa)         AS n_estufas,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_cura_compliance_mes
            """
        )
        print(
            f"  Total ciclos tentados = {edge['sum_total']:,}  "
            f"compliant = {edge['sum_compliant']:,}  "
            f"({edge['pct_global']:.2f}%)  "
            f"estufas = {edge['n_estufas']}  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )

        # Range guard: compliance percentage sanity.
        if edge["pct_global"] is not None:
            if not (0 <= edge["pct_global"] <= 100):
                print(f"  WARN: pct fora de [0,100]: {edge['pct_global']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
