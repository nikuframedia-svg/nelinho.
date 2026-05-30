"""Q.108.L.2 — view `marts.v_copilot_feedback_mes`.

Feedback positivo % por mês. Source: copilot_feedback.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_copilot_feedback_mes AS
SELECT
    DATE_TRUNC('month', created_at)::date                       AS data,
    COUNT(*)                                                    AS n_feedback,
    COUNT(*) FILTER (WHERE is_positive = TRUE)                  AS n_positive,
    AVG(CASE WHEN rating IS NOT NULL THEN rating END)           AS rating_avg
FROM copilot_feedback
WHERE created_at IS NOT NULL
GROUP BY 1
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("DROP VIEW IF EXISTS marts.v_copilot_feedback_mes")
        await conn.execute(VIEW_SQL)
        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_copilot_feedback_mes")
        print(f"  OK view criada — {n_rows:,} linhas.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
