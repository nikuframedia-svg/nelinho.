"""Q.140.C — API de sectores: lista de sectores + ranking por sector.

Endpoints read-only (a edição de níveis é o PATCH em employee_extras_api):

    GET /v1/workforce/sectors                       — os 7 grupos de área
    GET /v1/workforce/sectors/ranking?area_group=   — ranking inverso do sector

`area_group` é query param (não path) porque um dos grupos é "Cura/Moldes" —
a barra partiria um path param.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.workforce.levels import AREA_GROUPS
from src.workforce.sector_preference_service import (
    LEVEL_SCALE,
    SectorPreferenceService,
)
from src.shared.auth.headers import require_tenant_header

router = APIRouter(prefix="/v1/workforce/sectors", tags=["Workforce sectors"])


get_tenant_id = require_tenant_header


@router.get("")
async def list_sectors(
    tenant_id: UUID = Depends(get_tenant_id),
) -> dict:
    """Os 7 grupos de área (sectores) + a convenção de escala (3=melhor)."""
    return {"sectors": list(AREA_GROUPS), "level_scale": LEVEL_SCALE}


@router.get("/ranking")
async def sector_ranking(
    area_group: str = Query(..., description="Grupo de área (ex.: Laminagem, Cura/Moldes)."),
    limit: int = Query(100, ge=1, le=500),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Ranking inverso: colaboradores APTOS ao sector, ordenados por preferência.

    Só inclui quem já trabalhou no sector (axioma 5 — nunca alarga). Ordem
    determinística por (effective_level desc, ops desc, recência asc, id).
    """
    if area_group not in AREA_GROUPS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"sector desconhecido: {area_group!r} (válidos: {list(AREA_GROUPS)})",
        )
    svc = SectorPreferenceService(session, tenant_id)
    return await svc.sector_ranking(area_group, limit=limit)
