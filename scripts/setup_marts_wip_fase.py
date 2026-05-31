"""Q.108.W2 — view `marts.v_wip_fase_dia`.

Work In Progress por fase: contagem de operações activas (não terminadas)
em cada fase. Snapshot diário (re-corre periodicamente — o consumidor pega
na linha mais recente).

Critério "activa": OFFP_DATAFIM IS NULL E fase com FP_SEQUENCIA<30 (canónico
Q.79 — fases terminais 30+ são history/expedição).

Source: factory_raw.of_fp + factory_raw.fases_producao. Anchor previsto:
SUM(n_wip) ~ 4 233 OFs × ~6 fases (~25k–34k rows totais).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_wip_fase_dia AS
SELECT
    CURRENT_DATE                              AS data,
    fp."FP_ID"                                AS fase_id,
    COALESCE(fp."FP_NOME", '(sem fase)')      AS fase,
    fp."FP_SEQUENCIA"                         AS fase_sequencia,
    COUNT(*)                                  AS n_wip
FROM factory_raw.of_fp ofp
JOIN factory_raw.fases_producao fp
  ON fp."FP_ID" = ofp."OFFP_FP_ID"
WHERE fp."FP_SEQUENCIA" < 30
  AND NULLIF(ofp."OFFP_DATAFIM", '') IS NULL  -- ainda não terminada
GROUP BY 1, 2, 3, 4
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_wip_fase_dia")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_wip_fase_dia")
        print(f"  OK view criada — {n_rows:,} linhas (fases activas hoje).")

        if n_rows == 0:
            print("  AVISO: 0 linhas — factory_raw.of_fp pode estar vazia ou tudo terminado.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_wip)                       AS total_wip,
                COUNT(*)                         AS n_fases,
                MAX(n_wip)                       AS max_per_fase
            FROM marts.v_wip_fase_dia
            """
        )
        top = await conn.fetch(
            """
            SELECT fase, n_wip
            FROM marts.v_wip_fase_dia
            ORDER BY n_wip DESC
            LIMIT 5
            """
        )
        print(
            f"  Total WIP = {edge['total_wip']:,} operações activas "
            f"em {edge['n_fases']} fases. Max por fase = {edge['max_per_fase']:,}"
        )
        print("  Top 5 fases (WIP):")
        for row in top:
            print(f"    {row['fase']}: {row['n_wip']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
