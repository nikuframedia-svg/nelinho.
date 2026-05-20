"""Q.66.A.4 — job de reconciliação do estado das ordens (Q.54.B).

Movido de `src.shared.scheduler` sem alterações de comportamento.
A função `_reconcile_order_statuses_all_tenants` continua privada
e o wrapper `_order_status_reconcile_job` é o entry point do APScheduler.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def _reconcile_order_statuses_all_tenants() -> None:
    """Q.54.B — faz o `status` das ordens convergir com a fase actual.

    Reconciliacao puramente Postgres (nao precisa do ERP): uma ordem em
    fase terminal ("Entregue"/"Armazem"/"Embalado") passa a COMPLETED.
    Escreve `core.audit_log` por transicao. Best-effort por tenant — uma
    falha num tenant nao bloqueia os outros.
    """
    from sqlalchemy import select

    from src.core.models.tenant import Tenant
    from src.plan.services.order_status_reconciler import (
        reconcile_order_statuses,
    )
    from src.shared.database import get_session_context

    try:
        async with get_session_context() as session:
            tenant_ids = (
                await session.execute(select(Tenant.id))
            ).scalars().all()
    except Exception as exc:
        logger.warning("reconcile_order_statuses: tenant list failed: %s", exc)
        return

    for tid in tenant_ids:
        try:
            async with get_session_context() as session:
                result = await reconcile_order_statuses(session, tid)
                await session.commit()
            if result.transitioned:
                logger.info(
                    "reconcile_order_statuses tenant=%s transitioned=%d",
                    tid, result.transitioned,
                )
        except Exception as exc:
            logger.error(
                "reconcile_order_statuses tenant=%s failed: %s",
                tid, exc, exc_info=True,
            )


async def _order_status_reconcile_job() -> None:
    """Q.54.B — job dedicado de reconciliacao do estado das ordens.

    Reconciliacao puramente Postgres (nao depende do ERP) — corre SEMPRE,
    independente de ``sqlserver_enabled``. Cadencia frequente porque e
    barato e mantem o estado das ordens fresco para a pagina Producao.
    """
    await _reconcile_order_statuses_all_tenants()
