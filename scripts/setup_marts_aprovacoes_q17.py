"""Q.108.W1 — view `marts.v_aprovacoes_q17_mes`.

Aprovações Q.17 (governance Decision Runs) agregadas por mês:
  - total_propostas: COUNT decisions criadas no mês
  - total_aprovadas: COUNT que chegaram a status APPROVED/EXECUTED
  - total_pendentes: COUNT ainda em status PROPOSED
  - total_rejeitadas: COUNT em REJECTED/ROLLED_BACK
  - approval_time_avg_horas: AVG horas entre proposed_at e (EXECUTED ou
    ROLLED_BACK ou approved_at de approval). Mede latência decisória.

Source: `shared.decision_runs` (status field is canonical Q.17 lifecycle).
Reference: src/shared/models/governance.py:36-85.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_aprovacoes_q17_mes AS
SELECT
    DATE_TRUNC('month', proposed_at)::date                          AS data,
    action_type,
    COUNT(*)                                                        AS total_propostas,
    COUNT(*) FILTER (WHERE status IN ('APPROVED', 'EXECUTED'))      AS total_aprovadas,
    COUNT(*) FILTER (WHERE status = 'PROPOSED')                     AS total_pendentes,
    COUNT(*) FILTER (WHERE status IN ('REJECTED', 'ROLLED_BACK'))   AS total_rejeitadas,
    -- Approval time = horas entre proposed_at e executed_at (ou rolled_back_at quando rejeitada)
    AVG(
        EXTRACT(EPOCH FROM (
            COALESCE(executed_at, rolled_back_at) - proposed_at
        )) / 3600.0
    ) FILTER (WHERE status IN ('EXECUTED', 'ROLLED_BACK'))           AS approval_time_avg_horas,
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY EXTRACT(EPOCH FROM (
            COALESCE(executed_at, rolled_back_at) - proposed_at
        )) / 3600.0
    ) FILTER (WHERE status IN ('EXECUTED', 'ROLLED_BACK'))           AS approval_time_p50_horas
FROM shared.decision_runs
WHERE proposed_at IS NOT NULL
GROUP BY 1, 2
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_aprovacoes_q17_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_aprovacoes_q17_mes"
        )
        print(f"  OK view criada — {n_rows:,} linhas (mês × action_type).")

        if n_rows == 0:
            print(
                "  Sem decisões no histórico — view válida mas vazia. "
                "Será populada à medida que Q.17 decisões forem registadas."
            )
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(total_propostas)                AS sum_propostas,
                SUM(total_aprovadas)                AS sum_aprovadas,
                SUM(total_pendentes)                AS sum_pendentes,
                SUM(total_rejeitadas)               AS sum_rejeitadas,
                AVG(approval_time_avg_horas)        AS overall_avg_time_h,
                COUNT(DISTINCT action_type)         AS n_action_types,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_aprovacoes_q17_mes
            """
        )
        print(
            f"  Propostas={edge['sum_propostas']:,} "
            f"Aprovadas={edge['sum_aprovadas']:,} "
            f"Pendentes={edge['sum_pendentes']:,} "
            f"Rejeitadas={edge['sum_rejeitadas']:,}"
        )
        if edge["overall_avg_time_h"] is not None:
            print(
                f"  Tempo médio aprovação = {edge['overall_avg_time_h']:.2f}h "
                f"({edge['n_action_types']} action types, "
                f"{edge['min_mes']} → {edge['max_mes']})"
            )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
