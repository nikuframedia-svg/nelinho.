"""Q.116.D - endpoint PATCH para boost por barco.

Endpoint:
  PATCH /v1/plan/boat-boost/{boat_id}
    Body: { boost: 0-100, reason? }
    Upsert em plan.boat_boost (PK composta tenant_id+boat_id).

Padrao identico ao Q.116.C (upsert_order_boost):
  1. SELECT existing
  2. add() nova row OU mutate existing
  3. flush
  4. audit_change com action=INSERT/UPDATE + old_values/new_values
  5. NAO faz commit — boundary fica para o get_session dependency

RBAC: Permission.SCHEDULE_WRITE (NAO criar BOAT_BOOST_WRITE — reutilizamos
a permissao existente do plano, conforme spec).

Audit Q.61.18: o entity_id do audit_log e uma UUID v5 deterministica
derivada do boat_id (string) — uuid5(NAMESPACE_OID, f"boat_boost:{boat_id}").
Mesma barco, mesma UUID, sempre.

actor_id: `user_id` vem como string de require_user_header. Convertemos
best-effort para UUID; se nao for UUID valido (dev seed "alice" etc.) cai
para None — o updated_by string continua intacto na tabela e o trace_id
no audit_log preserva correlacao.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import NAMESPACE_OID, UUID, uuid5

from fastapi import APIRouter, Body, Depends, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.boat_boost import BoatBoost
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(prefix="/v1/plan", tags=["Q.116.D Boat Boost"])

# ─── RBAC ────────────────────────────────────────────────────────────────────

_require_schedule_write = PermissionDependency([Permission.SCHEDULE_WRITE])


def _actor_uuid(user_id: str) -> Optional[UUID]:
    """Best-effort UUID a partir de user_id string. None se nao for UUID."""
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


# ─── Schemas ────────────────────────────────────────────────────────────────


class BoatBoostUpsert(BaseModel):
    boost: int = Field(..., ge=0, le=100, description="Boost de 0-100")
    reason: Optional[str] = Field(default=None, max_length=2000)


class BoatBoostOut(BaseModel):
    boat_id: str
    boost: int
    reason: Optional[str]
    updated_by: str
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Audit helpers ──────────────────────────────────────────────────────────


def _audit_entity_id(boat_id: str) -> UUID:
    """UUID v5 deterministica para o entity_id do audit_log.

    audit_log.entity_id e UUID; mapeamos o boat_id string para uma UUID
    estavel — mesmo barco, mesma UUID, sempre.
    """
    return uuid5(NAMESPACE_OID, f"boat_boost:{boat_id}")


# ─── PATCH /v1/plan/boat-boost/{boat_id} ────────────────────────────────────


@router.patch(
    "/boat-boost/{boat_id}",
    response_model=BoatBoostOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_schedule_write)],
)
async def upsert_boat_boost(
    # Q.172.F4E — espelha o String(80) do modelo BoatBoost: sem o constraint,
    # um boat_id >80 chars rebentava/truncava silenciosamente no INSERT.
    boat_id: str = Path(..., min_length=1, max_length=80),
    body: BoatBoostUpsert = Body(...),
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> BoatBoostOut:
    """Upsert do boost manual de um barco. Boost 0-100."""
    stmt = select(BoatBoost).where(
        BoatBoost.boat_id == boat_id,
        BoatBoost.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is None:
        row = BoatBoost(
            tenant_id=tenant_id,
            boat_id=boat_id,
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
        entity_type="boat_boost",
        entity_id=_audit_entity_id(boat_id),
        action=action,  # type: ignore[arg-type]
        old_values=old_vals,
        new_values={"boost": body.boost, "reason": body.reason},
        actor_id=_actor_uuid(user_id),
        reason="upsert_boat_boost",
    )
    return row  # type: ignore[return-value]
