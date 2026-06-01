"""Q.150 — corre o job de afinidade operador/fase ON-DEMAND.

O job real corre por cron às 03:30 UTC (agendado por register_tenant). Em dev
não há que esperar: este script corre-o já, para a aba "Operadores" do FaseSheet
deixar de mostrar "O job de afinidades ainda não correu para esta fase".

É idempotente (UPSERT). Imprime um diagnóstico ANTES (quantas combinações
operador×fase reais existem em factory_raw nos últimos 90d) — se der 0, a aba
fica vazia por falta de histórico no ERP, não por agendamento.

Uso:
    python scripts/run_phase_operator_affinity.py [tenant_uuid]
Default tenant = dev (00000000-0000-0000-0000-000000000001).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, text

from src.governance.models.phase_operator_affinity import PhaseOperatorAffinity
from src.scheduling.jobs.phase_operator_affinity import _phase_operator_affinity_job
from src.shared.database import get_session_context

_DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")

_DIAG_SQL = text(
    """
    SELECT COUNT(*) FROM (
        SELECT 1
        FROM factory_raw.offp_eq eq
        JOIN factory_raw.of_fp o ON o."OFFP_ID" = eq."OFFPEQ_OFFP_ID"
        WHERE eq."OFFPEQ_E_ID" IS NOT NULL
          AND o."OFFP_FP_ID" IS NOT NULL
          AND NULLIF(o."OFFP_DATAINICIO", '') IS NOT NULL
          AND o."OFFP_DATAINICIO" >= :cutoff
          AND o."OFFP_DATAINICIO" <= :now
        GROUP BY eq."OFFPEQ_E_ID", o."OFFP_FP_ID"
    ) s
    """
)


async def _main(tenant_id: UUID) -> None:
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S")
    async with get_session_context() as session:
        pairs = (
            await session.execute(_DIAG_SQL, {"cutoff": cutoff_iso, "now": now_iso})
        ).scalar()
    print(f"[diag] combinacoes operador-fase reais (offp_eq JOIN of_fp, 90d) = {pairs}")
    if not pairs:
        print("[aviso] 0 combinações — sem histórico real no ERP para esta janela.")

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
