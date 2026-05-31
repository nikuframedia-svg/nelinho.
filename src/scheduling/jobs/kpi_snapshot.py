"""Q.117.D — job diário que grava a série histórica de KPIs.

Corre uma vez por dia (00:45 UTC, depois do daily_feedback) e escreve um
ponto por KPI da whitelist em ``profit.kpi_snapshot``, para o gráfico de
tendência da página LLM › KPIs.

A lista de tenants chega de ``start_scheduler``. Em dev arranca vazia, por
isso o job descobre os tenants activos na BD (fallback: tenant dev). Assim
funciona em dev e em produção sem configuração extra.
"""

from __future__ import annotations

import logging
from typing import List
from uuid import UUID

logger = logging.getLogger(__name__)

_DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


async def _resolve_tenants(tenant_ids: List[UUID]) -> List[UUID]:
    """Devolve a lista passada ou, se vazia, os tenants activos da BD."""
    if tenant_ids:
        return list(tenant_ids)
    try:
        from src.core.models.tenant import TenantStatus
        from src.core.services.tenant_service import TenantService
        from src.shared.database import get_session_context

        async with get_session_context() as session:
            ts = TenantService(session)
            active = await ts.list_tenants(status=TenantStatus.ACTIVE, limit=1000)
            ids = [t.id for t in active]
        if ids:
            return ids
    except Exception as exc:
        logger.warning("kpi_snapshot: tenant discovery failed (%s) — dev fallback", exc)
    return [_DEV_TENANT]


async def _kpi_snapshot_job(tenant_ids: List[UUID]) -> None:
    """Grava o snapshot diário de KPIs para cada tenant. Best-effort."""
    from src.profit.services.kpi_history import capture_kpi_snapshot
    from src.shared.database import get_session_context

    tenants = await _resolve_tenants(tenant_ids)
    for tid in tenants:
        try:
            async with get_session_context() as session:
                written = await capture_kpi_snapshot(session, tid)
            logger.info("kpi_snapshot tenant=%s kpis=%s", tid, written)
        except Exception as exc:
            logger.error(
                "kpi_snapshot failed for tenant=%s: %s", tid, exc, exc_info=True,
            )
