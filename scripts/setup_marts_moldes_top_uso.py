"""Q.108.J.2 — view `marts.v_moldes_top_uso`.

Top moldes mais usados (snapshot).
Q.173.AJ: plan.mold não tem usage_counter; substitui por contagem real
de OFs que usaram o molde via factory_raw.of_fp.OF_OF_ID_MLD (molde pai).

Granularidade: snapshot diário, 1 linha por molde activo.
Cube consume e ordena por n_utilizacoes DESC para top-N.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_moldes_top_uso AS
-- Q.173.AJ: plan.mold não tem usage_counter → conta OFs via OF_OF_ID_MLD.
-- OF_OF_ID_MLD = OF do molde-pai (raiz); join sobre OF_ID = ID do barco.
SELECT
    CURRENT_DATE                                AS data,
    m.id                                        AS molde_id,
    m.mold_code,
    m.name                                      AS molde_nome,
    m.mold_type,
    COALESCE(uso.n_utilizacoes, 0)              AS n_utilizacoes
FROM plan.mold m
LEFT JOIN (
    SELECT
        CAST(ofp."OFFP_OF_ID_MLD" AS text)       AS mold_erp_id,
        COUNT(DISTINCT ofp."OFFP_OF_ID")         AS n_utilizacoes
    FROM factory_raw.of_fp ofp
    WHERE ofp."OFFP_OF_ID_MLD" IS NOT NULL
      AND ofp."OFFP_OF_ID_MLD" != ofp."OFFP_OF_ID"
    GROUP BY 1
) uso ON uso.mold_erp_id = m.mold_code
WHERE m.active = TRUE
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
