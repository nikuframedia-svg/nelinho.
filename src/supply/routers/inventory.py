"""
Supply inventory endpoints — `/v1/supply/inventory/*` + `/materials/{sku}/{adjust,movements,position}`.

Q.67.6.B4 — extracted from ``src/supply/api.py``. Uses lazy attribute
lookup on ``src.supply.api`` so that ``patch.object(supply_api,
"InventoryLedger")`` / ``"MaterialService"`` keeps intercepting the
collaborator that the endpoint actually instantiates.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from ._common import (
    CurrentInventoryResponse,
    InventoryMovementRequest,
    InventoryMovementResponse,
    StockAdjustRequest,
    StockAdjustResponse,
)


router = APIRouter(tags=["Supply Chain"])


@router.get("/inventory/{sku_id}", response_model=CurrentInventoryResponse)
async def get_current_inventory(
    sku_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Get current on-hand inventory for a SKU."""
    from src.supply import api as supply_api

    ledger = supply_api.InventoryLedger(session, tenant_id)
    on_hand = await ledger.get_current_on_hand(sku_id)
    return CurrentInventoryResponse(sku_id=sku_id, on_hand=float(on_hand))


@router.post(
    "/inventory/movement",
    response_model=InventoryMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_inventory_movement(
    request: InventoryMovementRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Record inventory movement (receipt, consumption, adjustment)."""
    from src.supply import api as supply_api

    ledger = supply_api.InventoryLedger(session, tenant_id)

    try:
        result = await ledger.record_movement(
            sku_id=request.sku_id,
            qty_change=request.qty_change,
            transaction_type=request.transaction_type,
            reference_id=request.reference_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    await session.commit()

    return InventoryMovementResponse(
        sku_id=result["sku_id"],
        on_hand_after=float(result["on_hand_after"]),
        qty_opening=float(result["qty_opening"]),
        qty_closing=float(result["qty_closing"]),
        reference_id=str(result["reference_id"]) if result["reference_id"] else None,
    )


@router.get("/materials/{sku_id}/position")
async def get_material_position(
    sku_id: str,
    horizon_days: int = 14,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Prospeção material (MR02) — on-hand + in-transit vs min_stock.

    Devolve um payload livre porque a forma exacta varia com a config do
    tenant (depth de horizon, alertas activos). Não usa `response_model`
    intencionalmente.
    """
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    return await svc.get_position(sku_id=sku_id, horizon_days=horizon_days)


@router.post("/materials/{sku_id}/adjust", response_model=StockAdjustResponse)
async def adjust_stock(
    sku_id: str,
    req: StockAdjustRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """MR06/ST01 — manual adjustment that NEVER lets on-hand go negative."""
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    try:
        result = await svc.adjust_stock(
            sku_id=sku_id,
            qty_delta=Decimal(str(req.qty_delta)),
            reason=req.reason,
            actor=req.actor,
            reference_id=req.reference_id,
        )
    except supply_api.NegativeStockBlockedError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "NEGATIVE_STOCK_BLOCKED",
                "sku_id": exc.sku_id,
                "current_qty": float(exc.current),
                "requested_delta": float(exc.delta),
            },
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return StockAdjustResponse(
        sku_id=result["sku_id"],
        on_hand_after=float(result["on_hand_after"]),
        qty_opening=float(result["qty_opening"]),
        qty_closing=float(result["qty_closing"]),
        qty_delta=result["qty_delta"],
        reason=result["reason"],
    )


@router.get("/materials/{sku_id}/movements")
async def get_movements(
    sku_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    transaction_type: Optional[Literal["consume", "receive", "adjust"]] = None,
    limit: int = 100,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """ST02/MR07 — inventory movement history. Payload livre."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="limit must be in [1, 1000]")

    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    return await svc.get_movements(
        sku_id=sku_id,
        since=since,
        until=until,
        transaction_type=transaction_type,
        limit=limit,
    )
