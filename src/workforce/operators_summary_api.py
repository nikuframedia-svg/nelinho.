"""Q.159 — Resumo de operadores ativos (contagem + quebra por área).

Fonte única: `factory_raw.v_active_operators` (E_ACTIVO + trabalho nos últimos 2
meses, ~107). A quebra por área deriva de `offp_eq ⋈ of_fp ⋈ fases_producao`
(só `FP_PRODUCAO=true`, últimos 60d) — uma pessoa conta em várias áreas
(polivalência), por isso a soma das áreas > contagem total.

    GET /v1/workforce/operators/summary  → {count, window_days, by_area:[{area,ops}]}

Read-only. Se a view não existir (dev/test sem sync), devolve count=0 / by_area=[]
em vez de rebentar — estado honesto, nunca mock.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.shared.auth.headers import require_tenant_header

router = APIRouter(prefix="/v1/workforce/operators", tags=["Workforce operators"])

# Janela canónica (ver scripts/q159_setup_active_operators_view.py — "últimos 2 meses").
_WINDOW_DAYS = 60

_BY_AREA_SQL = text(
    """
    SELECT f."FP_NOME"                      AS area,
           count(DISTINCT eq."OFFPEQ_E_ID") AS ops
    FROM factory_raw.v_active_operators ao
    JOIN factory_raw.offp_eq eq ON eq."OFFPEQ_E_ID" = ao.e_id
    JOIN factory_raw.of_fp   o  ON o."OFFP_ID"      = eq."OFFPEQ_OFFP_ID"
    JOIN factory_raw.fases_producao f ON f."FP_ID" = o."OFFP_FP_ID"
    WHERE f."FP_PRODUCAO" = true
      AND NULLIF(o."OFFP_DATAINICIO", '')::timestamp >= now() - interval '60 days'
    GROUP BY f."FP_NOME"
    ORDER BY ops DESC
    """
)


get_tenant_id = require_tenant_header


@router.get("/summary")
async def operators_summary(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Contagem de operadores ativos (~107) + quebra por área."""
    view_exists = await session.scalar(
        text(
            "SELECT 1 FROM information_schema.views "
            "WHERE table_schema = 'factory_raw' "
            "AND table_name = 'v_active_operators'"
        )
    )
    if not view_exists:
        return {"count": 0, "window_days": _WINDOW_DAYS, "by_area": []}

    count = await session.scalar(
        text("SELECT count(*) FROM factory_raw.v_active_operators")
    )
    rows = await session.execute(_BY_AREA_SQL)
    by_area = [{"area": r.area, "ops": int(r.ops)} for r in rows]
    return {
        "count": int(count or 0),
        "window_days": _WINDOW_DAYS,
        "by_area": by_area,
    }
