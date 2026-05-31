"""Q.108.E.2 — view `marts.v_rework_por_molde_mes`.

Granularidade: (data=mês, molde_id). Source: `quality.rework_entry`
(populado pela ETL `src/adapters/nelo/etl/quality.py`).

Q.108.E.1 destrancou esta view ao popular `rework_entry.mold_id` a partir
de `OperationRow.mold_work_order_id` (ERP `OF_OF_ID_MLD`). Antes desse
sub-sprint a coluna existia em schema mas era sempre NULL — agora cada
incidente carrega o molde que o causou.

Anchor: depende do volume real após primeiro mirror_quality com a nova
ETL. Validação inicial = count(*) > 0 (a view ganha linhas à medida que
a ETL é re-executada sobre a janela histórica).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_rework_por_molde_mes AS
SELECT
    date_trunc('month', detected_at)::date            AS data,
    mold_id                                           AS molde_id,
    COUNT(*)                                          AS rework_count,
    COUNT(*) FILTER (
        WHERE (context->>'severe_return')::boolean = TRUE
    )                                                 AS rework_grave
FROM quality.rework_entry
WHERE mold_id IS NOT NULL
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_rework_por_molde_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_rework_por_molde_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × molde).")

        if n_rows == 0:
            print(
                "  AVISO: 0 linhas. Re-correr `mirror_quality` após Q.108.E.1 "
                "para popular `rework_entry.mold_id` na janela histórica."
            )
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT molde_id) AS n_moldes,
                SUM(rework_count)        AS total_rework,
                SUM(rework_grave)        AS total_grave,
                MIN(data)                AS min_mes,
                MAX(data)                AS max_mes
            FROM marts.v_rework_por_molde_mes
            """
        )
        print(
            f"  Moldes distintos = {edge['n_moldes']}  "
            f"total = {edge['total_rework']:,}  "
            f"graves = {edge['total_grave']:,}  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
