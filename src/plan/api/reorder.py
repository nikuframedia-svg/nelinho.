"""Q.115.C — POST /v1/plan/operations/reorder (drag-drop manual).

Endpoint que o frontend Q.115.K chama apos o utilizador arrastar uma
operacao no painel. Valida axiomas Spelke via safety_net, cria novo
ScheduleCommit e emite evento Kafka plan.manual_override.

Response 200  -> commit criado, delta_summary populado.
Response 422  -> violacao de axioma Spelke com detalhe PT-PT.
Response 404  -> sem commit base ou operacao nao encontrada.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.api._cpo_common import _tenant_id
from src.plan.services.manual_reorder import SafetyNetViolation, apply_manual_reorder
from src.shared.database import get_session

router = APIRouter(prefix="/v1/plan/operations", tags=["plan-reorder"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReorderRequest(BaseModel):
    operation_id: str = Field(..., description="ID da operacao a mover")
    new_phase: str = Field(..., description="phase_id de destino")
    new_start_ts: datetime = Field(..., description="Novo inicio (ISO 8601 com tz)")
    new_operator_id: Optional[str] = Field(
        default=None, description="Novo operador (opcional)"
    )


class ReorderResponse(BaseModel):
    commit_sha: str = Field(..., description="SHA256 do novo ScheduleCommit criado")
    delta_summary: Dict[str, Any] = Field(
        ..., description="{moved_from, moved_to, axiom_checks_passed}"
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/reorder",
    response_model=ReorderResponse,
    status_code=status.HTTP_200_OK,
    summary="Reorder manual drag-drop (Q.115.C)",
)
async def reorder_operation(
    body: ReorderRequest,
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> ReorderResponse:
    """Move uma operacao para nova fase/timestamp via drag-drop.

    Valida os axiomas Spelke antes de persistir. Se algum axioma for
    violado devolve 422 com `axiom` e `reason_pt` em PT-PT.
    """
    try:
        result = await apply_manual_reorder(
            session=db,
            tenant_id=tenant_id,
            operation_id=body.operation_id,
            new_phase=body.new_phase,
            new_start_ts=body.new_start_ts,
            new_operator_id=body.new_operator_id,
        )
    except SafetyNetViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "violou_axioma_spelke",
                "axiom": exc.axiom_name,
                "operation_id": exc.operation_id,
                "reason_pt": exc.reason_pt,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ReorderResponse(
        commit_sha=result["commit_sha"],
        delta_summary=result["delta_summary"],
    )
