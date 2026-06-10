"""Rule firing log endpoints — Sprint Q.14.A + Q.14.C.

Q.67.6.B5 — split from the legacy ``src/governance/api.py``.

Three endpoints:
* ``GET /rule-firings`` — cursor-paginated audit log of detector firings.
* ``PATCH /rule-firings/{id}/outcome`` — operator decision (closes the loop
  for the A/B framework, which reads accepted/(accepted+rejected+expired)).
* ``GET /rule-firings/adoption`` — Bayesian per-variant adoption stats.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session

from ._dependencies import get_current_user, get_tenant_id
from src.shared.time import utc_now

router = APIRouter(tags=["Governance"])


class RuleFiringResponse(BaseModel):
    """One audit row from `governance.rule_firing`."""

    id: str
    rule_id: str
    variant_id: Optional[str] = None
    fired_at: str
    last_fired_at: Optional[str] = None
    fire_count: int
    outcome: str
    dedupe_key: Optional[str] = None
    correlation_id: Optional[str] = None
    trigger_payload: Dict[str, Any] = Field(default_factory=dict)
    rule_output: Dict[str, Any] = Field(default_factory=dict)
    accepted_at: Optional[str] = None
    accepted_by: Optional[str] = None
    notes: Optional[str] = None


class RuleFiringOutcomeUpdate(BaseModel):
    """Body for `PATCH /v1/governance/rule-firings/{id}/outcome`."""

    outcome: str = Field(..., description="New outcome: accepted/rejected/expired/superseded")
    notes: Optional[str] = Field(None, max_length=1000)


@router.get(
    "/rule-firings",
    response_model=List[RuleFiringResponse],
)
async def list_rule_firings(
    rule_id: Optional[str] = Query(None, description="Filter by rule_id"),
    outcome: Optional[str] = Query(
        None,
        description="Filter by outcome (proposed/accepted/rejected/expired/superseded)",
    ),
    since: Optional[datetime] = Query(
        None, description="Only firings on/after this timestamp (UTC)",
    ),
    until: Optional[datetime] = Query(
        None, description="Only firings before this timestamp (UTC)",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> List[RuleFiringResponse]:
    """List rule firings for the current tenant.

    Sprint Q.14.A — answers the *"why did the system suggest X 3 weeks
    ago?"* question. Filters compose with AND. Default order is most-
    recent first (so paginating "give me the last 50" works without a
    cursor).
    """
    from sqlalchemy import select

    from src.governance.models import RuleFiring

    stmt = (
        select(RuleFiring)
        .where(RuleFiring.tenant_id == tenant_id)
        .order_by(RuleFiring.fired_at.desc())
    )
    if rule_id is not None:
        stmt = stmt.where(RuleFiring.rule_id == rule_id)
    if outcome is not None:
        stmt = stmt.where(RuleFiring.outcome == outcome)
    if since is not None:
        stmt = stmt.where(RuleFiring.fired_at >= since)
    if until is not None:
        stmt = stmt.where(RuleFiring.fired_at < until)

    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()

    return [
        RuleFiringResponse(
            id=str(r.id),
            rule_id=r.rule_id,
            variant_id=r.variant_id,
            fired_at=r.fired_at.isoformat(),
            last_fired_at=(
                r.last_fired_at.isoformat() if r.last_fired_at else None
            ),
            fire_count=r.fire_count,
            outcome=r.outcome,
            dedupe_key=r.dedupe_key,
            correlation_id=str(r.correlation_id) if r.correlation_id else None,
            trigger_payload=r.trigger_payload or {},
            rule_output=r.rule_output or {},
            accepted_at=r.accepted_at.isoformat() if r.accepted_at else None,
            accepted_by=str(r.accepted_by) if r.accepted_by else None,
            notes=r.notes,
        )
        for r in rows
    ]


@router.patch("/rule-firings/{firing_id}/outcome")
async def update_rule_firing_outcome(
    firing_id: UUID,
    payload: RuleFiringOutcomeUpdate,
    tenant_id: UUID = Depends(get_tenant_id),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update the outcome of a rule firing — closes the audit loop.

    When an operator accepts / rejects a suggestion in the UI, the
    frontend posts here. The Q.14.C A/B framework reads
    ``accepted/(accepted+rejected+expired)`` per ``rule_id`` to compare
    variants. Without this endpoint, every row stays at ``proposed``
    forever and adoption stats are meaningless.
    """
    from sqlalchemy import select, update

    from src.governance.models import RuleFiring, RuleFiringOutcome

    valid_outcomes = {
        RuleFiringOutcome.ACCEPTED.value,
        RuleFiringOutcome.REJECTED.value,
        RuleFiringOutcome.EXPIRED.value,
        RuleFiringOutcome.SUPERSEDED.value,
    }
    if payload.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid outcome '{payload.outcome}'. "
                f"Allowed: {sorted(valid_outcomes)}"
            ),
        )

    stmt = select(RuleFiring).where(
        RuleFiring.id == firing_id,
        RuleFiring.tenant_id == tenant_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"rule firing {firing_id} not found in this tenant",
        )

    now = utc_now()
    user_uuid: Optional[UUID] = None
    try:
        user_uuid = UUID(str(user))
    except (ValueError, TypeError):
        # `get_current_user` returns a string; if it's not a UUID,
        # we keep accepted_by NULL but still record the notes/outcome.
        pass

    # Q.66.B.3: RuleFiring e ELE PROPRIO um audit-trail row (registo de
    # quando uma rule disparou); este UPDATE so altera outcome/accepted_by/
    # notes na mesma row de audit — record_rule_firing ja foi a fonte
    # original. Auto-audit via colunas accepted_at/accepted_by/outcome.
    await db.execute(  # noqa: audit_coverage  # audit-trail row self-update (outcome/notes)
        update(RuleFiring)
        .where(RuleFiring.id == firing_id)
        .values(
            outcome=payload.outcome,
            accepted_at=now if payload.outcome == RuleFiringOutcome.ACCEPTED.value else row.accepted_at,
            accepted_by=user_uuid if payload.outcome == RuleFiringOutcome.ACCEPTED.value else row.accepted_by,
            notes=payload.notes,
        )
    )
    await db.commit()
    return {"id": str(firing_id), "outcome": payload.outcome}


