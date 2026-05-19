"""
ProdPlan ONE - Supply Chain API
=================================

REST endpoints for Supply Chain Planning:
- Inventory ledger
- Demand forecasting (Prophet)
- ROP calculation
- ABC analysis

Sprint Q.12 — todos os endpoints declaram `response_model` explícito,
schemas Pydantic substituem `List[dict]` arbitrário, e o tenant é
validado via `require_tenant_header` (rejeita header em falta/zero UUID
em vez de aceitar silenciosamente).
"""

import logging
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.bom import BOMItem
from src.core.models.product import Product
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

from .abc_analysis import ABCAnalysis
from .forecaster import ARIMAForecaster
from .inventory_ledger import InventoryLedger
from .material_service import (
    MaterialNotFoundError,
    MaterialService,
    NegativeStockBlockedError,
)
from .rop_calculator import ROPCalculator

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/supply", tags=["Supply Chain"])


# ═══════════════════════════════════════════════════════════════════════════════
# Request / Response Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class HistoricalDemandPoint(BaseModel):
    """Um ponto histórico (data + quantidade) consumido pelo forecaster."""

    date: date_type
    quantity: float = Field(ge=0, description="Quantidade observada (>=0)")


class ForecastRequest(BaseModel):
    """Request for demand forecast."""

    sku_id: str = Field(min_length=1, max_length=100)
    historical_data: List[HistoricalDemandPoint] = Field(min_length=1)
    periods_ahead: int = Field(default=30, ge=1, le=365)


class ForecastResponse(BaseModel):
    """Resposta do forecaster — payload livre porque o conteúdo varia
    com o método (Prophet, ARIMA, MA…)."""

    sku_id: str
    forecast: List[Dict[str, Any]] = Field(default_factory=list)
    method: Optional[str] = None
    quality: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None


class InventoryMovementRequest(BaseModel):
    """Request for inventory movement."""

    sku_id: str = Field(min_length=1, max_length=100)
    qty_change: float
    transaction_type: Literal["consume", "receive", "adjust"]
    reference_id: Optional[UUID] = None


class InventoryMovementResponse(BaseModel):
    sku_id: str
    on_hand_after: float
    qty_opening: float
    qty_closing: float
    reference_id: Optional[str] = None


class CurrentInventoryResponse(BaseModel):
    sku_id: str
    on_hand: float


class ROPSkuResponse(BaseModel):
    """Saída do calculador de ROP. Mantém os campos crus do calculator."""

    sku_id: str
    rop: float
    base_rop: float
    safety_stock: float
    z_score: float
    service_level: float


class ABCSkuInput(BaseModel):
    sku_id: str
    value: float = Field(ge=0)


class ABCAnalysisRequest(BaseModel):
    skus_list: List[ABCSkuInput] = Field(min_length=1)


class ABCBucket(BaseModel):
    count: int
    skus: List[Dict[str, Any]]


class ABCDistributionResponse(BaseModel):
    distribution: Dict[str, ABCBucket]


class MaterialCreateRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    min_stock_qty: float = Field(default=0.0, ge=0)
    reorder_qty: float = Field(default=0.0, ge=0)
    lead_time_days: int = Field(default=7, ge=0)
    unit_of_measure: str = "UN"
    category: Optional[str] = None
    critical_flag: bool = False
    default_supplier_id: Optional[UUID] = None


class MinStockPatchRequest(BaseModel):
    min_stock_qty: float = Field(ge=0)


class StockAdjustRequest(BaseModel):
    qty_delta: float
    reason: str = Field(min_length=1, max_length=500)
    actor: Optional[str] = None
    reference_id: Optional[UUID] = None


class StockAdjustResponse(BaseModel):
    sku_id: str
    on_hand_after: float
    qty_opening: float
    qty_closing: float
    qty_delta: float
    reason: str


class ReconciliationCreateRequest(BaseModel):
    physical_qty: float = Field(ge=0)
    counted_by: Optional[str] = None
    comments: Optional[str] = None


class MaterialResponse(BaseModel):
    id: str
    sku_id: str
    name: str
    description: Optional[str] = None
    unit_of_measure: str
    category: Optional[str] = None
    default_supplier_id: Optional[str] = None
    lead_time_days: int
    min_stock_qty: float
    reorder_qty: float
    safety_stock_days: Optional[int] = None
    critical_flag: bool
    active: bool


