"""
ProdPlan ONE - Supply Chain API
=================================

REST endpoints for Supply Chain Planning:
- Inventory ledger
- Demand forecasting (Prophet)
- ROP calculation
- ABC analysis
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime
from decimal import Decimal

from src.shared.database import get_session
from .inventory_ledger import InventoryLedger
from .forecaster import ARIMAForecaster
from .rop_calculator import ROPCalculator
from .abc_analysis import ABCAnalysis
from .material_service import (
    MaterialNotFoundError,
    MaterialService,
    NegativeStockBlockedError,
)

router = APIRouter(prefix="/v1/supply", tags=["Supply Chain"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


# ═══════════════════════════════════════════════════════════════════════════════
# Request/Response Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ForecastRequest(BaseModel):
    """Request for demand forecast."""
    sku_id: str
    historical_data: List[dict]  # [{date, quantity}]
    periods_ahead: int = 30


class InventoryMovementRequest(BaseModel):
    """Request for inventory movement."""
    sku_id: str
    qty_change: float
    transaction_type: str  # "consume", "receive", "adjust"
    reference_id: Optional[UUID] = None


class ROPCalculateRequest(BaseModel):
    """Request for ROP calculation."""
    avg_daily_demand: float
    lead_time_days: int
    lead_time_std_dev: float
    service_level: float = 0.95


class ABCAnalysisRequest(BaseModel):
    """Request for ABC analysis."""
    skus_list: List[dict]  # [{sku_id, value}]


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/forecast", status_code=status.HTTP_200_OK)
async def forecast_demand(
    request: ForecastRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Generate demand forecast for a SKU using Prophet.
    
    Args:
        request: ForecastRequest with SKU ID, historical data, and periods ahead
    
    Returns:
        Forecast result with P50, P90, WMAPE, and quality
    """
    forecaster = ARIMAForecaster()
    
    result = await forecaster.forecast(
        sku_id=request.sku_id,
        historical_data=request.historical_data,
        periods_ahead=request.periods_ahead,
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    
    return result


@router.get("/inventory/{sku_id}", status_code=status.HTTP_200_OK)
async def get_current_inventory(
    sku_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Get current on-hand inventory for a SKU.
    
    Args:
        sku_id: SKU identifier
    
    Returns:
        Current on-hand quantity
    """
    ledger = InventoryLedger(session, tenant_id)
    on_hand = await ledger.get_current_on_hand(sku_id)
    
    return {
        "sku_id": sku_id,
        "on_hand": float(on_hand),
    }


@router.post("/inventory/movement", status_code=status.HTTP_201_CREATED)
async def record_inventory_movement(
    request: InventoryMovementRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Record inventory movement (receipt, consumption, adjustment).
    
    Args:
        request: InventoryMovementRequest with movement details
    
    Returns:
        Movement record with updated on-hand quantity
    """
    if request.transaction_type not in ("consume", "receive", "adjust"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transaction_type: {request.transaction_type}. Must be 'consume', 'receive', or 'adjust'",
        )
    
    ledger = InventoryLedger(session, tenant_id)
    
    result = await ledger.record_movement(
        sku_id=request.sku_id,
        qty_change=request.qty_change,
        transaction_type=request.transaction_type,
        reference_id=request.reference_id,
    )
    
    await session.commit()
    
    return {
        "sku_id": result["sku_id"],
        "on_hand_after": float(result["on_hand_after"]),
        "qty_opening": float(result["qty_opening"]),
        "qty_closing": float(result["qty_closing"]),
        "reference_id": str(result["reference_id"]) if result["reference_id"] else None,
    }


@router.get("/rop/{sku_id}", status_code=status.HTTP_200_OK)
async def calculate_rop(
    sku_id: str,
    avg_daily_demand: float,
    lead_time_days: int,
    lead_time_std_dev: float,
    service_level: float = 0.95,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Calculate Reorder Point (ROP) for a SKU.
    
    Args:
        sku_id: SKU identifier
        avg_daily_demand: Average daily demand (units)
        lead_time_days: Lead time in days
        lead_time_std_dev: Standard deviation of lead time
        service_level: Service level (0.90, 0.95, or 0.99)
    
    Returns:
        ROP calculation result with safety stock
    """
    calculator = ROPCalculator()
    
    result = calculator.calculate_rop(
        avg_daily_demand=avg_daily_demand,
        lead_time_days=lead_time_days,
        lead_time_std_dev=lead_time_std_dev,
        service_level=service_level,
    )
    
    return {
        "sku_id": sku_id,
        **result,
    }


@router.post("/abc", status_code=status.HTTP_200_OK)
async def calculate_abc_analysis(
    request: ABCAnalysisRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Calculate ABC classification for inventory SKUs.
    
    Args:
        request: ABCAnalysisRequest with list of SKUs (sku_id, value)
    
    Returns:
        ABC distribution (A, B, C classes)
    """
    analyzer = ABCAnalysis()
    
    result = analyzer.calculate_abc_distribution(
        skus_list=request.skus_list,
    )
    
    return {
        "distribution": {
            "A": {
                "count": len(result["A"]),
                "skus": result["A"],
            },
            "B": {
                "count": len(result["B"]),
                "skus": result["B"],
            },
            "C": {
                "count": len(result["C"]),
                "skus": result["C"],
            },
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint O.1-O.7 — Material master + prospeção + adjust + reconciliation
# ═══════════════════════════════════════════════════════════════════════════════

class MaterialCreateRequest(BaseModel):
    sku_id: str
    name: str
    min_stock_qty: float = 0.0
    reorder_qty: float = 0.0
    lead_time_days: int = 7
    unit_of_measure: str = "UN"
    category: Optional[str] = None
    critical_flag: bool = False
    default_supplier_id: Optional[UUID] = None


class MinStockPatchRequest(BaseModel):
    min_stock_qty: float


class StockAdjustRequest(BaseModel):
    qty_delta: float
    reason: str
    actor: Optional[str] = None
    reference_id: Optional[UUID] = None


class ReconciliationCreateRequest(BaseModel):
    physical_qty: float
    counted_by: Optional[str] = None
    comments: Optional[str] = None


def _material_to_dict(m) -> dict:
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


def _reconciliation_to_dict(r) -> dict:
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


@router.get("/materials", status_code=status.HTTP_200_OK)
async def list_materials(
    active_only: bool = True,
    category: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MaterialService(session, tenant_id)
    rows = await svc.list_materials(active_only=active_only, category=category)
    return [_material_to_dict(r) for r in rows]


@router.post("/materials", status_code=status.HTTP_201_CREATED)
async def create_material(
    req: MaterialCreateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
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
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Prospeção material (MR02) — on-hand + in-transit vs min_stock."""
    svc = MaterialService(session, tenant_id)
    return await svc.get_position(sku_id=sku_id, horizon_days=horizon_days)


@router.patch("/materials/{sku_id}/min-stock")
async def patch_min_stock(
    sku_id: str,
    req: MinStockPatchRequest,
    tenant_id: UUID = Depends(get_tenant_id),
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


@router.post("/materials/{sku_id}/adjust")
async def adjust_stock(
    sku_id: str,
    req: StockAdjustRequest,
    tenant_id: UUID = Depends(get_tenant_id),
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
    return {
        "sku_id": result["sku_id"],
        "on_hand_after": float(result["on_hand_after"]),
        "qty_opening": float(result["qty_opening"]),
        "qty_closing": float(result["qty_closing"]),
        "qty_delta": result["qty_delta"],
        "reason": result["reason"],
    }


@router.get("/materials/{sku_id}/movements")
async def get_movements(
    sku_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    transaction_type: Optional[str] = None,
    limit: int = 100,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """ST02/MR07 — inventory movement history."""
    svc = MaterialService(session, tenant_id)
    return await svc.get_movements(
        sku_id=sku_id,
        since=since,
        until=until,
        transaction_type=transaction_type,
        limit=limit,
    )


@router.post("/reconciliation", status_code=status.HTTP_201_CREATED)
async def create_reconciliation(
    sku_id: str,
    req: ReconciliationCreateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
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


@router.get("/reconciliation")
async def list_reconciliations(
    since: Optional[datetime] = None,
    unresolved_only: bool = False,
    limit: int = 100,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MaterialService(session, tenant_id)
    rows = await svc.list_reconciliations(
        since=since, unresolved_only=unresolved_only, limit=limit,
    )
    return [_reconciliation_to_dict(r) for r in rows]


@router.post("/reconciliation/{reconciliation_id}/resolve")
async def resolve_reconciliation(
    reconciliation_id: UUID,
    resolved_by: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
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










