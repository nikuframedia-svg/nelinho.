"""
Supply materials master endpoints — `/v1/supply/materials*`.

Q.67.6.B4 — extracted from ``src/supply/api.py``. Covers list/create
materials, BOM-derived catalogue with per-warehouse stock, min-stock
override. Adjust/movements/position live in ``inventory.py`` since they
mutate the inventory ledger.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.bom import BOMItem
from src.core.models.product import Product
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from ..models import WarehouseStock
from ._common import (
    BomMaterialResponse,
    BomMaterialsEnvelope,
    MaterialCreateRequest,
    MaterialResponse,
    MinStockPatchRequest,
    WarehouseStockBreakdown,
    material_to_dict,
)


router = APIRouter(tags=["Supply Chain"])


@router.get("/materials", response_model=List[MaterialResponse])
async def list_materials(
    active_only: bool = True,
    category: Optional[str] = None,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    rows = await svc.list_materials(active_only=active_only, category=category)
    return [material_to_dict(r) for r in rows]


@router.get("/materials/from-bom", response_model=BomMaterialsEnvelope)
async def list_materials_from_bom(
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 500,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Lista os materiais reais derivados da BOM, com stock por armazém.

    `supply.material_master` está vazio nesta instalação — os materiais reais
    da NELO são os componentes-folha de `core.bom_items` (um
    `component_product_id` que nunca aparece como `parent_product_id`),
    cruzados com `core.products` para nome, unidade e custo padrão.
    Ordenado por nº de BOMs que o consomem (os mais usados primeiro).

    O stock vem de `supply.warehouse_stock` — espelho do ERP NELO
    (view `produto_stocks_por_armazem`), sincronizado pelo ETL `stock`.
    `on_hand` é o total entre armazéns; `warehouses` é a repartição por
    armazém. Se o stock nunca foi sincronizado, `stock_available=false`.
    """
    limit = max(1, min(limit, 5000))

    # Produtos que são pai de alguma BOM → não são folha.
    parents = (
        select(BOMItem.parent_product_id)
        .where(BOMItem.tenant_id == tenant_id)
        .distinct()
    )

    # Componentes-folha + estatísticas de uso.
    leaf = (
        select(
            BOMItem.component_product_id.label("cid"),
            func.count(distinct(BOMItem.parent_product_id)).label("used_in_n_boms"),
            func.sum(BOMItem.quantity_per).label("total_qty_per"),
        )
        .where(BOMItem.tenant_id == tenant_id)
        .where(BOMItem.component_product_id.notin_(parents))
        .group_by(BOMItem.component_product_id)
        .subquery()
    )

    stmt = (
        select(
            Product.id,
            Product.product_code,
            Product.product_name,
            Product.base_unit,
            Product.standard_cost,
            Product.category,
            Product.product_type,
            leaf.c.used_in_n_boms,
            leaf.c.total_qty_per,
        )
        .join(leaf, leaf.c.cid == Product.id)
        .order_by(leaf.c.used_in_n_boms.desc(), Product.product_name)
    )
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            Product.product_name.ilike(like) | Product.product_code.ilike(like)
        )
    if category:
        stmt = stmt.where(Product.category == category)
    stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()

    # Stock por armazém — espelho local de `supply.warehouse_stock`, mantido
    # pelo ETL `stock`. `product_code` == `WarehouseStock.product_code`.
    stock_by_code: Dict[str, List[WarehouseStock]] = {}
    stock_synced_at: Optional[datetime] = None
    ws_rows = (
        await session.execute(
            select(WarehouseStock).where(WarehouseStock.tenant_id == tenant_id)
        )
    ).scalars().all()
    for ws in ws_rows:
        stock_by_code.setdefault(ws.product_code, []).append(ws)
        if stock_synced_at is None or ws.synced_at > stock_synced_at:
            stock_synced_at = ws.synced_at

    stock_available = len(ws_rows) > 0
    unavailable_reason: Optional[str] = None
    if not stock_available:
        unavailable_reason = (
            "O stock por armazém ainda não foi sincronizado. Corre o ETL "
            "`scripts/sync_nelo_erp.py --only stock` para espelhar a view "
            "`produto_stocks_por_armazem` do ERP NELO."
        )

    # Q.53.D — data prevista de rutura a partir do consumo histórico real.
    # O predictor lê o ledger (`InventoryLedgerEntry`, transaction_type=
    # "consume"); `product_code == sku_id` é a convenção desta instalação
    # (mesmo P_ID do ERP). Só prevemos materiais com stock conhecido — sem
    # on-hand não há data de rutura honesta. Materiais sem histórico de
    # consumo devolvem `predicted_stockout_date=None` com confidence "none".
    on_hand_by_code: Dict[str, float] = {}
    for r in rows:
        code = r.product_code
        ws_list = stock_by_code.get(code, [])
        if ws_list:
            on_hand_by_code[code] = float(
                sum(float(ws.stock) for ws in ws_list)
            )
    stockout_by_code: Dict[str, Dict[str, Any]] = {}
    if on_hand_by_code:
        from src.supply import api as supply_api

        predictor = supply_api.StockoutPredictor(session, tenant_id)
        stockout_by_code = await predictor.predict_many(
            on_hand_by_sku=on_hand_by_code
        )

    items: List[BomMaterialResponse] = []
    for r in rows:
        warehouses = sorted(
            (
                WarehouseStockBreakdown(
                    warehouse_id=ws.warehouse_id,
                    warehouse_name=ws.warehouse_name,
                    stock=float(ws.stock),
                )
                for ws in stock_by_code.get(r.product_code, [])
            ),
            key=lambda w: -w.stock,
        )
        on_hand = (
            sum(w.stock for w in warehouses) if warehouses else None
        )
        prediction = stockout_by_code.get(r.product_code)
        items.append(
            BomMaterialResponse(
                id=str(r.id),
                product_code=r.product_code,
                product_name=r.product_name,
                unit_of_measure=r.base_unit or "UN",
                standard_cost=(
                    float(r.standard_cost) if r.standard_cost is not None else None
                ),
                category=r.category,
                product_type=(
                    r.product_type.value
                    if hasattr(r.product_type, "value")
                    else str(r.product_type)
                ),
                used_in_n_boms=int(r.used_in_n_boms or 0),
                total_qty_per=(
                    float(r.total_qty_per) if r.total_qty_per is not None else None
                ),
                on_hand=on_hand,
                warehouses=warehouses,
                predicted_stockout_date=(
                    prediction["predicted_stockout_date"] if prediction else None
                ),
                stockout_confidence=(
                    prediction["confidence"] if prediction else None
                ),
                avg_daily_consumption=(
                    prediction["avg_daily_consumption"] if prediction else None
                ),
            )
        )

    return BomMaterialsEnvelope(
        items=items,
        count=len(items),
        stock_available=stock_available,
        stock_synced_at=stock_synced_at.isoformat() if stock_synced_at else None,
        stock_source=(
            "erp_nelo_warehouse_stock" if stock_available else "indisponivel"
        ),
        unavailable_reason=unavailable_reason,
    )


@router.post(
    "/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_material(
    req: MaterialCreateRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    try:
        row = await svc.create_material(
            sku_id=req.sku_id,
            name=req.name,
            min_stock_qty=Decimal(str(req.min_stock_qty)),
            reorder_qty=Decimal(str(req.reorder_qty)),
            lead_time_days=req.lead_time_days,
            unit_of_measure=req.unit_of_measure,
            category=req.category,
            critical_flag=req.critical_flag,
            default_supplier_id=req.default_supplier_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return material_to_dict(row)


@router.patch("/materials/{sku_id}/min-stock", response_model=MaterialResponse)
async def patch_min_stock(
    sku_id: str,
    req: MinStockPatchRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """MR05/O.3 — override the configured min_stock_qty."""
    from src.supply import api as supply_api

    svc = supply_api.MaterialService(session, tenant_id)
    try:
        row = await svc.update_min_stock(
            sku_id=sku_id,
            min_stock_qty=Decimal(str(req.min_stock_qty)),
        )
    except supply_api.MaterialNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Material {sku_id} not found")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return material_to_dict(row)
