"""
ProdPlan ONE - COGS API
========================
"""

from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.profit.services.cost_service import CostService

router = APIRouter(prefix="/cogs", tags=["COGS"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    return x_tenant_id


class COGSCalculateRequest(BaseModel):
    """COGS calculation request."""
    order_id: str
    product_id: UUID
    quantity: Decimal
    bom_costs: Dict[str, Decimal] = {}
    labor_allocations: List[Dict[str, Any]] = []
    machine_usage: List[Dict[str, Any]] = []
    setup_activities: List[Dict[str, Any]] = []
    overhead_rate: Decimal = Decimal("0")
    total_production_hours: Decimal = Decimal("0")
    scrap_rate: Decimal = Decimal("0.02")


class COGSResponse(BaseModel):
    """COGS calculation response."""
    order_id: str
    total_cogs: float
    cogs_per_unit: float
    breakdown: Dict[str, Any]
    currency: str


@router.post("/calculate", response_model=COGSResponse)
async def calculate_cogs(
    request: COGSCalculateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Calculate COGS for an order."""
    service = CostService(session, tenant_id)
    
    result = await service.calculate_cogs(
        order_id=request.order_id,
        product_id=request.product_id,
        quantity=request.quantity,
        bom_costs=request.bom_costs,
        labor_allocations=request.labor_allocations,
        machine_usage=request.machine_usage,
        setup_activities=request.setup_activities,
        overhead_rate=request.overhead_rate,
        total_production_hours=request.total_production_hours,
        scrap_rate=request.scrap_rate,
    )
    
    return COGSResponse(
        order_id=result.order_id,
        total_cogs=float(result.total_cogs),
        cogs_per_unit=float(result.cogs_per_unit),
        breakdown=result.breakdown.to_dict(),
        currency=result.currency,
    )


@router.get("/orders/{order_id}")
async def get_order_cogs(
    order_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Get COGS for an order."""
    service = CostService(session, tenant_id)
    calculation = await service.get_calculation(order_id)
    
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No COGS calculation found for order {order_id}",
        )
    
    return {
        "order_id": calculation.order_id,
        "product_id": str(calculation.product_id),
        "quantity": float(calculation.quantity),
        "total_cogs": float(calculation.total_cogs),
        "cogs_per_unit": float(calculation.cogs_per_unit),
        "breakdown": {
            "material": float(calculation.material_cost),
            "labor": float(calculation.labor_cost),
            "machine": float(calculation.machine_cost),
            "setup": float(calculation.setup_cost),
            "overhead": float(calculation.overhead_cost),
            "scrap": float(calculation.scrap_cost),
        },
        "status": calculation.status.value,
        "calculated_at": calculation.calculated_at.isoformat() if calculation.calculated_at else None,
    }


@router.get("/orders/{order_id}/margin")
async def get_order_margin(
    order_id: str,
    selling_price: float,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Calculate margin for an order given selling price."""
    service = CostService(session, tenant_id)
    calculation = await service.get_calculation(order_id)
    
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No COGS calculation found for order {order_id}",
        )
    
    gross_profit = selling_price - float(calculation.cogs_per_unit)
    margin_percent = (gross_profit / selling_price * 100) if selling_price > 0 else 0
    
    return {
        "order_id": order_id,
        "cogs_per_unit": float(calculation.cogs_per_unit),
        "selling_price": selling_price,
        "gross_profit_per_unit": gross_profit,
        "gross_margin_percent": round(margin_percent, 2),
        "total_revenue": selling_price * float(calculation.quantity),
        "total_cogs": float(calculation.total_cogs),
        "total_gross_profit": gross_profit * float(calculation.quantity),
    }










