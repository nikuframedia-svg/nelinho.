"""Q.108.E.2 — view `marts.v_rework_por_disciplina_mes`.

Granularidade: (data=mês, disciplina). Source: `quality.rework_entry`
com `context.product_type_name` (TP_NOME) populado pela ETL desde
Q.108.E.1.

Disciplina = TP_NOME do produto (Canoe Sprint, Canoe Marathon, Ocean,
Fitness, …). Permite drill-down de qualidade pela mesma dim usada em
comercial_facturacao_disciplina, abrindo correlação cruzada cost × qual.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_rework_por_disciplina_mes AS
SELECT
    date_trunc('month', detected_at)::date     AS data,
    (context->>'product_type_name')            AS disciplina,
    COUNT(*)                                   AS rework_count,
    COUNT(*) FILTER (
        WHERE (context->>'severe_return')::boolean = TRUE
    )                                          AS rework_grave
FROM quality.rework_entry
WHERE (context->>'product_type_name') IS NOT NULL
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(
            "DROP VIEW IF EXISTS marts.v_rework_por_disciplina_mes"
        )
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_rework_por_disciplina_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × disciplina).")

        if n_rows == 0:
            print(
                "  AVISO: 0 linhas. Re-correr `mirror_quality` após "
                "Q.108.E.1 para popular `context.product_type_name`."
            )
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT disciplina) AS n_disc,
                SUM(rework_count)          AS total_rework,
                SUM(rework_grave)          AS total_grave,
                MIN(data)                  AS min_mes,
                MAX(data)                  AS max_mes
            FROM marts.v_rework_por_disciplina_mes
            """
        )
        print(
            f"  Disciplinas distintas = {edge['n_disc']}  "
            f"total = {edge['total_rework']:,}  "
            f"graves = {edge['total_grave']:,}  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
