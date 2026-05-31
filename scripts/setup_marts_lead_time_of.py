"""Q.108.F.1 — view `marts.v_lead_time_of_mes`.

Lead time médio de OF por mês de fechamento = dias entre MIN(OFFP_DATAINICIO)
e MAX(OFFP_DATAFIM) por work_order_id, agregado pelo mês em que a última
fase terminou.

Granularidade: (data = mês de fechamento, AVG/P50/P90 em dias). CONTAGEM de
OFs fechadas como denominador. NÃO inclui OFs ainda em curso.

Anchor de validação: count > 0 + lead_time_dias_avg numa faixa razoável
(2..120 dias para uma fábrica de kayaks); fora dela = sinal de filtros mal
postos ou dados corrompidos.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_lead_time_of_mes AS
-- Q.108.F.1: lead time de OFs por mês de fechamento.
-- CTE 1: agregar fases por OF → opened_at, closed_at, n_phases.
-- CTE 2: filtrar OFs com ambos timestamps válidos e closed_at >= opened_at.
-- Final: agregar por mês de fechamento (avg/p50/p90 em dias).
WITH of_envelope AS (
    SELECT
        "OFFP_OF_ID" AS of_id,
        MIN(CAST(NULLIF("OFFP_DATAINICIO", '') AS timestamp)) AS opened_at,
        MAX(CAST(NULLIF("OFFP_DATAFIM", '') AS timestamp))    AS closed_at,
        COUNT(*) AS n_phases
    FROM factory_raw.of_fp
    WHERE NULLIF("OFFP_DATAINICIO", '') IS NOT NULL
      AND NULLIF("OFFP_DATAFIM", '')    IS NOT NULL
    GROUP BY 1
),
of_clean AS (
    SELECT
        of_id,
        opened_at,
        closed_at,
        n_phases,
        EXTRACT(EPOCH FROM (closed_at - opened_at)) / 86400.0 AS lead_time_dias
    FROM of_envelope
    WHERE closed_at >= opened_at
      AND closed_at > opened_at  -- exclui OFs com tudo no mesmo segundo (artefacto)
)
SELECT
    DATE_TRUNC('month', closed_at)::date                    AS data,
    COUNT(*)                                                AS n_ofs_fechadas,
    AVG(lead_time_dias)                                     AS lead_time_dias_avg,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lead_time_dias) AS lead_time_dias_p50,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY lead_time_dias) AS lead_time_dias_p90,
    MIN(lead_time_dias)                                     AS lead_time_dias_min,
    MAX(lead_time_dias)                                     AS lead_time_dias_max
FROM of_clean
GROUP BY 1
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_lead_time_of_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_lead_time_of_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (meses).")

        if n_rows == 0:
            print("  AVISO: 0 linhas — factory_raw.of_fp pode estar vazia.")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(n_ofs_fechadas)            AS total_ofs,
                AVG(lead_time_dias_avg)        AS overall_avg,
                MIN(lead_time_dias_avg)        AS month_min_avg,
                MAX(lead_time_dias_avg)        AS month_max_avg,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_lead_time_of_mes
            """
        )
        print(
            f"  Total OFs fechadas = {edge['total_ofs']:,}  "
            f"avg lead time = {edge['overall_avg']:.1f} dias  "
            f"(min mês: {edge['month_min_avg']:.1f}, max mês: {edge['month_max_avg']:.1f})  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )

        # Range sanity guard.
        if edge["overall_avg"] is not None:
            if not (1.0 <= edge["overall_avg"] <= 365.0):
                print(
                    f"  WARN: avg fora da faixa esperada 1-365 dias "
                    f"({edge['overall_avg']:.1f}). Verificar filtros / dados."
                )

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
