"""
Shared dependencies + schemas for supply sub-routers (Q.67.6.B4).
=================================================================

Hosts the Pydantic schemas and helper functions used by more than one
sub-router under ``src/supply/routers/``. Single sub-routers keep their
own request/response models inline to avoid spreading a tiny pile of
classes across many files.

Backward compatibility
----------------------
Every schema declared here is re-exported from ``src.supply.api`` so
that external imports such as ``from src.supply.api import
ForecastRequest`` keep working. Characterization tests in
``tests/supply/test_api_characterization_q67.py`` use
``patch.object(supply_api, "InventoryLedger")`` to swap collaborators —
that contract is honoured by keeping those symbols as attributes of
``src.supply.api`` and by having sub-routers do a lazy attribute lookup
(``supply_api.InventoryLedger(...)``) at call time.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# Forecast schemas
# ═══════════════════════════════════════════════════════════════════════════


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


class StockoutForecastResponse(BaseModel):
    """Data prevista de rutura a partir do consumo histórico real."""

    sku_id: str
    predicted_stockout_date: Optional[str] = None
    confidence: str = Field(description="high / medium / low / none")
    avg_daily_consumption: float
    history_days: int
    total_consumed: float
    window_days: int
    days_to_stockout: Optional[float] = None
    on_hand: float
    reason: Optional[str] = None
    method: str


# ═══════════════════════════════════════════════════════════════════════════
# Inventory schemas
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# ROP / ABC schemas
# ═══════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════
# Material schemas
# ═══════════════════════════════════════════════════════════════════════════


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


class WarehouseStockBreakdown(BaseModel):
    """Stock de um material num armazém — uma linha de `supply.warehouse_stock`."""

    warehouse_id: int
    warehouse_name: str
    stock: float


class BomMaterialResponse(BaseModel):
    """Material derivado da BOM — componente-folha de `core.bom_items`.

    Os materiais reais da NELO não vivem em `supply.material_master` (vazio),
    mas como produtos componente de uma BOM que nunca são, eles próprios,
    produto-pai. Este endpoint expõe esses componentes-folha.

    O stock vem de `supply.warehouse_stock` — espelho do ERP NELO (view
    `produto_stocks_por_armazem`), sincronizado pelo ETL `stock`. `on_hand`
    é o total entre armazéns; `warehouses` é a repartição por armazém.
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
        default=None, description="Stock total entre armazéns — null se não sincronizado"
    )
    warehouses: List[WarehouseStockBreakdown] = Field(
        default_factory=list, description="Repartição do stock por armazém"
    )
    predicted_stockout_date: Optional[str] = Field(
        default=None,
        description=(
            "Data prevista de rutura (ISO) a partir do consumo histórico real "
            "do ledger. Null se não há histórico suficiente ou sem stock."
        ),
    )
    stockout_confidence: Optional[str] = Field(
        default=None,
        description="Confiança da previsão: high/medium/low/none",
    )
    avg_daily_consumption: Optional[float] = Field(
        default=None,
        description="Consumo médio diário (unidades) usado na previsão",
    )


class BomMaterialsEnvelope(BaseModel):
    """Catálogo de materiais derivado da BOM + estado do stock por armazém."""

    items: List[BomMaterialResponse]
    count: int
    stock_available: bool = Field(
        description="True se há stock sincronizado em supply.warehouse_stock"
    )
    stock_synced_at: Optional[str] = Field(
        default=None, description="ISO timestamp da última sincronização do stock"
    )
    stock_source: str = Field(
        description="'erp_nelo_warehouse_stock' ou 'indisponivel'"
    )
    unavailable_reason: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Purchasing / reconciliation schemas
# ═══════════════════════════════════════════════════════════════════════════


class PurchaseOrderItem(BaseModel):
    """Uma encomenda a fornecedor — uma linha de `supply.purchase_orders`."""

    id: str
    po_number: Optional[str] = None
    erp_movement_id: Optional[int] = None
    supplier_name: str
    supplier_erp_id: Optional[int] = None
    product_code: str
    product_name: Optional[str] = None
    qty_ordered: float
    qty_received: float
    qty_outstanding: float
    unit_of_measure: str
    ordered_at: Optional[str] = None
    eta: Optional[str] = None
    received_at: Optional[str] = None
    status: str
    is_overdue: bool
    days_to_eta: Optional[int] = None
    source: str
    notes: Optional[str] = None


class PurchaseOrdersSummary(BaseModel):
    open: int
    overdue: int
    received: int
    cancelled: int
    total_outstanding_qty: float


class PurchaseOrdersEnvelope(BaseModel):
    """Tracking de encomendas a fornecedor — backing da tab Entregas.

    Degrada com honestidade: se o mirror `supply.purchase_orders` nunca
    foi sincronizado, `data_available=false` e `unavailable_reason`
    explica como sincronizar.
    """

    items: List[PurchaseOrderItem]
    count: int
    data_available: bool
    source: str = Field(
        description="'supply_purchase_orders' ou 'indisponivel'"
    )
    last_synced_at: Optional[str] = None
    unavailable_reason: Optional[str] = None
    summary: PurchaseOrdersSummary


class ReconciliationCreateRequest(BaseModel):
    physical_qty: float = Field(ge=0)
    counted_by: Optional[str] = None
    comments: Optional[str] = None


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


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def material_to_dict(m: Any) -> Dict[str, Any]:
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


def reconciliation_to_dict(r: Any) -> Dict[str, Any]:
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


__all__ = [
    # Forecast
    "HistoricalDemandPoint",
    "ForecastRequest",
    "ForecastResponse",
    "StockoutForecastResponse",
    # Inventory
    "InventoryMovementRequest",
    "InventoryMovementResponse",
    "CurrentInventoryResponse",
    # ROP / ABC
    "ROPSkuResponse",
    "ABCSkuInput",
    "ABCAnalysisRequest",
    "ABCBucket",
    "ABCDistributionResponse",
    # Materials
    "MaterialCreateRequest",
    "MinStockPatchRequest",
    "StockAdjustRequest",
    "StockAdjustResponse",
    "MaterialResponse",
    "WarehouseStockBreakdown",
    "BomMaterialResponse",
    "BomMaterialsEnvelope",
    # Purchasing / reconciliation
    "PurchaseOrderItem",
    "PurchaseOrdersSummary",
    "PurchaseOrdersEnvelope",
    "ReconciliationCreateRequest",
    "ReconciliationResponse",
    # Helpers
    "material_to_dict",
    "reconciliation_to_dict",
]
