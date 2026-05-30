"""Q.108.H — view `marts.v_facturacao_mom`.

MoM growth da facturação. Window function LAG() faz aqui (Cube YAMLs não
têm window functions). PARTITION BY disciplina, ORDER BY data.

mom_pct = (mes - mes_anterior) / mes_anterior — interpretado como FRACAO
no Cube (apresentar como % na narração). Mes_anterior=0 → NULL (drop).

Source: marts.v_facturacao_mes (agregação prévia disciplina × mês).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_facturacao_mom AS
WITH monthly AS (
    SELECT
        data,
        disciplina,
        SUM(facturado_eur) AS facturado_eur
    FROM marts.v_facturacao_mes
    GROUP BY 1, 2
),
with_prev AS (
    SELECT
        data,
        disciplina,
        facturado_eur,
        LAG(facturado_eur) OVER (PARTITION BY disciplina ORDER BY data) AS prev_eur
    FROM monthly
)
SELECT
    data,
    disciplina,
    facturado_eur,
    prev_eur,
    CASE
        WHEN prev_eur IS NULL OR prev_eur = 0 THEN NULL
        ELSE (facturado_eur - prev_eur) / prev_eur
    END                                              AS mom_pct
FROM with_prev
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_facturacao_mom")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_facturacao_mom"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × disciplina).")

        if n_rows == 0:
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                AVG(mom_pct)         AS avg_mom,
                MAX(mom_pct)         AS max_mom,
                MIN(mom_pct)         AS min_mom,
                COUNT(*) FILTER (WHERE mom_pct IS NOT NULL) AS n_with_mom,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_facturacao_mom
            """
        )
        print(
            f"  MoM com dados = {edge['n_with_mom']:,}  "
            f"avg = {(edge['avg_mom'] or 0)*100:.1f}%  "
            f"range [{(edge['min_mom'] or 0)*100:.1f}%, {(edge['max_mom'] or 0)*100:.1f}%]  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
