"""ProdPlan ONE — Report retention cleanup (Sprint Q.22.G).

``reports.report_run`` rows accumulate one per generation / delivery.
The retention job prunes runs older than their owning schedule's
``retention_days`` (ad-hoc runs with no schedule use a default).

Each deleted run leaves a ``core.audit_log`` DELETE row in the same
transaction — invariant 7: the cleanup is itself auditable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.reports.models import ReportRun, ReportSchedule

logger = logging.getLogger("reports.cleanup")

DEFAULT_RETENTION_DAYS = 90


async def cleanup_expired_runs(
    session: AsyncSession,
    tenant_id: UUID,
    default_retention_days: int = DEFAULT_RETENTION_DAYS,
) -> int:
    """Apaga ``ReportRun`` rows fora da janela de retenção.

    A retenção por run = ``retention_days`` do schedule dono, ou
    ``default_retention_days`` para runs ad-hoc. Devolve o número de
    runs apagados. Cada run apagado escreve um ``core.audit_log`` DELETE
    na mesma transacção.
    """
    now = datetime.utcnow()

    schedules = (
        await session.execute(
            select(ReportSchedule).where(ReportSchedule.tenant_id == tenant_id)
        )
    ).scalars().all()
    retention_by_schedule = {s.id: s.retention_days for s in schedules}

    runs = (
        await session.execute(
            select(ReportRun).where(
                ReportRun.tenant_id == tenant_id,
                ReportRun.generated_at.isnot(None),
            )
        )
    ).scalars().all()

    deleted = 0
    for run in runs:
        retention = retention_by_schedule.get(
            run.schedule_id, default_retention_days
        )
        cutoff = now - timedelta(days=retention)
        if run.generated_at >= cutoff:
            continue
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                entity_type="report_run",
                entity_id=run.id,
                action="DELETE",
                old_values={
                    "report_type": run.report_type,
                    "status": run.status,
                    "generated_at": run.generated_at.isoformat(),
                },
                reason=f"limpeza de retenção ({retention}d)",
            )
        )
        await session.delete(run)
        deleted += 1

    if deleted:
        await session.commit()
        logger.info(
            "limpeza de retenção: %d run(s) apagados para tenant %s",
            deleted, tenant_id,
        )
    return deleted
