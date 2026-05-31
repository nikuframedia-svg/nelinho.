"""Q.115.B — Endpoints de configuração + user_input validado.

Routers:
  POST/GET  /v1/config/revenue-target
  GET/PUT   /v1/config/client-priority/{client_id}
  POST/GET/PATCH /v1/user-input

Audit Q.61.18 em cada mutação. Tenant via require_tenant_header.
RBAC: CONFIG_WRITE (revenue-target + client-priority) e SCHEDULE_READ (user-input).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.client_priority import ClientPriority
from src.core.models.daily_revenue_target import DailyRevenueTarget
from src.core.models.user_input import UserInput
from src.governance.audit_service import audit_change
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(prefix="/v1", tags=["Config Q.115"])

# ─────────────────────────────────────────────────────────────────────────────
# Guardas RBAC nomeadas — overrideáveis em testes via dependency_overrides
# ─────────────────────────────────────────────────────────────────────────────

_require_config_write = PermissionDependency([Permission.CONFIG_WRITE])
_require_schedule_read = PermissionDependency([Permission.SCHEDULE_READ])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class RevenueTargetCreate(BaseModel):
    effective_from: date
    target_eur: Decimal = Field(..., gt=0, description="Meta de receita em EUR (>0)")


class RevenueTargetOut(BaseModel):
    id: UUID
    tenant_id: UUID
    effective_from: date
    target_eur: Decimal
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientPriorityUpdate(BaseModel):
    priority: int = Field(..., ge=1, le=5, description="Prioridade de 1 (máxima) a 5 (mínima)")
    reason: Optional[str] = Field(default=None)


class ClientPriorityOut(BaseModel):
    client_id: UUID
    tenant_id: UUID
    priority: int
    reason: Optional[str]
    updated_at: datetime
    updated_by: str

    model_config = {"from_attributes": True}


_VAGUE_TERMS = {"qualquer coisa", "alguma coisa", "isso", "aquilo", "tudo"}


class UserInputCreate(BaseModel):
    what: str = Field(..., min_length=10, max_length=2000, description="O que mudar")
    where_page: Literal["decisoes", "overall", "llm", "configuracoes"] = Field(
        ..., description="Em que página"
    )
    economic_reason: str = Field(
        ..., min_length=30, max_length=2000, description="Razão económica"
    )

    @field_validator("what", "economic_reason")
    @classmethod
    def reject_vague(cls, v: str) -> str:
        if v.strip().lower() in _VAGUE_TERMS:
            raise ValueError("descrição demasiado vaga")
        return v.strip()


class UserInputOut(BaseModel):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    author: str
    what: str
    where_page: str
    economic_reason: str
    status: str
    result_pr_url: Optional[str]
    claude_run_id: Optional[str]
    audit_trace_id: Optional[str]

    model_config = {"from_attributes": True}


class UserInputPatch(BaseModel):
    status: Optional[str] = None
    result_pr_url: Optional[str] = None
    claude_run_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Revenue target
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/config/revenue-target",
    response_model=RevenueTargetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_config_write)],
)
async def create_revenue_target(
    body: RevenueTargetCreate,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> RevenueTargetOut:
    """Cria nova meta de receita diária. Append-only — 1 row por (tenant, data)."""
    row = DailyRevenueTarget(
        id=uuid4(),
        tenant_id=tenant_id,
        effective_from=body.effective_from,
        target_eur=float(body.target_eur),
        created_by=user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma meta para a data {body.effective_from}.",
        )

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="daily_revenue_target",
        entity_id=row.id,
        action="INSERT",
        new_values={
            "effective_from": body.effective_from.isoformat(),
            "target_eur": str(body.target_eur),
        },
        actor_id=None,
        reason="create_revenue_target",
    )
    return row  # type: ignore[return-value]


@router.get(
    "/config/revenue-target",
    response_model=List[RevenueTargetOut],
)
async def list_revenue_targets(
    current_only: bool = Query(default=False),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[RevenueTargetOut]:
    """Lista metas de receita ordenadas por data descendente.

    ?current_only=true devolve apenas o registo mais recente.
    """
    stmt = (
        select(DailyRevenueTarget)
        .where(DailyRevenueTarget.tenant_id == tenant_id)
        .order_by(DailyRevenueTarget.effective_from.desc())
    )
    if current_only:
        stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalars().all()  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# Client priority
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/config/client-priority",
    response_model=List[ClientPriorityOut],
)
async def list_client_priorities(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[ClientPriorityOut]:
    """Lista prioridades de clientes (paginada)."""
    offset = (page - 1) * page_size
    stmt = (
        select(ClientPriority)
        .where(ClientPriority.tenant_id == tenant_id)
        .order_by(ClientPriority.priority.asc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return result.scalars().all()  # type: ignore[return-value]


@router.put(
    "/config/client-priority/{client_id}",
    response_model=ClientPriorityOut,
    dependencies=[Depends(_require_config_write)],
)
async def upsert_client_priority(
    client_id: UUID,
    body: ClientPriorityUpdate,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> ClientPriorityOut:
    """Upsert da prioridade de um cliente. Prioridade deve ser 1–5."""
    stmt = select(ClientPriority).where(
        ClientPriority.client_id == client_id,
        ClientPriority.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is None:
        row = ClientPriority(
            client_id=client_id,
            tenant_id=tenant_id,
            priority=body.priority,
            reason=body.reason,
            updated_at=now,
            updated_by=user_id,
        )
        session.add(row)
        action: str = "INSERT"
        old_vals = None
    else:
        old_vals = {"priority": existing.priority, "reason": existing.reason}
        existing.priority = body.priority
        existing.reason = body.reason
        existing.updated_at = now
        existing.updated_by = user_id
        row = existing
        action = "UPDATE"

    await session.flush()

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="client_priority",
        entity_id=client_id,
        action=action,  # type: ignore[arg-type]
        old_values=old_vals,
        new_values={"priority": body.priority, "reason": body.reason},
        actor_id=None,
        reason="upsert_client_priority",
    )
    return row  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# User input
# ─────────────────────────────────────────────────────────────────────────────

_VALID_STATUSES = {"pending", "in_progress", "done", "rejected"}


@router.post(
    "/user-input",
    response_model=UserInputOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_schedule_read)],
)
async def create_user_input(
    body: UserInputCreate,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> UserInputOut:
    """Cria um pedido de evolução do utilizador com validação obrigatória."""
    from src.shared.observability import get_trace_id

    row = UserInput(
        id=uuid4(),
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
        author=user_id,
        what=body.what,
        where_page=body.where_page,
        economic_reason=body.economic_reason,
        status="pending",
        audit_trace_id=get_trace_id(),
    )
    session.add(row)
    await session.flush()

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="user_input",
        entity_id=row.id,
        action="INSERT",
        new_values={
            "what": body.what[:100],
            "where_page": body.where_page,
        },
        actor_id=None,
        reason="create_user_input",
    )
    return row  # type: ignore[return-value]


@router.get(
    "/user-input",
    response_model=List[UserInputOut],
    dependencies=[Depends(_require_schedule_read)],
)
async def list_user_input(
    status_filter: str = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[UserInputOut]:
    """Lista pedidos de evolução filtrados por status."""
    if status_filter not in _VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status inválido. Use: {', '.join(sorted(_VALID_STATUSES))}",
        )
    offset = (page - 1) * page_size
    stmt = (
        select(UserInput)
        .where(UserInput.tenant_id == tenant_id, UserInput.status == status_filter)
        .order_by(UserInput.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    return result.scalars().all()  # type: ignore[return-value]


@router.patch(
    "/user-input/{input_id}",
    response_model=UserInputOut,
    dependencies=[Depends(_require_schedule_read)],
)
async def patch_user_input(
    input_id: UUID,
    body: UserInputPatch,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> UserInputOut:
    """Actualiza status/resultado de um pedido. Usado pelo Claude remoto."""
    stmt = select(UserInput).where(
        UserInput.id == input_id,
        UserInput.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    if body.status is not None and body.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status inválido. Use: {', '.join(sorted(_VALID_STATUSES))}",
        )

    old_vals = {
        "status": row.status,
        "result_pr_url": row.result_pr_url,
        "claude_run_id": row.claude_run_id,
    }

    if body.status is not None:
        row.status = body.status
    if body.result_pr_url is not None:
        row.result_pr_url = body.result_pr_url
    if body.claude_run_id is not None:
        row.claude_run_id = body.claude_run_id

    await session.flush()

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="user_input",
        entity_id=row.id,
        action="UPDATE",
        old_values=old_vals,
        new_values={
            "status": row.status,
            "result_pr_url": row.result_pr_url,
            "claude_run_id": row.claude_run_id,
        },
        actor_id=None,
        reason="patch_user_input",
    )
    return row  # type: ignore[return-value]
