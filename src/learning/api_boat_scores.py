"""Q.115.X6 — endpoints de afinidade barco/fase e potencialidade por barco.

GET /v1/learning/boat-phase-scores — top-N pares (boat, fase) ordenados por score.
GET /v1/learning/boat-potential    — top-N barcos ordenados por potential_score.

Read-only. Alimenta o tab Aprendizagem (complemento de /v1/learning/affinities).
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.models.boat_phase_score import BoatPhaseScore
from src.governance.models.boat_potential import BoatPotential
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/learning", tags=["Aprendizagem"])

_tenant_id = require_tenant_header


# ─── Schemas ─────────────────────────────────────────────────────────────────


class BoatPhaseScoreOut(BaseModel):
    boat_id: str
    phase_id: str
    score: float
    sample_count: int
    last_computed_at: datetime


class BoatPotentialOut(BaseModel):
    boat_id: str
    potential_score: float
    revenue_eur_lifetime: Decimal
    last_computed_at: datetime


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/boat-phase-scores", response_model=List[BoatPhaseScoreOut])
async def get_boat_phase_scores(
    boat_id: Optional[str] = Query(None, description="Filtra por barco"),
    phase_id: Optional[str] = Query(None, description="Filtra por fase"),
    top: Optional[int] = Query(10, ge=1, le=200, description="Top-N por score"),
    order: str = Query(
        "desc",
        pattern="^(asc|desc)$",
        description="asc=mais difíceis primeiro (pior score); desc=melhores primeiro",
    ),
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> List[BoatPhaseScoreOut]:
    """Devolve afinidades barco/fase ordenadas por score.

    Por omissão devolve descendente (melhores barcos primeiro). Com ``order=asc``
    devolve ascendente, útil para identificar os barcos mais exigentes por fase
    (consumido pelo FaseSheet do Q.116.A).

    Retorna lista vazia se o job ainda nunca correu.
    """
    stmt = select(BoatPhaseScore).where(
        BoatPhaseScore.tenant_id == tenant_id
    )
    if boat_id:
        stmt = stmt.where(BoatPhaseScore.boat_id == boat_id)
    if phase_id:
        stmt = stmt.where(BoatPhaseScore.phase_id == phase_id)

    if order == "asc":
        stmt = stmt.order_by(BoatPhaseScore.score.asc())
    else:
        stmt = stmt.order_by(BoatPhaseScore.score.desc())
    if top is not None:
        stmt = stmt.limit(top)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        BoatPhaseScoreOut(
            boat_id=r.boat_id,
            phase_id=r.phase_id,
            score=r.score,
            sample_count=r.sample_count,
            last_computed_at=r.last_computed_at,
        )
        for r in rows
    ]


@router.get("/boat-potential", response_model=List[BoatPotentialOut])
async def get_boat_potential(
    top: Optional[int] = Query(10, ge=1, le=200, description="Top-N por potential_score"),
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> List[BoatPotentialOut]:
    """Devolve barcos ordenados por potential_score descendente.

    Retorna lista vazia se o job ainda nunca correu.
    """
    stmt = (
        select(BoatPotential)
        .where(BoatPotential.tenant_id == tenant_id)
        .order_by(BoatPotential.potential_score.desc())
    )
    if top is not None:
        stmt = stmt.limit(top)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        BoatPotentialOut(
            boat_id=r.boat_id,
            potential_score=r.potential_score,
            revenue_eur_lifetime=r.revenue_eur_lifetime,
            last_computed_at=r.last_computed_at,
        )
        for r in rows
    ]
