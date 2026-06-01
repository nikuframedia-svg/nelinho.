"""Q.141.D — API da linha temporal: actuals (o que aconteceu) por intervalo.

GET /v1/plan/timeline/actuals?from=&to=&group_by=&granularity=

Serve o lado PASSADO da timeline /overall (o futuro vem do plano CPO). Read-only,
best-effort (tabela ausente → 200 vazio, nunca 5xx). `factory_raw` é o espelho
ERP partilhado; a camada de fases é tenant-agnóstica (ver service).

`granularity`:
* `raw`  — items individuais (1 por fase). Default para intervalos curtos.
* `day`  — agregado por (grupo × dia) + amostra (intervalos grandes / mês).
* `auto` — raw quando o intervalo ≤ 14 dias, day quando > 31 (espelha o toggle
  Dia/Semana/Mês do OverallPage).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.services.timeline_actuals_service import (
    TimelineActualsService,
    aggregate_by_day,
)
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timeline", tags=["Timeline"])

_MAX_RANGE_DAYS = 366
_VALID_GROUP = {"barco", "fase", "operador"}
_VALID_GRAN = {"raw", "day", "auto"}


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


@router.get("/actuals")
async def get_actuals(
    from_: date = Query(..., alias="from", description="Data inicial (YYYY-MM-DD)."),
    to: date = Query(..., description="Data final inclusiva (YYYY-MM-DD)."),
    group_by: Optional[str] = Query(None, description="barco | fase | operador (p/ day)."),
    granularity: str = Query("auto", description="raw | day | auto."),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """O que aconteceu no intervalo: fases (barcos/operadores) + expedições."""
    if to < from_:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "`to` anterior a `from`")
    if (to - from_).days > _MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"intervalo > {_MAX_RANGE_DAYS} dias")
    if group_by is not None and group_by not in _VALID_GROUP:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"group_by inválido (use {_VALID_GROUP})")
    if granularity not in _VALID_GRAN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"granularity inválido (use {_VALID_GRAN})")

    span = (to - from_).days
    gran = granularity
    if gran == "auto":
        gran = "day" if span > 31 else "raw"

    svc = TimelineActualsService(session, tenant_id)
    items, items_trunc = await svc.actuals_items(from_, to)
    expeditions, exp_trunc = await svc.expeditions(from_, to)

    resp: dict = {
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "granularity": gran,
        "group_by": group_by,
        "expeditions": expeditions,
        "truncated": bool(items_trunc or exp_trunc),
    }
    if gran == "day":
        gb = group_by or "barco"
        resp["group_by"] = gb
        resp["lanes"] = aggregate_by_day(items, gb)
        resp["items"] = []
    else:
        resp["items"] = items
        resp["lanes"] = []
    return resp
