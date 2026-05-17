"""ProdPlan ONE — Phase Transition Gaps API (Sprint X.3 / L2 lacuna).

Read+write surface over the 16 cura/secagem transitions in
``plan.phase_transition_gap``. Until this PR these gaps were only
editable via direct DB writes — Plan v4 §4.7 calls them out as
"química real" (epoxy cure, paint dry, glue set) and any change should
be deliberate, audited, and surfaced in the UI.

Two endpoints:

* ``GET  /v1/plan/phase-gaps``           — merged view (DB rows where
                                           present, ``NELO_CURING_GAPS_SEED``
                                           rows otherwise).
* ``PATCH /v1/plan/phase-gaps/{from}/{to}`` — upsert + reason ≥10 chars,
                                              the same gate the operator
                                              UI mirrors client-side.

The CPO scheduler reads ``plan.phase_transition_gap`` via
:func:`src.plan.cpo.state._load_phase_transition_gaps`, which already
falls back to the SEED — so before this PR existed, edits weren't
surfaced anywhere. Now: edit here → next ``/v1/plan/cpo/schedule`` run
picks the new value via the same loader path. No state.py changes
needed.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.cpo.state import NELO_CURING_GAPS_SEED, normalize_phase_code
from src.plan.models.phase_gap import PhaseTransitionGap
from src.shared.auth.headers import require_tenant_header, require_user_uuid
from src.shared.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/phase-gaps", tags=["PLAN"])

REASON_MIN_LEN = 10


# ─── Schemas ─────────────────────────────────────────────────────────────


class PhaseGapOut(BaseModel):
    from_phase_code: str
    to_phase_code: str
    min_gap_hours: float
    reason: Optional[str] = None
    n_observations: Optional[int] = None
    active: bool = True
    # 'seed' when the row only exists in NELO_CURING_GAPS_SEED (not yet
    # written to plan.phase_transition_gap for this tenant); 'db' when
    # the row is persisted. The UI uses this to render the badge.
    source: str


class PhaseGapsResponse(BaseModel):
    items: list[PhaseGapOut]


class PhaseGapPatchIn(BaseModel):
    min_gap_hours: float = Field(..., gt=0, le=72)
    reason: str = Field(
        ...,
        min_length=REASON_MIN_LEN,
        max_length=512,
        description=(
            "Razão obrigatória (≥10 chars) — química real, mudanças sem "
            "evidência podem produzir defeitos. Alimenta a aprendizagem."
        ),
    )


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=PhaseGapsResponse)
async def list_phase_gaps(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> PhaseGapsResponse:
    """Merged view: DB row per (from, to) where it exists, fallback to seed.

    The 16 entries from ``NELO_CURING_GAPS_SEED`` are always returned
    so a fresh tenant immediately sees the canonical cura/secagem
    table. Operator edits add a DB row that overrides the seed for
    that tenant only.
    """
    stmt = select(PhaseTransitionGap).where(
        PhaseTransitionGap.tenant_id == tenant_id,
    )
    rows = (await session.execute(stmt)).scalars().all()
    db_by_pair: dict[tuple[str, str], PhaseTransitionGap] = {}
    for r in rows:
        key = (
            normalize_phase_code(r.from_phase_code),
            normalize_phase_code(r.to_phase_code),
        )
        db_by_pair[key] = r

    items: list[PhaseGapOut] = []
    seen: set[tuple[str, str]] = set()

    # 1) Seed entries first (canonical order from state.py).
    for from_p, to_p, hours, reason, n_obs in NELO_CURING_GAPS_SEED:
        key = (normalize_phase_code(from_p), normalize_phase_code(to_p))
        seen.add(key)
        existing = db_by_pair.get(key)
        if existing is not None:
            items.append(
                PhaseGapOut(
                    from_phase_code=existing.from_phase_code,
                    to_phase_code=existing.to_phase_code,
                    min_gap_hours=float(existing.min_gap_hours),
                    reason=existing.reason,
                    n_observations=existing.n_observations,
                    active=existing.active,
                    source="db",
                )
            )
        else:
            items.append(
                PhaseGapOut(
                    from_phase_code=from_p,
                    to_phase_code=to_p,
                    min_gap_hours=float(hours),
                    reason=reason,
                    n_observations=n_obs,
                    active=True,
                    source="seed",
                )
            )

    # 2) Any DB rows that have NO seed counterpart (manual extras).
    for key, r in db_by_pair.items():
        if key in seen:
            continue
        items.append(
            PhaseGapOut(
                from_phase_code=r.from_phase_code,
                to_phase_code=r.to_phase_code,
                min_gap_hours=float(r.min_gap_hours),
                reason=r.reason,
                n_observations=r.n_observations,
                active=r.active,
                source="db",
            )
        )

    return PhaseGapsResponse(items=items)


@router.patch(
    "/{from_phase_code}/{to_phase_code}",
    response_model=PhaseGapOut,
)
async def update_phase_gap(
    from_phase_code: str,
    to_phase_code: str,
    body: PhaseGapPatchIn,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> PhaseGapOut:
    """Upsert the gap for one transition with mandatory reason ≥10 chars.

    The reason field carries the audit trail — Plan v4 §4.7 explicitly
    says cura/secagem mudanças são química real e exigem justificação.
    The CPO scheduler picks up the new value on the next
    ``/v1/plan/cpo/schedule`` run (no cache invalidation needed because
    ``state._load_phase_transition_gaps`` reads fresh on every load).
    """
    if not from_phase_code or not to_phase_code:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="from_phase_code and to_phase_code are required",
        )

    norm_from = normalize_phase_code(from_phase_code)
    norm_to = normalize_phase_code(to_phase_code)
    if not norm_from or not norm_to:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="phase codes cannot be empty after normalization",
        )

    stmt = select(PhaseTransitionGap).where(
        PhaseTransitionGap.tenant_id == tenant_id,
        PhaseTransitionGap.from_phase_code == norm_from,
        PhaseTransitionGap.to_phase_code == norm_to,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        # Bootstrap from SEED if available so legacy reason / n_observations
        # carry over for audit purposes.
        seed_match = next(
            (
                (h, r, n)
                for f, t, h, r, n in NELO_CURING_GAPS_SEED
                if normalize_phase_code(f) == norm_from
                and normalize_phase_code(t) == norm_to
            ),
            None,
        )
        n_obs_seed = seed_match[2] if seed_match else None
        new_row = PhaseTransitionGap(
            tenant_id=tenant_id,
            from_phase_code=norm_from,
            to_phase_code=norm_to,
            min_gap_hours=Decimal(str(body.min_gap_hours)),
            reason=body.reason,
            n_observations=n_obs_seed,
            active=True,
        )
        session.add(new_row)
        await session.flush()
        existing = new_row
    else:
        existing.min_gap_hours = Decimal(str(body.min_gap_hours))
        existing.reason = body.reason
        existing.active = True
        await session.flush()

    logger.info(
        "phase-gap edited %s -> %s: %.2fh by user=%s reason=%r",
        norm_from,
        norm_to,
        body.min_gap_hours,
        user_id,
        body.reason[:80],
    )

    return PhaseGapOut(
        from_phase_code=existing.from_phase_code,
        to_phase_code=existing.to_phase_code,
        min_gap_hours=float(existing.min_gap_hours),
        reason=existing.reason,
        n_observations=existing.n_observations,
        active=existing.active,
        source="db",
    )
