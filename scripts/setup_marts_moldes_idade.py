"""Q.108.W3 — view `marts.v_moldes_idade`.

Idade média dos moldes (snapshot). Calculada a partir de `plan.mold.acquired_date`
quando preenchida. Moldes activos (active=TRUE) são incluídos.

Source: plan.mold (mirror ERP com idade quando disponível em MLD_DATACRIACAO).
Snapshot diário — re-corre para refletir aquisições recentes.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_moldes_idade AS
SELECT
    CURRENT_DATE                                          AS data,
    COUNT(*) FILTER (WHERE active = TRUE)                 AS n_activos,
    COUNT(*) FILTER (WHERE acquired_date IS NOT NULL)     AS n_com_data,
    -- Postgres: date - date devolve integer (dias); dividir por 365.25 → anos.
    AVG((CURRENT_DATE - acquired_date)::numeric / 365.25)
        FILTER (WHERE acquired_date IS NOT NULL)          AS idade_anos_avg,
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY (CURRENT_DATE - acquired_date)::numeric / 365.25
    ) FILTER (WHERE acquired_date IS NOT NULL)            AS idade_anos_p50,
    MAX((CURRENT_DATE - acquired_date)::numeric / 365.25)
        FILTER (WHERE acquired_date IS NOT NULL)          AS idade_anos_max
FROM plan.mold
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_moldes_idade")
        await conn.execute(VIEW_SQL)

        edge = await conn.fetchrow("SELECT * FROM marts.v_moldes_idade")
        if edge is None or edge["n_activos"] == 0:
            print("  AVISO: 0 moldes na plan.mold.")
            return 0

        print(
            f"  Activos = {edge['n_activos']}  com data = {edge['n_com_data']}  "
            f"idade média = {edge['idade_anos_avg']:.1f} anos  "
            f"P50 = {edge['idade_anos_p50']:.1f}  "
            f"MAX = {edge['idade_anos_max']:.1f}"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
