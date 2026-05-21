"""Q.61.19 — `GET /v1/governance/audit-logs` (paginado, filtros).

Antes do Q.61.19 a tabela `core.audit_log` nao tinha endpoint publico —
invariante 7 ("auditoria escrita na mesma tx + consultavel") so
estava meio feito. Q.61.18 deu o ponto unico de escrita; Q.61.19 da
o ponto unico de leitura.

Filtros:
  * entity_type (ex: "decision_run", "schedule_commit")
  * entity_id (UUID — ver historia de UMA entidade)
  * actor_id (UUID — ver tudo o que UM user fez)
  * action (INSERT | UPDATE | DELETE)
  * since / until (datetime ISO)
  * trace_id (substring — durante a transicao Q.61.18 o trace_id vai
    em `reason` como `[trace_id=...]`)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.audit import AuditLog
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session


router = APIRouter(prefix="/audit-logs", tags=["Governance"])


# ─── schemas ───────────────────────────────────────────────────────────


class AuditLogEntry(BaseModel):
    """Uma linha do audit log."""

    id: UUID
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    old_values: Optional[dict[str, Any]] = None
    new_values: Optional[dict[str, Any]] = None
    actor_id: Optional[UUID] = None
    actor_role: Optional[str] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogPage(BaseModel):
    """Resposta paginada."""

    entries: list[AuditLogEntry]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


# ─── endpoint ──────────────────────────────────────────────────────────


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="ex: decision_run"),
    entity_id: Optional[UUID] = Query(None),
    actor_id: Optional[UUID] = Query(None),
    action: Optional[Literal["INSERT", "UPDATE", "DELETE"]] = Query(None),
    since: Optional[datetime] = Query(None, description="ISO 8601"),
    until: Optional[datetime] = Query(None, description="ISO 8601"),
    trace_id: Optional[str] = Query(None, description="substring do trace_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> AuditLogPage:
    """Lista entradas do audit log com filtros + paginacao.

    Tenant-scoped por design (require_tenant_header garante).
    Ordenacao: created_at DESC (mais recente primeiro).
    """
    filters = [AuditLog.tenant_id == tenant_id]
    if entity_type is not None:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if action is not None:
        filters.append(AuditLog.action == action)
    if since is not None:
        filters.append(AuditLog.created_at >= since)
    if until is not None:
        filters.append(AuditLog.created_at <= until)
    if trace_id is not None:
        # Q.61.18 prefixa reason com `[trace_id=...]`; ate Q.61.18.1
        # adicionar coluna dedicada, filtramos por substring.
        filters.append(AuditLog.reason.like(f"%trace_id={trace_id}%"))

    where = and_(*filters)

    count_q = select(func.count()).select_from(AuditLog).where(where)
    total = (await session.execute(count_q)).scalar() or 0

    page_q = (
        select(AuditLog)
        .where(where)
        .order_by(desc(AuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(page_q)).scalars().all()

    return AuditLogPage(
        entries=[AuditLogEntry.model_validate(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


__all__ = ["router"]
