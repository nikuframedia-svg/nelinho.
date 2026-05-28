"""Q.116.C — endpoints PATCH para boost + override de transporte por encomenda.

Endpoints:
  PATCH /v1/plan/order-boost/{work_order_id}
    Body: { boost: 0-100, reason? }
    Upsert em plan.order_boost.

  PATCH /v1/plan/work-orders/{work_order_id}/transport-date
    Body: { transport_date?: datetime | null, reason? }
    Upsert em plan.work_order_override. `transport_date=None` limpa o override.

Ambos partilham o padrao do Q.115.B (upsert_client_priority):
  1. SELECT existing
  2. add() nova row OU mutate existing
  3. flush
  4. audit_change com action=INSERT/UPDATE + old_values/new_values
  5. NAO faz commit — boundary fica para o get_session dependency

RBAC: Permission.SCHEDULE_WRITE (NAO criar ORDER_WRITE — reutilizamos a
permissao existente do plano).

Audit Q.61.18: o entity_id do audit_log e uma UUID v5 deterministica
derivada do work_order_id (INT) — uuid5(NAMESPACE_OID, "order_boost:{id}")
ou "work_order_override:{id}". Mesma sub-sprint nunca colide.

actor_id: `user_id` vem como string de require_user_header (JWT sub ou
X-User-Id dev). Convertemos best-effort para UUID; se nao for UUID
valido (dev seed "alice" etc.) cai para None — o updated_by string
continua intacto na tabela e o trace_id no audit_log preserva
correlacao.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import NAMESPACE_OID, UUID, uuid5

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.order_boost import OrderBoost
from src.plan.models.work_order_override import WorkOrderOverride
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(prefix="/v1/plan", tags=["Q.116.C Order Writes"])

# ─── RBAC ────────────────────────────────────────────────────────────────────

_require_schedule_write = PermissionDependency([Permission.SCHEDULE_WRITE])


def _actor_uuid(user_id: str) -> Optional[UUID]:
    """Best-effort UUID a partir de user_id string. None se nao for UUID."""
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


# ─── Schemas ────────────────────────────────────────────────────────────────


class OrderBoostUpsert(BaseModel):
    boost: int = Field(..., ge=0, le=100, description="Boost de 0-100")
    reason: Optional[str] = Field(default=None, max_length=2000)


class OrderBoostOut(BaseModel):
    work_order_id: int
    boost: int
    reason: Optional[str]
    updated_by: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransportDateUpsert(BaseModel):
    transport_date: Optional[datetime] = Field(
        default=None,
        description="Nova data de transporte. None = limpar override.",
    )
    reason: Optional[str] = Field(default=None, max_length=2000)


class WorkOrderOverrideOut(BaseModel):
    work_order_id: int
    transport_date_override: Optional[datetime]
    reason: Optional[str]
    updated_by: str
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Audit helpers ──────────────────────────────────────────────────────────


def _audit_entity_id(entity_type: str, work_order_id: int) -> UUID:
    """UUID v5 deterministica para o entity_id do audit_log.

    audit_log.entity_id e UUID; aqui mapeamos o INT do ERP para uma UUID
    estavel — mesma encomenda, mesma UUID, sempre.
    """
    return uuid5(NAMESPACE_OID, f"{entity_type}:{work_order_id}")


# ─── PATCH /v1/plan/order-boost/{work_order_id} ─────────────────────────────


@router.patch(
    "/order-boost/{work_order_id}",
    response_model=OrderBoostOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_schedule_write)],
)
async def upsert_order_boost(
    work_order_id: int,
    body: OrderBoostUpsert,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> OrderBoostOut:
    """Upsert do boost manual de uma encomenda. Boost 0-100."""
    stmt = select(OrderBoost).where(
        OrderBoost.work_order_id == work_order_id,
        OrderBoost.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is None:
        row = OrderBoost(
            work_order_id=work_order_id,
            tenant_id=tenant_id,
            boost=body.boost,
            reason=body.reason,
            updated_by=user_id,
            updated_at=now,
        )
        session.add(row)
        action: str = "INSERT"
        old_vals: Optional[dict] = None
    else:
        old_vals = {"boost": existing.boost, "reason": existing.reason}
        existing.boost = body.boost
        existing.reason = body.reason
        existing.updated_by = user_id
        existing.updated_at = now
        row = existing
        action = "UPDATE"

    await session.flush()

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="order_boost",
        entity_id=_audit_entity_id("order_boost", work_order_id),
        action=action,  # type: ignore[arg-type]
        old_values=old_vals,
        new_values={"boost": body.boost, "reason": body.reason},
        actor_id=_actor_uuid(user_id),
        reason="upsert_order_boost",
    )
    return row  # type: ignore[return-value]


# ─── PATCH /v1/plan/work-orders/{work_order_id}/transport-date ──────────────


@router.patch(
    "/work-orders/{work_order_id}/transport-date",
    response_model=WorkOrderOverrideOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_schedule_write)],
)
async def upsert_transport_date_override(
    work_order_id: int,
    body: TransportDateUpsert,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> WorkOrderOverrideOut:
    """Upsert do override de data de transporte. None = limpar override."""
    stmt = select(WorkOrderOverride).where(
        WorkOrderOverride.work_order_id == work_order_id,
        WorkOrderOverride.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    new_transport_date_iso = (
        body.transport_date.isoformat() if body.transport_date is not None else None
    )

    if existing is None:
        row = WorkOrderOverride(
            work_order_id=work_order_id,
            tenant_id=tenant_id,
            transport_date_override=body.transport_date,
            reason=body.reason,
            updated_by=user_id,
            updated_at=now,
        )
        session.add(row)
        action: str = "INSERT"
        old_vals: Optional[dict] = None
    else:
        old_iso = (
            existing.transport_date_override.isoformat()
            if existing.transport_date_override is not None
            else None
        )
        old_vals = {
            "transport_date_override": old_iso,
            "reason": existing.reason,
        }
        existing.transport_date_override = body.transport_date
        existing.reason = body.reason
        existing.updated_by = user_id
        existing.updated_at = now
        row = existing
        action = "UPDATE"

    await session.flush()

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="work_order_override",
        entity_id=_audit_entity_id("work_order_override", work_order_id),
        action=action,  # type: ignore[arg-type]
        old_values=old_vals,
        new_values={
            "transport_date_override": new_transport_date_iso,
            "reason": body.reason,
        },
        actor_id=_actor_uuid(user_id),
        reason="upsert_transport_date_override",
    )
    return row  # type: ignore[return-value]
