"""
ProdPlan ONE - Schedule Preview-Delta API (Sprint Q.4 / PL01-PL24)
==================================================================

Drag-and-drop side-effect preview + apply for the Layer 1/Layer 2
SchedulingPage UI.

  POST /v1/plan/schedule/preview-delta
        — sub-second; recomputes fitness deltas + conflict checks
  POST /v1/plan/schedule/apply-move
        — persists a new ScheduleCommit child after operator confirms

The preview endpoint is the load-bearing call: every drop fires it,
so it MUST stay sub-second. It never runs GA/CP-SAT — just an in-memory
mutation + `compute_fitness` against the latest committed schedule.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.services.preview_delta_service import (
    PreviewDeltaService,
    PreviewMutation,
)
from src.shared.database import get_session
from src.shared.auth.headers import require_tenant_header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule", tags=["Schedule preview"])


get_tenant_id = require_tenant_header


def get_user(x_user_id: Optional[str] = Header(None, alias="X-User-Id")) -> str:
    return x_user_id or "system"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

# Q.55.C — a operação-alvo identifica-se por `operation_id` (id no commit)
# OU por `order_id` (nº de OF / `hull` do barco). O frontend Fábrica só
# conhece o barco; o backend resolve a operação certa do commit. Pelo
# menos um dos dois é obrigatório.
class _MoveTargetIn(BaseModel):
    operation_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    order_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    new_phase_id: Optional[str] = Field(default=None, max_length=100)
    new_worker_ids: Optional[list[str]] = None

    @model_validator(mode="after")
    def _require_a_target(self) -> "_MoveTargetIn":
        if not self.operation_id and not self.order_id:
            raise ValueError("operation_id ou order_id é obrigatório")
        return self


class PreviewDeltaIn(_MoveTargetIn):
    pass


class ApplyMoveIn(_MoveTargetIn):
    reason: str = Field(..., min_length=10, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/preview-delta")
async def preview_delta(
    body: PreviewDeltaIn,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Recompute fitness/throughput/conflict deltas after a single op move.

    Sub-second contract: this endpoint must never call the CPO solver or
    re-decode a chromosome. It mutates the latest commit's `operations`
    list in memory and reruns `compute_fitness`, plus runs the cheap
    pair-rule + double-booking checks.
    """
    svc = PreviewDeltaService(session, tenant_id)
    try:
        result = await svc.preview(
            PreviewMutation(
                operation_id=body.operation_id,
                order_id=body.order_id,
                new_phase_id=body.new_phase_id,
                new_worker_ids=body.new_worker_ids,
            )
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result.to_dict()


@router.post("/apply-move", status_code=status.HTTP_201_CREATED)
async def apply_move(
    body: ApplyMoveIn,
    tenant_id: UUID = Depends(get_tenant_id),
    user: str = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Persist the move as a new ScheduleCommit (child of latest).

    Plan v4 §11.3: the operator's reason is mandatory because every
    write feeds Camada 1 / Camada 2 of the learning system.
    """
    svc = PreviewDeltaService(session, tenant_id)
    # `apply` resolve `operation_id` no sítio (a partir do `order_id`) e
    # escreve-o de volta na mutação — lê-se daqui para a resposta.
    mutation = PreviewMutation(
        operation_id=body.operation_id,
        order_id=body.order_id,
        new_phase_id=body.new_phase_id,
        new_worker_ids=body.new_worker_ids,
    )
    try:
        commit = await svc.apply(mutation, author=user, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "commit_sha": commit.commit_sha256,
        "parent_sha": None if commit.parent_id is None else "see /v1/plan/cpo/commits",
        "operation_id": mutation.operation_id,
        "applied_by": user,
        "reason": body.reason,
    }
