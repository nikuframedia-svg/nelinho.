"""Q.107 Onda 1 — view `marts.v_pecas_cortadas_mes` (paralelo a pecas_laminadas).

Padrão idêntico a `setup_marts_pecas_laminadas.py` Q.99:
- Filtro `FP_NOME ILIKE '%corte%'` (4 fases: Corte, Corte peças,
  Corte & Costura, Preparação).
- 1 row por (mês × fase). SUM(n) por mês = anchor.

Anchor Abril 2026 = **4 923** fases de corte terminadas.

Idempotente.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_pecas_cortadas_mes AS
SELECT
    DATE_TRUNC('month',
        CAST(NULLIF(ofp."OFFP_DATAFIM", '') AS date)
    )::date                                                          AS data,
    fp."FP_ID"                                                       AS fase_id,
    fp."FP_NOME"                                                     AS fase,
    COUNT(*)                                                         AS n
FROM factory_raw.of_fp ofp
JOIN factory_raw.fases_producao fp
  ON fp."FP_ID" = ofp."OFFP_FP_ID"
WHERE fp."FP_NOME" ILIKE '%corte%'
  AND NULLIF(ofp."OFFP_DATAFIM", '') IS NOT NULL
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_pecas_cortadas_mes")
        await conn.execute(VIEW_SQL)
        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_pecas_cortadas_mes")
        anchor = await conn.fetchval(
            "SELECT SUM(n) FROM marts.v_pecas_cortadas_mes WHERE data='2026-04-01'"
        )
        print(f"  OK view criada -- {n:,} rows. Anchor Abril 2026 = {anchor}")
        assert anchor == 4923, f"anchor falhou: {anchor}"
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
