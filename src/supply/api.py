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

from src.shared.database import get_session
from .inventory_ledger import InventoryLedger
from .forecaster import ARIMAForecaster
from .rop_calculator import ROPCalculator
from .abc_analysis import ABCAnalysis

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










