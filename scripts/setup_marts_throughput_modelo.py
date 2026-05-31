"""Q.108.F.3b — view `marts.v_throughput_modelo_sem`.

Throughput semanal de OFs concluídas por (disciplina × modelo). Fonte:
factory_raw.ordemfabrico.OF_DATAFIM como data canónica de fecho da OF
+ JOIN produto + produto_tipo (este último mirrored em Q.102.A).

Granularidade: (semana, modelo, disciplina). Permite cross-cube com
qualidade_rework_por_disciplina e comercial_facturacao_disciplina.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_throughput_modelo_sem AS
SELECT
    DATE_TRUNC('week', CAST(NULLIF(o."OF_DATAFIM", '') AS timestamp))::date  AS data,
    p."P_NOME"                                                                AS modelo,
    p."P_ID"                                                                  AS modelo_id,
    COALESCE(pt."TP_NOME", 'Não categorizado')                                AS disciplina,
    COUNT(*)                                                                  AS n_ofs_concluidas
FROM factory_raw.ordemfabrico o
JOIN factory_raw.produto p
  ON p."P_ID" = o."OF_P_ID"
LEFT JOIN factory_raw.produto_tipo pt
  ON pt."TP_ID" = p."P_TP_ID"
WHERE NULLIF(o."OF_DATAFIM", '') IS NOT NULL
GROUP BY 1, 2, 3, 4
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_throughput_modelo_sem")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_throughput_modelo_sem"
        )
        print(f"  OK view criada — {n_rows:,} linhas (semana × modelo × disciplina).")

        if n_rows == 0:
            print("  AVISO: 0 linhas — verifica produto_tipo mirror Q.102.A.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_ofs_concluidas)               AS total,
                COUNT(DISTINCT modelo)              AS n_modelos,
                COUNT(DISTINCT disciplina)          AS n_disciplinas,
                MIN(data) AS min_sem,
                MAX(data) AS max_sem
            FROM marts.v_throughput_modelo_sem
            """
        )
        top = await conn.fetch(
            """
            SELECT disciplina, SUM(n_ofs_concluidas) AS n
            FROM marts.v_throughput_modelo_sem
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 5
            """
        )
        print(
            f"  Total OFs concluídas = {edge['total']:,}  "
            f"modelos = {edge['n_modelos']}  "
            f"disciplinas = {edge['n_disciplinas']}  "
            f"({edge['min_sem']} → {edge['max_sem']})"
        )
        print("  Top 5 disciplinas:")
        for row in top:
            print(f"    {row['disciplina']}: {row['n']:,}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
