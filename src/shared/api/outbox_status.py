"""Q.61.34 — `GET /v1/outbox/status`.

Cumpre a parte de **observabilidade** do plano de outbox: o dispatcher
(src/shared/outbox_dispatcher.py) ja faz retry + DLQ; faltava forma
de o operador VER o backlog em runtime sem `psql`.

Resposta:
  * pending: nº de events em fila (status='pending')
  * published: total acumulado de events ja entregues (status='published')
  * failed: nº de events movidos para DLQ (status='failed')
  * oldest_pending_age_seconds: idade do event pendente mais antigo
    (None se nao ha pendentes). Util para alarmar se o dispatcher
    para de drenar.
  * retry_pending: nº de events com retry_count > 0 ainda em pending
    (drenagem em curso mas a falhar).

Tenant scope: opcional. O operator central pode querer ver TODOS os
tenants (sem header) ou um especifico (com X-Tenant-Id).

Q.61.34.1 (follow-up): retry exponential backoff exige adicionar
coluna `next_retry_at` ao EventOutbox via migration — fora de scope
para este sub-sprint.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.shared.outbox_models import EventDLQ, EventOutbox


router = APIRouter(prefix="/v1/outbox", tags=["Outbox"])


class OutboxStatus(BaseModel):
    """Snapshot do backlog do outbox."""

    pending: int
    published: int
    failed: int
    dlq: int
    oldest_pending_age_seconds: Optional[float] = None
    retry_pending: int
    tenant_id: Optional[UUID] = None  # echo do filtro aplicado


@router.get("/status", response_model=OutboxStatus)
async def get_outbox_status(
    tenant_id: UUID = Depends(require_tenant_header),
    include_all_tenants: bool = Query(
        False,
        description="Operador central ve TODOS os tenants. Default: tenant do header.",
    ),
    session: AsyncSession = Depends(get_session),
) -> OutboxStatus:
    """Lê estado actual do outbox. Read-only, barato."""
    base = select(EventOutbox)
    if not include_all_tenants:
        base = base.where(EventOutbox.tenant_id == tenant_id)

    async def _count(status_filter: Optional[str] = None) -> int:
        q = select(func.count()).select_from(EventOutbox)
        if not include_all_tenants:
            q = q.where(EventOutbox.tenant_id == tenant_id)
        if status_filter is not None:
            q = q.where(EventOutbox.status == status_filter)
        return int((await session.execute(q)).scalar() or 0)

    pending = await _count("pending")
    published = await _count("published")
    failed = await _count("failed")

    # DLQ count (sem tenant scope — a DLQ table nao tem coluna tenant_id;
    # join via EventOutbox para filtrar quando necessario).
    dlq_q = select(func.count()).select_from(EventDLQ)
    if not include_all_tenants:
        # join EventOutbox para aplicar tenant filter via FK
        dlq_q = dlq_q.join(
            EventOutbox, EventOutbox.id == EventDLQ.event_outbox_id,
        ).where(EventOutbox.tenant_id == tenant_id)
    dlq = int((await session.execute(dlq_q)).scalar() or 0)

    # Oldest pending — apanha o sintoma "dispatcher parou de drenar"
    oldest_q = select(func.min(EventOutbox.created_at)).where(
        EventOutbox.status == "pending",
    )
    if not include_all_tenants:
        oldest_q = oldest_q.where(EventOutbox.tenant_id == tenant_id)
    oldest_created = (await session.execute(oldest_q)).scalar()

    age_seconds: Optional[float] = None
    if oldest_created is not None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        # asyncpg devolve tz-aware ja
        age_seconds = (now - oldest_created).total_seconds()

    # Retry pending — events em fila mas que ja falharam pelo menos 1x
    retry_q = select(func.count()).select_from(EventOutbox).where(
        EventOutbox.status == "pending",
        EventOutbox.retry_count > 0,
    )
    if not include_all_tenants:
        retry_q = retry_q.where(EventOutbox.tenant_id == tenant_id)
    retry_pending = int((await session.execute(retry_q)).scalar() or 0)

    return OutboxStatus(
        pending=pending,
        published=published,
        failed=failed,
        dlq=dlq,
        oldest_pending_age_seconds=age_seconds,
        retry_pending=retry_pending,
        tenant_id=None if include_all_tenants else tenant_id,
    )


__all__ = ["router"]
