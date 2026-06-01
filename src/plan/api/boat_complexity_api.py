"""Q.155.E — expõe o Índice de Complexidade do Barco (ICB) à UI.

GET /v1/plan/boat-complexity → lista por produto (id + nome + score + rank +
sinais brutos), para os badges de complexidade no /overall, CellOpsSheet e na
aba "Barcos exigentes". READ-only. Lê governance.boat_complexity (Q.155.A).
"""
from __future__ import annotations

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plan", tags=["Q.155 Complexidade do barco"])


class BoatComplexityItem(BaseModel):
    product_id: str
    product_name: str
    complexity_score: float  # [0,1] — UI mostra ×100
    rank: int
    n_components: int
    paint_kg_per_of: float
    n_distinct_phases: float


@router.get(
    "/boat-complexity",
    response_model=List[BoatComplexityItem],
    status_code=status.HTTP_200_OK,
)
async def list_boat_complexity(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[BoatComplexityItem]:
    try:
        rows = (
            await session.execute(
                text(
                    "SELECT product_id, product_name, complexity_score, rank, "
                    "n_components, paint_kg_per_of, n_distinct_phases "
                    "FROM governance.boat_complexity WHERE tenant_id = :t "
                    "ORDER BY rank"
                ),
                {"t": str(tenant_id)},
            )
        ).mappings().all()
    except Exception as exc:  # tabela ausente (job ainda não correu) → lista vazia
        logger.debug("list_boat_complexity skipped: %s", exc)
        return []
    return [
        BoatComplexityItem(
            product_id=str(r["product_id"]),
            product_name=str(r["product_name"] or r["product_id"]),
            complexity_score=float(r["complexity_score"]),
            rank=int(r["rank"]),
            n_components=int(r["n_components"]),
            paint_kg_per_of=float(r["paint_kg_per_of"]),
            n_distinct_phases=float(r["n_distinct_phases"]),
        )
        for r in rows
    ]
