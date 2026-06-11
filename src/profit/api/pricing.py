"""
ProdPlan ONE - Pricing API
===========================
"""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
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

    # F4.E — ordem sem COGS calculado é 404 (mesmo padrão de cogs.py),
    # não 500 via global_exception_handler. O serviço continua a levantar
    # ValueError (também é consumido pelo handler Kafka COGS_CALCULATED).
    try:
        result = await service.recommend_pricing(
            order_id=request.order_id,
            base_markup_percent=request.base_markup_percent,
            target_margin_percent=request.target_margin_percent,
            demand_pressure=request.demand_pressure,
            inventory_factor=request.inventory_factor,
            competitor_factor=request.competitor_factor,
            seasonality_factor=request.seasonality_factor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    return result.to_dict()


class PriceSimulationRequest(BaseModel):
    """Price simulation request.

    F4.E — `prices` exige pelo menos 1 preço (lista vazia era aceite e
    devolvia simulação vazia); `quantity` é opcional (None → quantidade
    do COGS na BD) mas, quando vem, tem de ser ≥ 1.
    """
    order_id: str
    prices: List[Decimal] = Field(..., min_length=1)
    quantity: Optional[int] = Field(None, ge=1)


@router.post("/simulate")
async def simulate_prices(
    request: PriceSimulationRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Simulate impact of different prices."""
    service = PricingService(session, tenant_id)

    try:
        result = await service.simulate_price_impact(
            order_id=request.order_id,
            prices=request.prices,
            quantity=request.quantity,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    return {"simulations": result}










