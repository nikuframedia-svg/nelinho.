"""Q.167.H.1 — view `marts.v_producao_disciplina_mes`.

Produção MENSAL de OFs concluídas por disciplina. O slice que faltava: havia
semanal×disciplina (`v_throughput_modelo_sem`, Q.108.F.3b) e diário-sem-
disciplina (`producao_ofs_fechadas_dia`, Q.152), mas nenhum mensal×disciplina —
a granularidade natural para "produção por disciplina este ano, por mês".

Fonte: `factory_raw.ordemfabrico.OF_DATAFIM` (data canónica de fecho da OF)
+ JOIN produto + produto_tipo (mirrored em Q.102.A). Disciplina = `TP_NOME`
(6=Canoe Sprint, 243=Ocean, 244=Marathon, 245/246=Fitness). Granularidade:
(mês, disciplina). 1 contagem aditiva.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_producao_disciplina_mes AS
SELECT
    DATE_TRUNC('month', CAST(NULLIF(o."OF_DATAFIM", '') AS timestamp))::date  AS data,
    COALESCE(pt."TP_NOME", 'Não categorizado')                                AS disciplina,
    pt."TP_ID"                                                                AS disciplina_id,
    COUNT(*)                                                                  AS n_ofs_concluidas
FROM factory_raw.ordemfabrico o
JOIN factory_raw.produto p
  ON p."P_ID" = o."OF_P_ID"
LEFT JOIN factory_raw.produto_tipo pt
  ON pt."TP_ID" = p."P_TP_ID"
WHERE NULLIF(o."OF_DATAFIM", '') IS NOT NULL
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS marts")
        await conn.execute("DROP VIEW IF EXISTS marts.v_producao_disciplina_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_producao_disciplina_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × disciplina).")

        if n_rows == 0:
            print("  AVISO: 0 linhas — verifica produto_tipo mirror Q.102.A.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_ofs_concluidas)       AS total,
                COUNT(DISTINCT disciplina)  AS n_disciplinas,
                MIN(data)                   AS min_mes,
                MAX(data)                   AS max_mes
            FROM marts.v_producao_disciplina_mes
            """
        )
        top = await conn.fetch(
            """
            SELECT disciplina, SUM(n_ofs_concluidas) AS n
            FROM marts.v_producao_disciplina_mes
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 5
            """
        )
        print(
            f"  Total OFs concluídas = {edge['total']:,}  "
            f"disciplinas = {edge['n_disciplinas']}  "
            f"({edge['min_mes']} -> {edge['max_mes']})"
        )
        print("  Top 5 disciplinas:")
        for row in top:
            print(f"    {row['disciplina']}: {row['n']:,}")

        # Sanity: a soma mensal×disciplina = total de OFs com OF_DATAFIM (mesma
        # base que o diário producao_ofs_fechadas_dia, sem cortes).
        tot_of = await conn.fetchval(
            'SELECT COUNT(*) FROM factory_raw.ordemfabrico o '
            'JOIN factory_raw.produto p ON p."P_ID" = o."OF_P_ID" '
            'WHERE NULLIF(o."OF_DATAFIM", \'\') IS NOT NULL'
        )
        assert edge["total"] == tot_of, (
            f"Anchor falhou: soma mart {edge['total']} != OFs fechadas {tot_of}"
        )
        assert edge["n_disciplinas"] >= 3, (
            f"Anchor falhou: {edge['n_disciplinas']} disciplinas (esperado >=3)"
        )
        print(f"\n  Anchor OK ({tot_of:,} OFs fechadas; {edge['n_disciplinas']} disciplinas).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