class BomMaterialResponse(BaseModel):
    """Material derivado da BOM — componente-folha de `core.bom_items`.

    Os materiais reais da NELO não vivem em `supply.material_master` (vazio),
    mas como produtos componente de uma BOM que nunca são, eles próprios,
    produto-pai. Este endpoint expõe esses componentes-folha.

    O stock (`on_hand`/`min_stock`) vem ao vivo do ERP NELO (`dbo.PRODUTO`,
    colunas `P_STOCK`/`P_STOCKMIN`). Quando o ERP não está ligado, esses
    campos ficam `null` e `BomMaterialsEnvelope.erp_available` é `false`.
    """

    id: str
    product_code: str
    product_name: str
    unit_of_measure: str
    standard_cost: Optional[float] = None
    category: Optional[str] = None
    product_type: str
    used_in_n_boms: int = Field(description="Nº de BOMs distintas que consomem este material")
    total_qty_per: Optional[float] = Field(
        default=None, description="Soma de quantity_per em todas as BOMs"
    )
    on_hand: Optional[float] = Field(
        default=None, description="Stock atual (ERP NELO P_STOCK) — null se ERP offline"
    )
    min_stock: Optional[float] = Field(
        default=None, description="Stock mínimo (ERP NELO P_STOCKMIN) — null se ERP offline"
    )
    below_min: Optional[bool] = Field(
        default=None, description="on_hand < min_stock (só quando há leitura de stock)"
    )


class BomMaterialsEnvelope(BaseModel):
    """Catálogo de materiais derivado da BOM + estado da leitura de stock."""

    items: List[BomMaterialResponse]
    count: int
    erp_available: bool = Field(
        description="True se o stock veio ao vivo do ERP NELO"
    )
    stock_source: str = Field(
        description="'nelo_erp_live' ou 'indisponivel'"
    )
    unavailable_reason: Optional[str] = None


class ReconciliationResponse(BaseModel):
    id: str
    sku_id: str
    theoretical_qty: float
    physical_qty: float
    variance_qty: float
    variance_pct: Optional[float] = None
    counted_at: Optional[str] = None
    counted_by: Optional[str] = None
    comments: Optional[str] = None
    resolved: bool
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _material_to_dict(m) -> Dict[str, Any]:
    return {
        "id": str(m.id),
        "sku_id": m.sku_id,
        "name": m.name,
        "description": m.description,
        "unit_of_measure": m.unit_of_measure,
        "category": m.category,
        "default_supplier_id": str(m.default_supplier_id) if m.default_supplier_id else None,
        "lead_time_days": m.lead_time_days,
        "min_stock_qty": float(m.min_stock_qty),
        "reorder_qty": float(m.reorder_qty),
        "safety_stock_days": m.safety_stock_days,
        "critical_flag": m.critical_flag,
        "active": m.active,
    }


