"""Timeline endpoints — pending dashboard + cross-decision audit stream.

Q.67.6.B5 — split from the legacy ``src/governance/api.py``.

Two read endpoints:
* ``GET /decisions/timeline`` (Sprint M.1 — WG02/WG08) — grouped pending
  dashboard with anti-fatigue filters.
* ``GET /audit/timeline`` (Sprint M.6 — WG06) — chronological cross-decision
  event stream (propose/approve/execute/rollback).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..service import GovernanceService
from ._dependencies import get_governance_service

router = APIRouter(tags=["Governance"])


@router.get("/decisions/timeline")
async def get_timeline(
    group_by: str = Query(
        "criticality",
        description="criticality | risk_level | decision_type | status",
    ),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    actor_id: Optional[str] = Query(None, description="Proposer filter"),
    autonomy_level: Optional[str] = Query(None),
    min_impact: Optional[float] = Query(
        None,
        description="WG08 anti-fatigue: hide decisions with expected_impact magnitude below this",
    ),
    hide_low_risk: bool = Query(False, description="WG08 anti-fatigue"),
    max_per_user_shown: Optional[int] = Query(
        None,
        description="WG08 anti-fatigue: cap rows per proposer inside each group",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    service: GovernanceService = Depends(get_governance_service),
):
    """Pending-decision dashboard grouped by criticality / risk / type / status."""
    try:
        return await service.get_timeline(
            group_by=group_by,
            since=since, until=until,
            actor_id=actor_id, autonomy_level=autonomy_level,
            min_impact=min_impact,
            hide_low_risk=hide_low_risk,
            max_per_user_shown=max_per_user_shown,
            page=page, page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/audit/timeline")
async def get_audit_timeline(
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    actor: Optional[str] = Query(None),
    limit: int = Query(200, ge=10, le=1000),
    service: GovernanceService = Depends(get_governance_service),
):
    """Chronological cross-decision event stream (propose/approve/execute/rollback)."""
    return {
        "events": await service.get_audit_timeline(
            since=since, until=until, actor=actor, limit=limit,
        ),
    }


__all__ = ["router"]
