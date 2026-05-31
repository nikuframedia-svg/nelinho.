"""Q.116.B — admin endpoints para edicao de fases em routing templates.

Endpoints:
  PATCH /v1/plan/routing-templates/{template_id}/sequence
    Body: { phase_order: [phase_row_id, ...] }
    Reordena as fases — escreve novo `seq` 1..N + audit.

  PATCH /v1/plan/routing-templates/{template_id}/phases/{phase_row_id}/flexible
    Body: { is_flexible: bool, allowed_predecessors: [phase_id, ...] }
    Marca uma fase como posicao alternativa.

RBAC: Permission.CONFIG_WRITE (segue padrao `/v1/core/config` — editar
um routing template e configuracao de processo, nao um plano).

Padrao de erros segue Q.115/Q.116.C:
  * ValueError da service layer → 400 (input invalido).
  * RoutingTemplateNotFoundError → 404.
  * Outras excepcoes propagam para handler global FastAPI.

NAO faz commit — o boundary fica para a dependency `get_session`.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.services.routing_template_service import (
    RoutingTemplateNotFoundError,
    RoutingTemplateService,
)
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

router = APIRouter(
    prefix="/v1/plan/routing-templates",
    tags=["Q.116.B Routing Admin"],
)

_require_config_write = PermissionDependency([Permission.CONFIG_WRITE])


def _actor_uuid(user_id: str) -> Optional[UUID]:
    """Best-effort UUID a partir de user_id string. None se nao for UUID."""
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


# ─── Schemas ─────────────────────────────────────────────────────────────────


class UpdateSequenceBody(BaseModel):
    phase_order: List[UUID] = Field(
        ...,
        min_length=1,
        description=(
            "Lista de phase row IDs na nova ordem. Tem de cobrir "
            "exactamente as fases actuais do template."
        ),
    )


class SetFlexibleBody(BaseModel):
    is_flexible: bool = Field(
        ...,
        description=(
            "True = fase pode aparecer em mais do que uma posicao; "
            "False = posicao fixa (limpa allowed_predecessors)."
        ),
    )
    allowed_predecessors: List[str] = Field(
        default_factory=list,
        description=(
            "phase_id strings que podem preceder esta fase. Obrigatorio "
            "(pelo menos 1) quando is_flexible=True; tem de ser vazia "
            "quando is_flexible=False."
        ),
    )


class PhaseOut(BaseModel):
    id: UUID
    template_id: UUID
    seq: int
    phase_id: str
    phase_name: Optional[str]
    is_flexible: bool
    allowed_predecessors: Optional[List[str]]

    model_config = {"from_attributes": True}


class SequenceOut(BaseModel):
    template_id: UUID
    phases: List[PhaseOut]


# ─── PATCH /sequence ────────────────────────────────────────────────────────


@router.patch(
    "/{template_id}/sequence",
    response_model=SequenceOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_config_write)],
)
async def update_template_sequence(
    template_id: UUID,
    body: UpdateSequenceBody,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> SequenceOut:
    """Reordena as fases de um template — reindexa `seq` 1..N + audit."""
    svc = RoutingTemplateService(session, tenant_id)
    try:
        phases = await svc.update_phase_sequence(
            template_id=template_id,
            new_order=body.phase_order,
            actor=_actor_uuid(user_id),
        )
    except RoutingTemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"routing_template {template_id} nao encontrado",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SequenceOut(
        template_id=template_id,
        phases=[PhaseOut.model_validate(p) for p in phases],
    )


# ─── PATCH /phases/{phase_row_id}/flexible ──────────────────────────────────


@router.patch(
    "/{template_id}/phases/{phase_row_id}/flexible",
    response_model=PhaseOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_config_write)],
)
async def set_phase_flexible(
    template_id: UUID,
    phase_row_id: UUID,
    body: SetFlexibleBody,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> PhaseOut:
    """Marca/desmarca uma fase como posicao alternativa.

    `template_id` na URL e contextual — a phase row e identificada por
    `phase_row_id` (PK unico por tenant). Mantemos o template no path
    para o frontend conseguir construir URLs ja com o contexto da
    pagina de edicao do template.
    """
    svc = RoutingTemplateService(session, tenant_id)
    try:
        phase = await svc.set_flexible(
            phase_row_id=phase_row_id,
            is_flexible=body.is_flexible,
            allowed_predecessors=body.allowed_predecessors,
            actor=_actor_uuid(user_id),
        )
    except RoutingTemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"routing_template_phase {phase_row_id} nao encontrado",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return PhaseOut.model_validate(phase)
