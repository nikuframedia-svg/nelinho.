"""Q.149.B — corre o job de afinidade operador/fase ON-DEMAND.

O job real corre por cron às 03:30 UTC (agendado por register_tenant). Em dev
não há que esperar: este script corre-o já, para a aba "Operadores" do FaseSheet
deixar de mostrar "O job de afinidades ainda não correu para esta fase".

É idempotente (UPSERT). Imprime um diagnóstico ANTES (quantas linhas de
histórico com worker_id) porque o job é silencioso quando não há dados — se o
diagnóstico der 0, a aba fica vazia por falta de `worker_id` em
fases_of_history, e isso é um problema de DADOS (não de agendamento).

Uso:
    python scripts/run_phase_operator_affinity.py [tenant_uuid]
Default tenant = dev (00000000-0000-0000-0000-000000000001).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select

from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.plan.models.fases_of_history import FasesOfHistory
from src.scheduling.jobs.phase_operator_affinity import _phase_operator_affinity_job
from src.shared.database import get_session_context

_DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def _main(tenant_id: UUID) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    async with get_session_context() as session:
        n_hist = (
            await session.execute(
                select(func.count())
                .select_from(FasesOfHistory)
                .where(
                    FasesOfHistory.tenant_id == tenant_id,
                    FasesOfHistory.worker_id.is_not(None),
                    FasesOfHistory.phase_id.is_not(None),
                    FasesOfHistory.fase_inicio >= cutoff,
                )
            )
        ).scalar()
    print(f"[diag] fases_of_history c/ worker_id+phase_id (90d) = {n_hist}")
    if not n_hist:
        print(
            "[aviso] 0 linhas com worker_id — a aba Operadores fica vazia. "
            "Problema de DADOS (worker_id NULL no histórico), não de agendamento."
        )

    await _phase_operator_affinity_job(tenant_id)

    async with get_session_context() as session:
        n_aff = (
            await session.execute(
                select(func.count())
                .select_from(PhaseOperatorAffinity)
                .where(PhaseOperatorAffinity.tenant_id == tenant_id)
            )
        ).scalar()
    print(f"[resultado] governance.phase_operator_affinity linhas p/ tenant = {n_aff}")


if __name__ == "__main__":
    tid = UUID(sys.argv[1]) if len(sys.argv) > 1 else _DEV_TENANT
    asyncio.run(_main(tid))
