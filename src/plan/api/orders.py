"""GET /v1/plan/orders/active — orders activos para PhaseColumnView.

Sprint Q.18.ZIP.BE.1.

Devolve lista flat de production orders em curso (``status=IN_PROGRESS``)
no formato consumido pelo BoatCard / PhaseColumnView do frontend Producao.

Resposta:
    [
      {
        "id": "<uuid>",
        "hull": "<legacy_id como string>",
        "product_name": "...",
        "product_type": "K1|K2|K4|C1|C2|C4|Other",
        "phase": "<current_phase_name>",
        "status": "IN_PROGRESS",
        "created_date": "YYYY-MM-DD" | null,
        "transport_date": "YYYY-MM-DD" | null
      },
      ...
    ]

Endpoint só lê — drag-drop entre fases continua a passar por
``schedulePreviewApi.previewDelta`` (Q.4) que gera o ConsequenceBlock.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.order import OrderStatus, ProductionOrder
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(tags=["PLAN.Orders"])


def _order_to_card(o: ProductionOrder) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "hull": str(o.legacy_id) if o.legacy_id is not None else None,
        "product_name": o.product_name,
        "product_type": o.product_type,
        "phase": o.current_phase_name,
        "status": o.status.value if hasattr(o.status, "value") else str(o.status),
        "created_date": o.created_date.isoformat() if o.created_date else None,
        "transport_date": o.transport_date.isoformat() if o.transport_date else None,
    }


@router.get("/orders/active")
async def list_active_orders(
    phase: str | None = Query(None, description="Filtrar por current_phase_name."),
    limit: int = Query(200, ge=1, le=2000),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(ProductionOrder)
        .where(ProductionOrder.tenant_id == tenant_id)
        .where(ProductionOrder.status == OrderStatus.IN_PROGRESS)
    )
    if phase:
        stmt = stmt.where(ProductionOrder.current_phase_name == phase)
    stmt = stmt.order_by(ProductionOrder.created_date.desc().nullslast()).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_order_to_card(o) for o in rows]