def _reconciliation_to_dict(r) -> Dict[str, Any]:
    return {
        "id": str(r.id),
        "sku_id": r.sku_id,
        "theoretical_qty": float(r.theoretical_qty),
        "physical_qty": float(r.physical_qty),
        "variance_qty": float(r.variance_qty),
        "variance_pct": r.variance_pct,
        "counted_at": r.counted_at.isoformat() if r.counted_at else None,
        "counted_by": r.counted_by,
        "comments": r.comments,
        "resolved": r.resolved,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "resolved_by": r.resolved_by,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints — forecasting / inventory / ROP / ABC
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/forecast", response_model=ForecastResponse)
async def forecast_demand(
    request: ForecastRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Generate demand forecast for a SKU."""
    forecaster = ARIMAForecaster()

    result = await forecaster.forecast(
        sku_id=request.sku_id,
        historical_data=[p.model_dump() for p in request.historical_data],
        periods_ahead=request.periods_ahead,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )

    return ForecastResponse(
        sku_id=request.sku_id,
        forecast=result.get("forecast", []),
        method=result.get("method"),
        quality=result.get("quality"),
        extra={k: v for k, v in result.items() if k not in {"forecast", "method", "quality"}},
    )


@router.get("/inventory/{sku_id}", response_model=CurrentInventoryResponse)
async def get_current_inventory(
    sku_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Get current on-hand inventory for a SKU."""
    ledger = InventoryLedger(session, tenant_id)
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
    ledger = InventoryLedger(session, tenant_id)

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


@router.get("/rop/{sku_id}", response_model=ROPSkuResponse)
async def calculate_rop(
    sku_id: str,
    avg_daily_demand: float,
    lead_time_days: int,
    lead_time_std_dev: float,
    service_level: float = 0.95,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Calculate Reorder Point (ROP) for a SKU."""
    if avg_daily_demand < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="avg_daily_demand must be >= 0")
    if lead_time_days < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lead_time_days must be >= 0")
    if lead_time_std_dev < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lead_time_std_dev must be >= 0")
    if service_level not in (0.90, 0.95, 0.99):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="service_level must be one of 0.90, 0.95, 0.99",
        )

    calculator = ROPCalculator()
    result = calculator.calculate_rop(
        avg_daily_demand=avg_daily_demand,
        lead_time_days=lead_time_days,
        lead_time_std_dev=lead_time_std_dev,
        service_level=service_level,
    )

    return ROPSkuResponse(sku_id=sku_id, **result)


@router.post("/abc", response_model=ABCDistributionResponse)
async def calculate_abc_analysis(
    request: ABCAnalysisRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Calculate ABC classification for inventory SKUs."""
    analyzer = ABCAnalysis()
    result = analyzer.calculate_abc_distribution(
        skus_list=[s.model_dump() for s in request.skus_list],
    )
    return ABCDistributionResponse(
        distribution={
            "A": ABCBucket(count=len(result["A"]), skus=result["A"]),
            "B": ABCBucket(count=len(result["B"]), skus=result["B"]),
            "C": ABCBucket(count=len(result["C"]), skus=result["C"]),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Materials master + prospeção (Sprint O.1-O.7)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/materials", response_model=List[MaterialResponse])
async def list_materials(
    active_only: bool = True,
    category: Optional[str] = None,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    svc = MaterialService(session, tenant_id)
    rows = await svc.list_materials(active_only=active_only, category=category)
    return [_material_to_dict(r) for r in rows]


@router.get("/materials/from-bom", response_model=BomMaterialsEnvelope)
async def list_materials_from_bom(
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 500,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """Lista os materiais reais derivados da BOM, com stock ao vivo do ERP.

    `supply.material_master` está vazio nesta instalação — os materiais reais
    da NELO são os componentes-folha de `core.bom_items` (um
    `component_product_id` que nunca aparece como `parent_product_id`),
    cruzados com `core.products` para nome, unidade e custo padrão.
    Ordenado por nº de BOMs que o consomem (os mais usados primeiro).

    O stock (`on_hand`/`min_stock`) é lido ao vivo do ERP NELO
    (`dbo.PRODUTO.P_STOCK`/`P_STOCKMIN`). Quando o ERP está offline, o
    catálogo continua a responder e `erp_available=false`.
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

    # Stock ao vivo do ERP NELO — `core.products.product_code` == `dbo.PRODUTO.P_ID`.
    stock_by_pid: Dict[int, Any] = {}
    erp_available = False
    unavailable_reason: Optional[str] = None
    try:
        from src.adapters.nelo import services as nelo_services

        stock_rows = await nelo_services.list_product_stock()
        stock_by_pid = {s.product_id: s for s in stock_rows}
        erp_available = True
    except (RuntimeError, OSError, SQLAlchemyError) as exc:
        log.warning("Stock indisponível — adaptador NELO offline: %s", exc)
        unavailable_reason = (
            "O stock vem ao vivo do ERP NELO (SQL Server / dbo.PRODUTO), "
            "que não está ligado neste ambiente. O catálogo, custo e uso "
            "em BOM continuam disponíveis."
        )

    items: List[BomMaterialResponse] = []
    for r in rows:
        stock = None
        try:
            stock = stock_by_pid.get(int(r.product_code))
        except (TypeError, ValueError):
            stock = None
        on_hand = float(stock.stock) if stock else None
        min_stock = float(stock.stock_min) if stock else None
        below_min = (
            on_hand < min_stock
            if on_hand is not None and min_stock is not None
            else None
        )
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
                min_stock=min_stock,
                below_min=below_min,
            )
        )

    return BomMaterialsEnvelope(
        items=items,
        count=len(items),
        erp_available=erp_available,
        stock_source="nelo_erp_live" if erp_available else "indisponivel",
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
    svc = MaterialService(session, tenant_id)
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
    return _material_to_dict(row)


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
    svc = MaterialService(session, tenant_id)
    return await svc.get_position(sku_id=sku_id, horizon_days=horizon_days)


@router.patch("/materials/{sku_id}/min-stock", response_model=MaterialResponse)
async def patch_min_stock(
    sku_id: str,
    req: MinStockPatchRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """MR05/O.3 — override the configured min_stock_qty."""
    svc = MaterialService(session, tenant_id)
    try:
        row = await svc.update_min_stock(
            sku_id=sku_id,
            min_stock_qty=Decimal(str(req.min_stock_qty)),
        )
    except MaterialNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Material {sku_id} not found")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _material_to_dict(row)


@router.post("/materials/{sku_id}/adjust", response_model=StockAdjustResponse)
async def adjust_stock(
    sku_id: str,
    req: StockAdjustRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
):
    """MR06/ST01 — manual adjustment that NEVER lets on-hand go negative."""
    svc = MaterialService(session, tenant_id)
    try:
        result = await svc.adjust_stock(
            sku_id=sku_id,
            qty_delta=Decimal(str(req.qty_delta)),
            reason=req.reason,
            actor=req.actor,
            reference_id=req.reference_id,
        )
    except NegativeStockBlockedError as exc:
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
    svc = MaterialService(session, tenant_id)
    return await svc.get_movements(
        sku_id=sku_id,
        since=since,
        until=until,
        transaction_type=transaction_type,
        limit=limit,
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
    svc = MaterialService(session, tenant_id)
    row = await svc.create_reconciliation(
        sku_id=sku_id,
        physical_qty=Decimal(str(req.physical_qty)),
        counted_by=req.counted_by,
        comments=req.comments,
    )
    return _reconciliation_to_dict(row)


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
    svc = MaterialService(session, tenant_id)
    rows = await svc.list_reconciliations(
        since=since, unresolved_only=unresolved_only, limit=limit,
    )
    return [_reconciliation_to_dict(r) for r in rows]


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
    svc = MaterialService(session, tenant_id)
    try:
        row = await svc.resolve_reconciliation(
            reconciliation_id=reconciliation_id, resolved_by=resolved_by,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _reconciliation_to_dict(row)
