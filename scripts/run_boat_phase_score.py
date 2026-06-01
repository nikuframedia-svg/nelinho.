"""Q.150 — corre o job de score barco/fase ON-DEMAND.

O job real corre por cron às 03:45 UTC. Em dev corre-o já para a aba "Barcos
exigentes" do FaseSheet encher. Idempotente (UPSERT).

Uso:
    python scripts/run_boat_phase_score.py [tenant_uuid]
Default tenant = dev (00000000-0000-0000-0000-000000000001).
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy import func, select

from src.governance.models.boat_phase_score import BoatPhaseScore
from src.scheduling.jobs.boat_phase_score_job import _boat_phase_score_job
from src.shared.database import get_session_context

_DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def _main(tenant_id: UUID) -> None:
    await _boat_phase_score_job(tenant_id)
    async with get_session_context() as session:
        n = (
            await session.execute(
                select(func.count())
                .select_from(BoatPhaseScore)
                .where(BoatPhaseScore.tenant_id == tenant_id)
            )
        ).scalar()
    print(f"[resultado] governance.boat_phase_score linhas p/ tenant = {n}")


if __name__ == "__main__":
    tid = UUID(sys.argv[1]) if len(sys.argv) > 1 else _DEV_TENANT
    asyncio.run(_main(tid))
