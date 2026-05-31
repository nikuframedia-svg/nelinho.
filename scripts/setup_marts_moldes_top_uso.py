"""Q.108.J.2 — view `marts.v_moldes_top_uso`.

Top moldes mais usados (snapshot). Source: plan.mold (com usage_counter
populado por src/adapters/nelo/etl/molds.py após Q.108.J.2).

Granularidade: snapshot diário, 1 linha por molde activo com counter > 0.
Cube consume e ordena por uso DESC para top-N.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_moldes_top_uso AS
SELECT
    CURRENT_DATE             AS data,
    id                       AS molde_id,
    mold_code,
    name                     AS molde_nome,
    mold_type,
    usage_counter            AS n_utilizacoes
FROM plan.mold
WHERE active = TRUE
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_moldes_top_uso")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_moldes_top_uso")
        print(f"  OK view criada — {n_rows} moldes activos.")

        if n_rows == 0:
            print("  AVISO: 0 moldes activos. Re-correr mirror_molds.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_utilizacoes)            AS total_uso,
                AVG(n_utilizacoes)            AS avg_uso,
                MAX(n_utilizacoes)            AS max_uso,
                COUNT(*) FILTER (WHERE n_utilizacoes > 0) AS com_uso
            FROM marts.v_moldes_top_uso
            """
        )
        print(
            f"  Total utilizações = {edge['total_uso']:,}  "
            f"AVG = {edge['avg_uso']:.1f}  "
            f"MAX (single mold) = {edge['max_uso']:,}  "
            f"moldes com uso > 0 = {edge['com_uso']}"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
