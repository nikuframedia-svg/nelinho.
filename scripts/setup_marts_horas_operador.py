"""Q.108.M — view `marts.v_horas_operador_mes`.

Horas trabalhadas por (mês × operador × fase). Source:
factory_raw.apontamento_trabalho (mirror Q.108.M).

PRESSUPOSIÇÃO de schema canónico (convenção NELO):
  - AT_DATA      → text ISO date
  - AT_E_ID      → integer (FK para ENTIDADE)
  - AT_OF_ID     → integer (FK para ORDEMFABRICO)
  - AT_FP_ID     → integer (FK para FASES_PRODUCAO)
  - AT_HORAS     → numeric (horas decimais)

Se um destes campos não existir no schema real, o setup script falha
explicitamente com asyncpg.exceptions.UndefinedColumnError — corrigir
nomes nesse momento. Documentado em q75_setup_raw_mirror.py:RAW_TABLES.

Granularidade: (mês, operador, fase). Destrava KPI 8.2 (horas mês),
prepara cross-cube com qualidade para custo_nao_qualidade (Q.108.M2+).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_horas_operador_mes AS
SELECT
    DATE_TRUNC('month', CAST(NULLIF(at."AT_DATA", '') AS date))::date  AS data,
    at."AT_E_ID"                                                       AS operador_id,
    at."AT_FP_ID"                                                      AS fase_id,
    fp."FP_NOME"                                                       AS fase,
    SUM(at."AT_HORAS")                                                 AS horas_total,
    COUNT(*)                                                           AS n_apontamentos,
    COUNT(DISTINCT at."AT_OF_ID")                                      AS n_ofs_distintas
FROM factory_raw.apontamento_trabalho at
LEFT JOIN factory_raw.fases_producao fp
  ON fp."FP_ID" = at."AT_FP_ID"
WHERE NULLIF(at."AT_DATA", '') IS NOT NULL
  AND at."AT_HORAS" IS NOT NULL
  AND at."AT_HORAS" > 0
GROUP BY 1, 2, 3, 4
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        # Pre-flight: confirma que a tabela existe (q75 deve ter espelhado).
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'factory_raw'
                  AND table_name = 'apontamento_trabalho'
            )
            """
        )
        if not exists:
            print(
                "  AVISO: factory_raw.apontamento_trabalho não existe. "
                "Correr `python scripts/q75_setup_raw_mirror.py` primeiro."
            )
            return 1

        await conn.execute("DROP VIEW IF EXISTS marts.v_horas_operador_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_horas_operador_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × operador × fase).")

        if n_rows == 0:
            print(
                "  AVISO: 0 linhas — apontamento_trabalho pode estar vazia "
                "ou os column names divergem do canónico."
            )
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(horas_total)                  AS total_h,
                COUNT(DISTINCT operador_id)       AS n_operadores,
                COUNT(DISTINCT fase_id)           AS n_fases,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_horas_operador_mes
            """
        )
        print(
            f"  Total horas = {edge['total_h']:,.1f}h  "
            f"operadores = {edge['n_operadores']}  "
            f"fases = {edge['n_fases']}  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
