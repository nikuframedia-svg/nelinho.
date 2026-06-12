"""Q.174.F4 — endpoints de ausências de operadores (override local).

Endpoints (RBAC Permission.SCHEDULE_WRITE):
  POST   /v1/plan/absences                 Body: { employee_code, date_start,
                                                   date_end, kind?, mode?,
                                                   erp_movent_id?, reason? }
  DELETE /v1/plan/absences/{absence_id}    → remove (idempotente)
  GET    /v1/plan/absences                 → lista overrides ativos

A fonte primária de ausências é o ERP (``ent_mov`` MET_MET_ID=2, lida direto
pelo loader do CPO — incl. FUTURAS). Estes endpoints cobrem o que o ERP não
tem na hora: ``mode='add'`` ("o João ligou doente hoje") e
``mode='ignore_erp'`` (anular um MOVENT_ID errado). O efeito aplica-se no
PRÓXIMO replan (FactoryState recarrega). Padrão Q.153.C1: SELECT → mutate →
flush → audit_change (mesma tx, invariante #7) → SEM commit (boundary =
get_session).

Emite o evento DSL ``worker_absent`` (Q.17) quando uma ausência 'add' é
criada — primeiro produtor real do evento (era definido e nunca disparado).
Best-effort: a falha do motor de regras nunca trava a escrita.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.worker_absence import WorkerAbsence
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plan", tags=["Q.174.F4 Worker Absence"])

_require_schedule_write = PermissionDependency([Permission.SCHEDULE_WRITE])


def _actor_uuid(user_id: str) -> Optional[UUID]:
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


# ─── Schemas ────────────────────────────────────────────────────────────────


class AbsenceIn(BaseModel):
    employee_code: str = Field(min_length=1, max_length=40)
    date_start: date
    date_end: date
    kind: Optional[str] = Field(default=None, max_length=40)
    mode: Literal["add", "ignore_erp"] = "add"
    erp_movent_id: Optional[int] = None
    reason: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _coherent(self) -> "AbsenceIn":
        if self.date_end < self.date_start:
            raise ValueError("date_end < date_start")
        if self.mode == "ignore_erp" and self.erp_movent_id is None:
            raise ValueError("mode='ignore_erp' exige erp_movent_id")
        return self


class AbsenceOut(BaseModel):
    id: UUID
    employee_code: str
    date_start: date
    date_end: date
    kind: Optional[str]
    mode: str
    erp_movent_id: Optional[int]
    reason: Optional[str]
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── POST /v1/plan/absences ─────────────────────────────────────────────────


@router.post(
    "/absences",
    response_model=AbsenceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_schedule_write)],
)
async def create_absence(
    body: AbsenceIn,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> AbsenceOut:
    """Regista uma ausência local (add) ou anula uma ausência ERP (ignore_erp).

    O CPO exclui o operador no intervalo no PRÓXIMO replan."""
    from uuid import uuid4

    row = WorkerAbsence(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        tenant_id=tenant_id,
        employee_code=body.employee_code,
        date_start=body.date_start,
        date_end=body.date_end,
        kind=body.kind,
        mode=body.mode,
        erp_movent_id=body.erp_movent_id,
        reason=body.reason,
        created_by=user_id,
    )
    session.add(row)
    await session.flush()
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="worker_absence",
        entity_id=row.id,
        action="INSERT",
        old_values=None,
        new_values={
            "employee_code": body.employee_code,
            "date_start": body.date_start.isoformat(),
            "date_end": body.date_end.isoformat(),
            "mode": body.mode,
            "kind": body.kind,
        },
        actor_id=_actor_uuid(user_id),
        reason="worker_absence_override",
    )

    # Q.17 — primeiro produtor real do evento `worker_absent` (estava definido
    # no DSL e nunca era emitido; "se o Paulo faltar, realoca a Laminagem"
    # passa a poder disparar). Best-effort: regras nunca travam a escrita.
    if body.mode == "add":
        try:
            from src.governance.yaml_policy import EventType as _EventType
            from src.governance.yaml_policy.runtime import (
                get_engine as _get_yp_engine,
            )

            # payload alinhado com a whitelist do DSL (rule_schema.py:
            # worker_id/worker_name/phase_id/shift/day_of_week/
            # absence_type/absence_date).
            await _get_yp_engine().on_event(
                _EventType.WORKER_ABSENT,
                {
                    "worker_id": body.employee_code,
                    "absence_type": body.kind or "manual",
                    "absence_date": body.date_start.isoformat(),
                    "day_of_week": body.date_start.strftime("%A"),
                },
                tenant_id=tenant_id,
                session=session,
            )
        except Exception as exc:  # pragma: no cover — motor de regras off
            logger.debug("worker_absent rules skipped: %s", exc)

    return row  # type: ignore[return-value]


# ─── DELETE /v1/plan/absences/{absence_id} ──────────────────────────────────


@router.delete(
    "/absences/{absence_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_schedule_write)],
)
async def delete_absence(
    absence_id: UUID,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Remove um override de ausência (idempotente)."""
    stmt = select(WorkerAbsence).where(
        WorkerAbsence.id == absence_id,
        WorkerAbsence.tenant_id == tenant_id,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return {"id": str(absence_id), "deleted": False}

    old = {
        "employee_code": existing.employee_code,
        "date_start": existing.date_start.isoformat(),
        "date_end": existing.date_end.isoformat(),
        "mode": existing.mode,
    }
    await session.execute(
        delete(WorkerAbsence).where(
            WorkerAbsence.id == absence_id,
            WorkerAbsence.tenant_id == tenant_id,
        )
    )
    await session.flush()
    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="worker_absence",
        entity_id=absence_id,
        action="DELETE",
        old_values=old,
        new_values=None,
        actor_id=_actor_uuid(user_id),
        reason="worker_absence_override_removed",
    )
    return {"id": str(absence_id), "deleted": True}


# ─── GET /v1/plan/absences ──────────────────────────────────────────────────


@router.get(
    "/absences",
    response_model=List[AbsenceOut],
    dependencies=[Depends(_require_schedule_write)],
)
async def list_absences(
    include_past: bool = False,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[AbsenceOut]:
    """Lista os overrides de ausência (ativos por defeito; o ERP não aparece
    aqui — só o que foi criado no nelinho)."""
    stmt = select(WorkerAbsence).where(WorkerAbsence.tenant_id == tenant_id)
    if not include_past:
        hoje = datetime.now(timezone.utc).date()
        stmt = stmt.where(WorkerAbsence.date_end >= hoje)
    stmt = stmt.order_by(WorkerAbsence.date_start.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)  # type: ignore[return-value]
