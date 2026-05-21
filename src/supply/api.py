"""Supply Chain API — aggregator router (Q.67.6.B4).

Composes per-domain sub-routers under ``/v1/supply``:
forecast, inventory, rop, materials, purchasing.

Backward-compat: collaborators (``InventoryLedger``, ``MaterialService``,
…) and Pydantic schemas are re-exported here so that
``patch.object(src.supply.api, "InventoryLedger")`` in characterization
tests still swaps the class actually used at request time. Sub-routers
do a lazy attribute lookup (``from src.supply import api as supply_api;
supply_api.X(...)``) so the patch path stays a single module.

History: 1009-line god-module decomposed in Q.67.6.B4, pinned by 34
characterization tests in ``tests/supply/test_api_characterization_q67.py``.
"""

from __future__ import annotations

from fastapi import APIRouter

from .abc_analysis import ABCAnalysis
from .forecaster import ARIMAForecaster
from .inventory_ledger import InventoryLedger
from .material_service import (
    MaterialNotFoundError,
    MaterialService,
    NegativeStockBlockedError,
)
from .purchase_order_service import PurchaseOrderService
from .rop_calculator import ROPCalculator
from .routers._common import (
    ABCAnalysisRequest,
    ABCBucket,
    ABCDistributionResponse,
    ABCSkuInput,
    BomMaterialResponse,
    BomMaterialsEnvelope,
    CurrentInventoryResponse,
    ForecastRequest,
    ForecastResponse,
    HistoricalDemandPoint,
    InventoryMovementRequest,
    InventoryMovementResponse,
    MaterialCreateRequest,
    MaterialResponse,
    MinStockPatchRequest,
    PurchaseOrderItem,
    PurchaseOrdersEnvelope,
    PurchaseOrdersSummary,
    ROPSkuResponse,
    ReconciliationCreateRequest,
    ReconciliationResponse,
    StockAdjustRequest,
    StockAdjustResponse,
    StockoutForecastResponse,
    WarehouseStockBreakdown,
)
from .routers.forecast import router as _forecast_router
from .routers.inventory import router as _inventory_router
from .routers.materials import router as _materials_router
from .routers.purchasing import router as _purchasing_router
from .routers.rop import router as _rop_router
from .services.rop_calculator import recompute_rop_configs
from .stockout_predictor import StockoutPredictor


router = APIRouter(prefix="/v1/supply", tags=["Supply Chain"])
for _sub in (
    _forecast_router,
    _inventory_router,
    _rop_router,
    _materials_router,
    _purchasing_router,
):
    router.include_router(_sub)
