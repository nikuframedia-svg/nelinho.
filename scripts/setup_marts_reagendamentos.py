"""Q.108.W1.2 — view `marts.v_reagendamentos_mes`.

Reagendamentos = cada planning_run_id distinto em plan.production_schedules
no mês representa uma corrida do CPO. Mede o ritmo de re-planeamento.
Sub-conta:
  - total_commits: COUNT(DISTINCT planning_run_id) por mês
  - live_commits: COUNT onde status = 'LIVE'
  - draft_commits: COUNT onde status = 'DRAFT'
  - replans: total_commits - 1 (cada corrida após a primeira é um re-plano)

Q.173.AJ: plan.plan_schedule_commits não existe; usa production_schedules
agrupado por planning_run_id (1 planning_run = 1 corrida CPO).
View válida com 0 rows enquanto o CPO não correr.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_reagendamentos_mes AS
-- Q.173.AJ: usa production_schedules agrupado por planning_run_id.
-- 1 planning_run_id distinto = 1 corrida CPO = 1 "commit".
WITH runs AS (
    SELECT
        planning_run_id,
        DATE_TRUNC('month', MIN(created_at))::date  AS data,
        -- status dominante da corrida (SCHEDULED/COMPLETED=LIVE, DRAFT=DRAFT)
        CASE
            WHEN BOOL_OR(status IN ('SCHEDULED', 'COMPLETED', 'IN_PROGRESS')) THEN 'LIVE'
            WHEN BOOL_OR(status = 'DRAFT')                                    THEN 'DRAFT'
            ELSE 'OTHER'
        END AS run_status
    FROM plan.production_schedules
    WHERE created_at IS NOT NULL
      AND planning_run_id IS NOT NULL
    GROUP BY 1
)
SELECT
    data,
    COUNT(*)::bigint                                    AS total_commits,
    COUNT(*) FILTER (WHERE run_status = 'LIVE')::bigint AS live_commits,
    COUNT(*) FILTER (WHERE run_status = 'DRAFT')::bigint AS draft_commits,
    GREATEST(COUNT(*) - 1, 0)::bigint                   AS replans
FROM runs
GROUP BY 1
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_reagendamentos_mes")
        await conn.execute(VIEW_SQL)

        n_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_reagendamentos_mes"
        )
        print(f"  OK view criada — {n_rows:,} meses.")

        if n_rows == 0:
            print("  Sem commits no histórico (CPO ainda não correu).")
            return 0

        edge = await conn.fetchrow(
            """
            SELECT
                SUM(total_commits) AS total,
                SUM(live_commits)  AS live,
                SUM(draft_commits) AS draft,
                SUM(replans)       AS replans,
                MIN(data) AS min_mes,
                MAX(data) AS max_mes
            FROM marts.v_reagendamentos_mes
            """
        )
        print(
            f"  Commits totais = {edge['total']:,}  "
            f"LIVE = {edge['live']:,}  DRAFT = {edge['draft']:,}  "
            f"Replans (com parent) = {edge['replans']:,}  "
            f"({edge['min_mes']} → {edge['max_mes']})"
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
