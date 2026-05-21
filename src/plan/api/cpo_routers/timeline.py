"""Q.67.6.B2 — sub-router para `/timeline` (Sprint K.2).

Endpoint:
* GET /timeline — up to 10 MAP-Elites candidate schedules from the last
  commit (or the commit identified by `commit_sha`). Humans pick one to
  promote via a governance decision.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.api._cpo_common import _resolve_commit_or_404, _tenant_id
from src.plan.cpo.commits import CommitsService
from src.shared.database import get_session

router = APIRouter()


# =============================================================================
# Response schemas
# =============================================================================

class TimelineCandidate(BaseModel):
    rank: int
    fitness: float
    generation: int
    behavioral: Dict[str, float]
    chromosome: Dict[str, Any]


class TimelineResponse(BaseModel):
    commit_sha256: Optional[str]
    candidates: List[TimelineCandidate]


# =============================================================================
# GET /timeline (Sprint K.2)
# =============================================================================

@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    commit_sha: Optional[str] = Query(default=None),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """
    Return up to 10 MAP-Elites candidate schedules from the last commit
    (or the commit identified by `commit_sha`).
    Humans pick one to promote via a governance decision.
    """
    service = CommitsService(db, tenant_id)
    if commit_sha:
        commit = await _resolve_commit_or_404(service, commit_sha)
    else:
        commit = await service.get_latest()
    if commit is None:
        return TimelineResponse(commit_sha256=None, candidates=[])

    candidates = [
        TimelineCandidate(
            rank=int(c.get("rank", 0)),
            fitness=float(c.get("fitness", 0.0)),
            generation=int(c.get("generation", 0)),
            behavioral=dict(c.get("behavioral", {})),
            chromosome=dict(c.get("chromosome", {})),
        )
        for c in (commit.alternatives or [])
    ]
    return TimelineResponse(
        commit_sha256=commit.commit_sha256,
        candidates=candidates,
    )
