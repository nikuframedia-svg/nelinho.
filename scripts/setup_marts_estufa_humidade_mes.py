"""Q.108 Onda A — view `marts.v_estufa_humidade_mes`.

AVG/MIN/MAX de humidade relativa (SD_HUM em 0-100%) por mês × estufa.
Fonte: IOT_SENSOR_DATA (sensors estufa = 12 Estufa 60, 14 Estufa 30,
17 Estufa Peças). Sensor 15 "Temperatura Exterior" EXCLUÍDO — não é
estufa, é ambiente exterior.

Conversão: view divide SD_HUM por 100 (0-100 → 0-1) para honrar a
unit canónica FRACAO. A narração no Cube apresenta como % multi-
plicando por 100. Decisão Luís Q.108: FRACAO sem unit nova.

Anchor histórico Estufa 60 (sensor 12): humidade média ~0.40 (40%).
Estufa 30 (sensor 14): ~0.31. Estufa Peças (sensor 17): ~0.42.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_estufa_humidade_mes AS
SELECT
    DATE_TRUNC('month', d."SD_DATE"::timestamp)::date AS data,
    d."SD_SENSOR_ID"                                  AS sensor_id,
    s."SENSOR_NAME"                                   AS estufa,
    ROUND(AVG(d."SD_HUM"::numeric) / 100.0, 4)        AS hum_avg,
    ROUND(MIN(d."SD_HUM"::numeric) / 100.0, 4)        AS hum_min,
    ROUND(MAX(d."SD_HUM"::numeric) / 100.0, 4)        AS hum_max,
    COUNT(*)                                          AS n_leituras
FROM factory_raw.iot_sensor_data d
JOIN factory_raw.iot_sensor s ON s."SENSOR_ID" = d."SD_SENSOR_ID"
WHERE d."SD_HUM" IS NOT NULL
  AND (s."SENSOR_NAME" ILIKE '%estufa%' OR s."SENSOR_LOCATION" ILIKE '%estufa%')
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_estufa_humidade_mes")
        await conn.execute(VIEW_SQL)
        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_estufa_humidade_mes")
        anchors = await conn.fetch(
            "SELECT sensor_id, estufa, "
            "ROUND(AVG(hum_avg)::numeric, 4)::float AS hum_avg_global, "
            "COUNT(*) AS meses "
            "FROM marts.v_estufa_humidade_mes "
            "GROUP BY sensor_id, estufa ORDER BY sensor_id"
        )
        print(f"  OK -- {n:,} rows.")
        for a in anchors:
            print(f"  sensor {a['sensor_id']} ({a['estufa']}): "
                  f"hum_avg_global={a['hum_avg_global']} ({a['meses']} meses)")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
