"""Q.108.M2 — view `marts.v_defeitos_operador_mes`.

Defeitos e operações por (mês × operador). JOIN canónico:
  factory_raw.offp_eq  (OFFPEQ_OFFP_ID + OFFPEQ_E_ID + OFFPEQ_CHEFE)
  → factory_raw.of_fp   (OFFP_ID + OFFP_OF_ID + OFFP_DATAFIM)
  → quality.rework_entry (of_id ↔ OFFP_OF_ID)

Cada operação de fase pode ter MÚLTIPLOS operadores em OFFP_EQ. Aqui
focamos no CAUSER (OFFPEQ_CHEFE=FALSE — quem fez o trabalho); os chefes
ficam fora deste mart (mart próprio em Q.108.M2 continuation).

Destrava `corr_defeitos_vs_operador` — último blocked da campanha Q.108.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_defeitos_operador_mes AS
WITH workers_per_op AS (
    -- Workers (não-chefes) por operação
    SELECT
        e."OFFPEQ_OFFP_ID"::text          AS operation_id,
        e."OFFPEQ_E_ID"                   AS operador_id,
        f."OFFP_OF_ID"::text              AS of_id,
        DATE_TRUNC('month',
            CAST(NULLIF(f."OFFP_DATAFIM", '') AS date)
        )::date                           AS data
    FROM factory_raw.offp_eq e
    JOIN factory_raw.of_fp f
      ON f."OFFP_ID" = e."OFFPEQ_OFFP_ID"
    WHERE NULLIF(f."OFFP_DATAFIM", '') IS NOT NULL
      AND COALESCE(e."OFFPEQ_CHEFE", FALSE) = FALSE
),
defeitos_per_of AS (
    -- COUNT defeitos por OF (de quality.rework_entry).
    SELECT
        of_id,
        COUNT(*)                          AS n_defeitos
    FROM quality.rework_entry
    GROUP BY 1
)
SELECT
    w.data                                AS data,
    w.operador_id                         AS operador_id,
    COUNT(DISTINCT w.operation_id)        AS n_ops,
    COUNT(DISTINCT w.of_id)               AS n_ofs,
    SUM(COALESCE(d.n_defeitos, 0))        AS n_defeitos
FROM workers_per_op w
LEFT JOIN defeitos_per_of d
  ON d.of_id = w.of_id
WHERE w.data IS NOT NULL
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'factory_raw'
                  AND table_name = 'offp_eq'
            )
            """
        )
        if not exists:
            print(
                "  AVISO: factory_raw.offp_eq não existe. Re-correr "
                "`python scripts/q75_setup_raw_mirror.py` primeiro."
            )
            return 1

        await conn.execute("DROP VIEW IF EXISTS marts.v_defeitos_operador_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_defeitos_operador_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × operador).")

        if n_rows == 0:
            print("  AVISO: 0 linhas — verifica column names OFFPEQ_*.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_ops)                     AS sum_ops,
                SUM(n_defeitos)                AS sum_def,
                COUNT(DISTINCT operador_id)    AS n_operadores,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_defeitos_operador_mes
            """
        )
        taxa = (edge["sum_def"] or 0) / max(edge["sum_ops"] or 1, 1)
        print(
            f"  operadores={edge['n_operadores']}  "
            f"ops={edge['sum_ops']:,}  defeitos={edge['sum_def']:,}  "
            f"taxa global={taxa*100:.2f}%  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
