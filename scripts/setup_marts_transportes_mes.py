"""Q.107 Onda 1 — view `marts.v_transportes_mes`. Anchor 2024 = 490 transportes.

Q.173.AJ: factory_raw.paises nao existe nesta BD; dim `pais` fica sempre
'Desconhecido'. O campo pais_id fica NULLable (TR_PAISES_ID direto).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_transportes_mes AS
-- Q.107 — transportes (TRANSPORTE granularidade, não OF). Cada row =
-- 1 viagem registada. Conta TR_DATA NOT NULL. Anchor 2024 = 490.
-- Q.173.AJ: factory_raw.paises nao existe; pais='Desconhecido' fixo.
SELECT
    DATE_TRUNC('month', CAST(NULLIF(tr."TR_DATA", '') AS date))::date  AS data,
    COALESCE(td."DEST_NOME", 'Desconhecido')                          AS destino,
    tr."TR_DEST_ID"                                                    AS destino_id,
    COALESCE(tt."TRTP_NOME", 'Desconhecido')                          AS tipo_transporte,
    tr."TR_TRTP_ID"                                                    AS tipo_transporte_id,
    'Desconhecido'::text                                               AS pais,
    tr."TR_PAISES_ID"                                                  AS pais_id,
    COUNT(*)                                                           AS n,
    SUM(CASE WHEN tr."TR_DATA_ENTREGA" IS NOT NULL
             AND NULLIF(tr."TR_DATA_ENTREGA",'') IS NOT NULL THEN 1 ELSE 0 END) AS n_entregues,
    COALESCE(SUM(tr."TR_CO2"::numeric), 0)::numeric(20,2)               AS co2_kg
FROM factory_raw.transporte tr
LEFT JOIN factory_raw.transp_destino td ON td."DEST_ID" = tr."TR_DEST_ID"
LEFT JOIN factory_raw.transp_tipo tt   ON tt."TRTP_ID" = tr."TR_TRTP_ID"
WHERE tr."TR_DATA" IS NOT NULL
  AND NULLIF(tr."TR_DATA", '') IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6, 7
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_transportes_mes")
        await conn.execute(VIEW_SQL)
        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_transportes_mes")
        a = await conn.fetchval(
            "SELECT SUM(n) FROM marts.v_transportes_mes WHERE EXTRACT(YEAR FROM data)=2024"
        )
        e = await conn.fetchval(
            "SELECT SUM(n_entregues) FROM marts.v_transportes_mes WHERE EXTRACT(YEAR FROM data)=2024"
        )
        co2_total = await conn.fetchval(
            "SELECT SUM(co2_kg)::float FROM marts.v_transportes_mes"
        )
        print(f"  OK -- {n:,} rows. transportes 2024 = {a}; entregues 2024 = {e}; "
              f"co2 total histórico = {co2_total:.0f} kg")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
