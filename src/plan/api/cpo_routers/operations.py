"""Q.67.6.B2 — sub-router para `/operations/{id}/worker-pairs` (Sprint Q.13.A).

Endpoint:
* GET /operations/{operation_id}/worker-pairs — top-N pair candidates.

Plan v4 §6.2 promises the manager sees alternative worker pairs BEFORE
confirming an assignment, with scores. This endpoint backs the
`<WorkerPairCard>` component on DragDropPlanner.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.api._cpo_common import _tenant_id
from src.plan.cpo.commits import CommitsService
from src.plan.cpo.state import FactoryState
from src.shared.database import get_session

router = APIRouter()


# =============================================================================
# Response schemas
# =============================================================================

class WorkerPairItem(BaseModel):
    """One ranked pair candidate. The frontend §6.2 promise renders these
    side-by-side with their score so the manager sees, e.g.:

    "Paulo Gomes + Maria Silva (8.2) OU João Costa + Ana Reis (6.1)"
    """
    chefe_id: str = Field(..., description="ERP employee_id of the team leader")
    partner_id: Optional[str] = Field(
        default=None,
        description="ERP employee_id of the partner (null for solo fallback "
                    "in PREFERRED-only phases like Laminagem post-Q.8)",
    )
    score: float = Field(
        ..., ge=0.0, le=10.0,
        description="Display score 0-10 (higher is better). 10 = lowest cost "
                    "in the pool; 0 = highest cost. Rounded to 0.1.",
    )


class WorkerPairsResponse(BaseModel):
    operation_id: str
    phase_id: Optional[str] = None
    needs_pair: bool = Field(
        ..., description="True iff the phase is in PAIR_REQUIRED or "
                          "PAIR_PREFERRED — when False, the response is empty.",
    )
    pairs: List[WorkerPairItem]


# =============================================================================
# GET /operations/{operation_id}/worker-pairs (Sprint Q.13.A)
# =============================================================================

@router.get(
    "/operations/{operation_id}/worker-pairs",
    response_model=WorkerPairsResponse,
)
async def get_worker_pairs(
    operation_id: str,
    top_n: int = Query(default=3, ge=1, le=10),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Sprint Q.13.A — top-N pair candidates for an op.

    Plan v4 §6.2 promises the manager sees alternative worker pairs
    BEFORE confirming an assignment, with scores. This endpoint backs
    the `<WorkerPairCard>` component on DragDropPlanner.

    Resolves the op from the latest ScheduleCommit (so the operator
    is choosing between alternatives for an already-planned op, not
    a hypothetical one). The phase + skill pool are read from the
    loaded `FactoryState`. Returns `needs_pair=False` + empty pairs
    list when the op's phase doesn't need a pair (the frontend then
    renders the single-worker UI).
    """
    state = await FactoryState.load(db, tenant_id)
    commits = CommitsService(db, tenant_id)
    parent = await commits.get_latest()
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no schedule commit yet — run /v1/plan/cpo/schedule first",
        )

    target_op = None
    for op_dict in (parent.operations or []):
        if str(op_dict.get("operation_id") or "") == operation_id:
            target_op = op_dict
            break
    if target_op is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"operation_id {operation_id!r} not found in latest commit",
        )

    # Build a thin SchedulingOperation just for pair_assignment lookup —
    # we only need phase_id + operation_id, not the full op.
    from src.plan.cpo.pair_assignment import (
        needs_pair_assignment,
        rank_pairs,
    )
    from src.plan.engines.scheduling_adapter import SchedulingOperation

    op = SchedulingOperation(
        operation_id=operation_id,
        order_id=str(target_op.get("order_id") or ""),
        product_id=str(target_op.get("product_id") or ""),
        sequence=int(target_op.get("sequence") or 0),
        operation_code=str(target_op.get("operation_code") or ""),
        duration_minutes=float(target_op.get("duration_minutes") or 0),
        machine_id=target_op.get("machine_id"),
        phase_id=str(target_op.get("phase_id") or ""),
    )

    needs = needs_pair_assignment(op, state)
    if not needs:
        return WorkerPairsResponse(
            operation_id=operation_id,
            phase_id=op.phase_id,
            needs_pair=False,
            pairs=[],
        )

    ranked = rank_pairs(op, state, top_n=top_n)
    return WorkerPairsResponse(
        operation_id=operation_id,
        phase_id=op.phase_id,
        needs_pair=True,
        pairs=[
            WorkerPairItem(
                chefe_id=str(p["chefe_id"]),
                partner_id=str(p["partner_id"]) if p["partner_id"] else None,
                score=float(p["score"]),
            )
            for p in ranked
        ],
    )
