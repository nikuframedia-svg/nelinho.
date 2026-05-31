"""Q.108.H — view `marts.v_hhi_clientes_mes`.

Herfindahl-Hirschman Index = SUM((quota_cliente)^2) onde quota = receita_cliente / receita_total.

Interpretação canónica HHI:
  - <0.15 (<1500 pontos × 10000): mercado pouco concentrado
  - 0.15-0.25 (1500-2500): concentração moderada
  - >0.25 (>2500): alta concentração

NELO: HHI elevado indica dependência de poucos clientes — risco
comercial (Gusser KanuSport = 30%+ típico).

Source: marts.v_facturacao_mes. Granularidade: (mês × disciplina).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_hhi_clientes_mes AS
WITH per_cliente AS (
    SELECT
        data,
        disciplina,
        cliente_id,
        SUM(facturado_eur) AS receita_cliente
    FROM marts.v_facturacao_mes
    WHERE cliente_id IS NOT NULL
      AND facturado_eur > 0  -- exclui créditos (NÃO contribuem para concentração)
    GROUP BY 1, 2, 3
),
with_shares AS (
    SELECT
        data,
        disciplina,
        cliente_id,
        receita_cliente,
        receita_cliente / NULLIF(SUM(receita_cliente) OVER (PARTITION BY data, disciplina), 0) AS quota
    FROM per_cliente
)
SELECT
    data,
    disciplina,
    SUM(POWER(quota, 2))                 AS hhi_indice,
    COUNT(*)                             AS n_clientes_mes,
    MAX(quota)                           AS quota_max,
    SUM(receita_cliente)                 AS receita_total_mes
FROM with_shares
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_hhi_clientes_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_hhi_clientes_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × disciplina).")

        if n_rows == 0:
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                AVG(hhi_indice)      AS hhi_avg,
                MAX(hhi_indice)      AS hhi_max,
                AVG(n_clientes_mes)  AS n_clientes_avg,
                MAX(quota_max)       AS quota_max,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_hhi_clientes_mes
            """
        )
        print(
            f"  HHI médio = {edge['hhi_avg']:.4f}  "
            f"MAX = {edge['hhi_max']:.4f}  "
            f"avg n_clientes/mês = {edge['n_clientes_avg']:.1f}  "
            f"quota max single = {edge['quota_max']*100:.1f}%  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
