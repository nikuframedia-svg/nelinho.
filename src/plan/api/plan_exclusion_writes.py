"""Q.153.C1 — endpoints para excluir/repor um barco do plano (reversível).

Endpoints (RBAC Permission.SCHEDULE_WRITE):
  POST   /v1/plan/boats/{order_id}/exclude   Body: { reason? }  → exclui/adia
  DELETE /v1/plan/boats/{order_id}/exclude                      → repõe (idempotente)
  GET    /v1/plan/boats/excluded                                → lista excluídos

"Tirar um barco" = excluí-lo do CPO de forma reversível. A presença da linha
em plan.plan_exclusion significa excluído; o efeito aplica-se no PRÓXIMO
replan (o FactoryState recarrega e filtra as open_orders). O barco continua
no ERP — nunca tocamos em factory_raw.

Padrão idêntico ao Q.116.D (boat_boost_writes): SELECT → add/mutate → flush →
audit_change (mesma tx, axioma 7) → SEM commit (boundary = get_session).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import NAMESPACE_OID, UUID, uuid5

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.plan_exclusion import PlanExclusion
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(prefix="/v1/plan", tags=["Q.153.C Plan Exclusion"])

_require_schedule_write = PermissionDependency([Permission.SCHEDULE_WRITE])


def _actor_uuid(user_id: str) -> Optional[UUID]:
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


def _audit_entity_id(order_id: str) -> UUID:
    """UUID v5 determinística — mesmo barco, mesma UUID (audit_log.entity_id)."""
    return uuid5(NAMESPACE_OID, f"plan_exclusion:{order_id}")


# ─── Schemas ────────────────────────────────────────────────────────────────


class ExcludeBoatIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class ExcludedBoatOut(BaseModel):
    order_id: str
    reason: Optional[str]
    excluded_by: str
    excluded_at: datetime

    model_config = {"from_attributes": True}


# ─── POST /v1/plan/boats/{order_id}/exclude ─────────────────────────────────


@router.post(
    "/boats/{order_id}/exclude",
    response_model=ExcludedBoatOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_schedule_write)],
)
async def exclude_boat(
    order_id: str,
    body: ExcludeBoatIn,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> ExcludedBoatOut:
    """Exclui/adia um barco do plano automático (reversível, idempotente)."""
    stmt = select(PlanExclusion).where(
        PlanExclusion.order_id == order_id,
        PlanExclusion.tenant_id == tenant_id,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is None:
        row = PlanExclusion(
            tenant_id=tenant_id,
            order_id=order_id,
            reason=body.reason,
            excluded_by=user_id,
            excluded_at=now,
        )
        session.add(row)
        action: str = "INSERT"
        old_vals: Optional[dict] = None
    else:
        old_vals = {"excluded": True, "reason": existing.reason}
        existing.reason = body.reason
        existing.excluded_by = user_id
        existing.excluded_at = now
        row = existing
        action = "UPDATE"

    await session.flush()
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="plan_exclusion",
        entity_id=_audit_entity_id(order_id),
        action=action,  # type: ignore[arg-type]
        old_values=old_vals,
        new_values={"excluded": True, "reason": body.reason},
        actor_id=_actor_uuid(user_id),
        reason="exclude_boat_from_plan",
    )
    return row  # type: ignore[return-value]


# ─── DELETE /v1/plan/boats/{order_id}/exclude ───────────────────────────────


@router.delete(
    "/boats/{order_id}/exclude",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_schedule_write)],
)
async def reinclude_boat(
    order_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Repõe um barco no plano (remove a exclusão). Idempotente: repor um
    barco já incluído devolve 200 com reincluded=False."""
    stmt = select(PlanExclusion).where(
        PlanExclusion.order_id == order_id,
        PlanExclusion.tenant_id == tenant_id,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return {"order_id": order_id, "reincluded": False}

    await session.execute(
        delete(PlanExclusion).where(
            PlanExclusion.order_id == order_id,
            PlanExclusion.tenant_id == tenant_id,
        )
    )
    await session.flush()
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="plan_exclusion",
        entity_id=_audit_entity_id(order_id),
        action="DELETE",  # type: ignore[arg-type]
        old_values={"excluded": True, "reason": existing.reason},
        new_values={"excluded": False},
        actor_id=_actor_uuid(user_id),
        reason="reinclude_boat_in_plan",
    )
    return {"order_id": order_id, "reincluded": True}


# ─── GET /v1/plan/boats/excluded ────────────────────────────────────────────


@router.get(
    "/boats/excluded",
    response_model=List[ExcludedBoatOut],
    dependencies=[Depends(_require_schedule_write)],
)
async def list_excluded_boats(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[ExcludedBoatOut]:
    """Lista os barcos actualmente excluídos do plano (para o painel + repor)."""
    stmt = (
        select(PlanExclusion)
        .where(PlanExclusion.tenant_id == tenant_id)
        .order_by(PlanExclusion.excluded_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)  # type: ignore[return-value]
