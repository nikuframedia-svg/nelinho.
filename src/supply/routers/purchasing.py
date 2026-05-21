"""
Supply purchasing endpoints — `/v1/supply/purchase-orders` + `/reconciliation*`.

Q.67.6.B4 — extracted from ``src/supply/api.py``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from ._common import (
    PurchaseOrderItem,
    PurchaseOrdersEnvelope,
    PurchaseOrdersSummary,
    ReconciliationCreateRequest,
    ReconciliationResponse,
    reconciliation_to_dict,
)


router = APIRouter(tags=["Supply Chain"])


@router.get("/purchase-orders", response_model=PurchaseOrdersEnvelope)
async def list_purchase_orders(
    status_filter: Optional[
        Literal["OPEN", "PARTIAL", "RECEIVED", "CANCELLED"]
    ] = None,
    product_code: Optional[str] = None,
    supplier: Optional[str] = None,
    open_only: bool = False,
    limit: int = 200,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Q.53.D — tracking de encomendas a fornecedor (tab Entregas).

    Lista as POs espelhadas em `supply.purchase_orders`: fornecedor,
    material, quantidade encomendada vs recebida, ETA e estado de receção.
    Fonte: ERP NELO `MOVIMENTO` tipo 9 ("Pedidos a fornecedor"), mirrored
    pelo ETL `purchase_orders`, mais POs criadas dentro do ProdPlan.

    Se o mirror nunca foi sincronizado devolve `data_available=false` com
    `unavailable_reason` — a UI mostra um empty-state explícito em vez de
    uma tabela vazia silenciosa (ZERO MOCKS).
    """
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="limit must be in [1, 1000]"
        )

    from src.supply import api as supply_api

    svc = supply_api.PurchaseOrderService(session, tenant_id)
    try:
        result = await svc.list_purchase_orders(
            status=status_filter,
            product_code=product_code,
            supplier=supplier,
            open_only=open_only,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PurchaseOrdersEnvelope(
        items=[PurchaseOrderItem(**i) for i in result["items"]],
        count=result["count"],
        data_available=result["data_available"],
        source=result["source"],
        last_synced_at=result["last_synced_at"],
        unavailable_reason=result["unavailable_reason"],
        summary=PurchaseOrdersSummary(**result["summary"]),
    )


@router.post(
    "/reconciliation",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reconciliation(
    sku_id: str,
    req: ReconciliationCreateRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """ST03/O.7 — submit a physical-count vs theoretical reconciliation."""
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    row = await svc.create_reconciliation(
        sku_id=sku_id,
        physical_qty=Decimal(str(req.physical_qty)),
        counted_by=req.counted_by,
        comments=req.comments,
    )
    return reconciliation_to_dict(row)


@router.get("/reconciliation", response_model=List[ReconciliationResponse])
async def list_reconciliations(
    since: Optional[datetime] = None,
    unresolved_only: bool = False,
    limit: int = 100,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="limit must be in [1, 1000]")

    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    rows = await svc.list_reconciliations(
        since=since, unresolved_only=unresolved_only, limit=limit,
    )
    return [reconciliation_to_dict(r) for r in rows]


@router.post(
    "/reconciliation/{reconciliation_id}/resolve",
    response_model=ReconciliationResponse,
)
async def resolve_reconciliation(
    reconciliation_id: UUID,
    resolved_by: Optional[str] = None,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    try:
        row = await svc.resolve_reconciliation(
            reconciliation_id=reconciliation_id, resolved_by=resolved_by,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    return reconciliation_to_dict(row)
