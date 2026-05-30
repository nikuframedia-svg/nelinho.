"""Q.108.N — view `marts.v_devolucoes_mes`.

Devoluções (notas de crédito) por (mês × cliente × disciplina × país).

**NELO não tem tabela DEVOLUCAO dedicada**; a fonte canónica são as
linhas de `entidade_phc_fact` com `EPHCF_FACTURADO < 0` (notas de
crédito emitidas, sinal negativo é o marcador, conforme decisão Q.102.B
na docstring de setup_marts_facturacao_mes.py:13-15).

Granularidade: (mês, cliente, disciplina, país) — mesma que
v_facturacao_mes para permitir cross-join.

Sinal: o valor é guardado como POSITIVO em valor_eur (i.e. ABS) para
facilitar leitura em UI; aditivo entre meses/clientes.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_devolucoes_mes AS
SELECT
    MAKE_DATE(f."EPHCF_ANO", f."EPHCF_MES", 1)              AS data,
    f."EPHCF_ANO"                                           AS ano,
    f."EPHCF_MES"                                           AS mes,
    COALESCE(e."E_NOME", 'Sem cliente registado')           AS cliente,
    f."EPHCF_EPHC_ID"                                       AS cliente_id,
    COALESCE(pt."TP_NOME", 'Não categorizado')              AS disciplina,
    COALESCE(NULLIF(TRIM(e."E_PAIS"), ''), 'sem_pais')      AS pais,
    SUM(ABS(f."EPHCF_FACTURADO"::numeric))                  AS valor_eur,
    COUNT(*)                                                AS n_notas
FROM factory_raw.entidade_phc_fact f
LEFT JOIN factory_raw.entidade_phc ephc
       ON ephc."EPHC_ID" = f."EPHCF_EPHC_ID"
LEFT JOIN factory_raw.entidade e
       ON e."E_ID" = ephc."EPHC_E_ID"
LEFT JOIN factory_raw.produto_tipo pt
       ON pt."TP_ID" = f."EPHCF_TP_ID"
WHERE f."EPHCF_FACTURADO" < 0
GROUP BY 1, 2, 3, 4, 5, 6, 7
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_devolucoes_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_devolucoes_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × cliente × disciplina × país).")

        if n_rows == 0:
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(valor_eur)                  AS total_eur,
                SUM(n_notas)                    AS total_notas,
                COUNT(DISTINCT cliente_id)      AS n_clientes,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_devolucoes_mes
            """
        )
        print(
            f"  Total devoluções = €{edge['total_eur']:,.2f}  "
            f"({edge['total_notas']:,} notas, "
            f"{edge['n_clientes']} clientes distintos, "
            f"{edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
