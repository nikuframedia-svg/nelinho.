"""Q.107 Onda 4 — view `marts.v_estufa_temp_mes`.

MAX/AVG de temperatura por mês × estufa. Fonte: IOT_SENSOR_DATA Q.98 (sensors 12/14/17).
SD_TEMPERATURE em °C. Cube vai agregar via MAX (sql_alias) cross-row.

Anchor Estufa 60 (sensor 12): pico ano 80.2°C; avg global 31.9°C; em
Abril 2026 pico = 79.4°C.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_estufa_temp_mes AS
SELECT
    DATE_TRUNC('month', d."SD_DATE"::timestamp)::date AS data,
    d."SD_SENSOR_ID"                                  AS sensor_id,
    s."SENSOR_NAME"                                   AS estufa,
    MAX(d."SD_TEMPERATURE"::numeric)::numeric         AS temp_max,
    ROUND(AVG(d."SD_TEMPERATURE"::numeric), 2)        AS temp_avg,
    COUNT(*)                                          AS n_leituras
FROM factory_raw.iot_sensor_data d
JOIN factory_raw.iot_sensor s ON s."SENSOR_ID" = d."SD_SENSOR_ID"
WHERE d."SD_TEMPERATURE" IS NOT NULL
  AND (s."SENSOR_NAME" ILIKE '%estufa%' OR s."SENSOR_LOCATION" ILIKE '%estufa%')
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_estufa_temp_mes")
        await conn.execute(VIEW_SQL)
        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_estufa_temp_mes")
        anchor = await conn.fetchrow(
            "SELECT MAX(temp_max)::float AS pico, ROUND(AVG(temp_avg)::numeric, 1)::float AS avg "
            "FROM marts.v_estufa_temp_mes WHERE sensor_id=12 AND data='2026-04-01'"
        )
        print(f"  OK -- {n:,} rows. Estufa 60 Abril 2026: pico {anchor['pico']}°C, avg {anchor['avg']}°C")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
