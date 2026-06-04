"""
ProdPlan ONE - Pricing API
===========================
"""

from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.profit.services.pricing_service import PricingService
from src.shared.auth.headers import require_tenant_header

router = APIRouter(prefix="/pricing", tags=["Pricing"])


get_tenant_id = require_tenant_header


class PricingRequest(BaseModel):
    """Pricing recommendation request."""
    order_id: str
    base_markup_percent: Decimal = Decimal("40")
    target_margin_percent: Decimal = Decimal("30")
    demand_pressure: Decimal = Decimal("1.0")
    inventory_factor: Decimal = Decimal("1.0")
    competitor_factor: Decimal = Decimal("1.0")
    seasonality_factor: Decimal = Decimal("1.0")


@router.post("/recommend")
async def recommend_pricing(
    request: PricingRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate pricing recommendations."""
    service = PricingService(session, tenant_id)
    
    result = await service.recommend_pricing(
        order_id=request.order_id,
        base_markup_percent=request.base_markup_percent,
        target_margin_percent=request.target_margin_percent,
        demand_pressure=request.demand_pressure,
        inventory_factor=request.inventory_factor,
        competitor_factor=request.competitor_factor,
        seasonality_factor=request.seasonality_factor,
    )
    
    return result.to_dict()


class PriceSimulationRequest(BaseModel):
    """Price simulation request."""
    order_id: str
    prices: List[Decimal]
    quantity: int = None


@router.post("/simulate")
async def simulate_prices(
    request: PriceSimulationRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Simulate impact of different prices."""
    service = PricingService(session, tenant_id)
    
    result = await service.simulate_price_impact(
        order_id=request.order_id,
        prices=request.prices,
        quantity=request.quantity,
    )
    
    return {"simulations": result}










