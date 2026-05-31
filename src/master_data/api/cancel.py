"""Q.115.X5 — Endpoints cancel/retire/deactivate para obras, encomendas, barcos, pessoas.

4 endpoints REST:
  POST /v1/work-orders/{of_id}/cancel        — cancela ordem de fabrico
  POST /v1/encomendas/{encomenda_id}/cancel  — cancela encomenda cliente
  POST /v1/master-data/boats/{boat_id}/retire            — retira barco/modelo
  POST /v1/master-data/employees/{employee_id}/deactivate — desactiva operador

Audit Q.61.18 + Kafka outbox em cada mutação.
RBAC: MASTER_DATA_WRITE.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.master_data.services.cancel_service import (
    CancelResult,
    cancel_encomenda,
    cancel_work_order,
    deactivate_employee,
    retire_boat,
)
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(prefix="/v1", tags=["Master Data — Cancel Q.115.X5"])

_require_master_write = PermissionDependency([Permission.MASTER_DATA_WRITE])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class CancelBody(BaseModel):
    reason: str = Field(..., min_length=10, description="Razão do cancelamento (mín. 10 caracteres)")


class CancelOut(BaseModel):
    entity_id: str
    action: str
    cancelled_at: datetime
    audit_trace_id: Optional[str] = None
    decision_id: Optional[UUID] = None
    warning: Optional[str] = None
    warning_ops_planeadas: int = 0

    model_config = {"from_attributes": True}


def _to_out(r: CancelResult) -> CancelOut:
    return CancelOut(
        entity_id=r.entity_id,
        action=r.action,
        cancelled_at=r.cancelled_at,
        audit_trace_id=r.audit_trace_id,
        decision_id=r.decision_id,
        warning=r.warning,
        warning_ops_planeadas=r.warning_ops_planeadas,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "/work-orders/{of_id}/cancel",
    response_model=CancelOut,
    dependencies=[Depends(_require_master_write)],
    summary="Cancela ordem de fabrico (soft-delete)",
)
async def cancel_work_order_endpoint(
    of_id: str,
    body: CancelBody,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> CancelOut:
    """Cancela uma ordem de fabrico. Soft-delete — mantém histórico para ML."""
    try:
        result = await cancel_work_order(
            session,
            of_id=of_id,
            reason=body.reason,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        await session.commit()
        return _to_out(result)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/encomendas/{encomenda_id}/cancel",
    response_model=CancelOut,
    dependencies=[Depends(_require_master_write)],
    summary="Cancela encomenda de cliente (registo interno)",
)
async def cancel_encomenda_endpoint(
    encomenda_id: str,
    body: CancelBody,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> CancelOut:
    """Regista cancelamento de encomenda. Não escreve no ERP directamente."""
    try:
        result = await cancel_encomenda(
            session,
            encomenda_id=encomenda_id,
            reason=body.reason,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        await session.commit()
        return _to_out(result)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/master-data/boats/{boat_id}/retire",
    response_model=CancelOut,
    dependencies=[Depends(_require_master_write)],
    summary="Retira barco/modelo de produção (soft-flag)",
)
async def retire_boat_endpoint(
    boat_id: str,
    body: CancelBody,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> CancelOut:
    """Retira barco/modelo. Mantém histórico para ML — não apaga rows."""
    try:
        result = await retire_boat(
            session,
            boat_id=boat_id,
            reason=body.reason,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        await session.commit()
        return _to_out(result)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/master-data/employees/{employee_id}/deactivate",
    response_model=CancelOut,
    dependencies=[Depends(_require_master_write)],
    summary="Desactiva operador (soft-flag active=false)",
)
async def deactivate_employee_endpoint(
    employee_id: UUID,
    body: CancelBody,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> CancelOut:
    """Desactiva operador. Se tiver ops futuras, emite Kafka para replan."""
    try:
        result = await deactivate_employee(
            session,
            employee_id=employee_id,
            reason=body.reason,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        await session.commit()
        return _to_out(result)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
