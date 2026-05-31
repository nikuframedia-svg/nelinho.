"""Q.108.H — view `marts.v_arpu_mes`.

ARPU (Average Revenue Per User): facturação / clientes activos por
(mês × disciplina × país). PRÉ-COMPUTADA aqui porque `clientes_activos`
é COUNT(DISTINCT cliente_id) — NÃO aditivo entre meses; somar/dividir
ao nível Cube produz números errados (mesmo cliente activo em vários
meses colapsaria).

Source: marts.v_facturacao_mes.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_arpu_mes AS
SELECT
    data,
    disciplina,
    pais,
    SUM(facturado_eur)                                AS facturado_total,
    COUNT(DISTINCT cliente_id)                        AS clientes_activos,
    SUM(facturado_eur) / NULLIF(COUNT(DISTINCT cliente_id), 0)  AS arpu_eur
FROM marts.v_facturacao_mes
WHERE cliente_id IS NOT NULL
GROUP BY 1, 2, 3
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_arpu_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_arpu_mes")
        print(f"  OK view criada — {n_rows:,} linhas (mês × disciplina × país).")

        if n_rows == 0:
            print("  AVISO: 0 linhas — v_facturacao_mes vazia.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                AVG(arpu_eur)            AS arpu_global,
                MAX(arpu_eur)            AS arpu_max,
                MIN(data)                AS min_mes,
                MAX(data)                AS max_mes
            FROM marts.v_arpu_mes
            """
        )
        print(
            f"  ARPU médio global = €{edge['arpu_global']:.2f}  "
            f"MAX = €{edge['arpu_max']:.2f}  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
