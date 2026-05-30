"""Q.108.W1.2 — view `marts.v_reagendamentos_mes`.

Reagendamentos = cada novo `plan.plan_schedule_commits` no mês representa
um plano produzido pelo CPO (mesmo que ainda em DRAFT). Mede o ritmo de
re-planeamento. Sub-conta:
  - total_commits: COUNT por mês
  - live_commits: COUNT que chegaram a status='LIVE' (aprovados Q.62.D.4)
  - draft_commits: ficaram em DRAFT (CPO produziu mas não foi aprovado)
  - replans_per_parent: para cada parent_id, quantos commits filhos
    existem — proxy de quantas vezes o plano foi alterado.

Source: src/plan/cpo/commits.py (plan.plan_schedule_commits).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_reagendamentos_mes AS
SELECT
    DATE_TRUNC('month', created_at)::date          AS data,
    COUNT(*)                                       AS total_commits,
    COUNT(*) FILTER (WHERE status = 'LIVE')        AS live_commits,
    COUNT(*) FILTER (WHERE status = 'DRAFT')       AS draft_commits,
    COUNT(*) FILTER (WHERE parent_id IS NOT NULL)  AS replans
FROM plan.plan_schedule_commits
WHERE created_at IS NOT NULL
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