@router.get("/rule-firings/adoption")
async def rule_firings_adoption(
    rule_id: str = Query(..., description="rule_id to summarise"),
    credible_interval: float = Query(
        0.95, ge=0.5, lt=1.0,
        description="Bayesian credible interval level (0.5-0.99)",
    ),
    min_sample: int = Query(
        50, ge=1,
        description="Minimum decided firings per variant before winner declared",
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Per-variant adoption stats for an A/B'd rule.

    Sprint Q.14.C — answers *"is variant A actually beating variant B?"*
    Aggregates `rule_firing` rows by `(variant_id, outcome)` and returns
    per-variant Bayesian Beta-Bernoulli posterior + 95% credible
    interval. A "winner" is declared only when the top variant's CI
    sits strictly above the runner-up's CI AND both have enough sample
    (`min_sample`, default 50).
    """
    from sqlalchemy import func, select

    from src.governance.ab_framework import compute_adoption_stats
    from src.governance.models import RuleFiring

    stmt = (
        select(
            RuleFiring.variant_id,
            RuleFiring.outcome,
            func.count(RuleFiring.id).label("n"),
        )
        .where(RuleFiring.tenant_id == tenant_id)
        .where(RuleFiring.rule_id == rule_id)
        .where(RuleFiring.variant_id.is_not(None))
        .group_by(RuleFiring.variant_id, RuleFiring.outcome)
    )
    result = await db.execute(stmt)
    rows = [
        (variant_id, outcome, int(n))
        for variant_id, outcome, n in result.all()
    ]

    report = compute_adoption_stats(
        rule_id=rule_id,
        rows=rows,
        credible_interval=credible_interval,
        min_sample_for_winner=min_sample,
    )
    return report.to_dict()


__all__ = ["router", "RuleFiringResponse", "RuleFiringOutcomeUpdate"]
