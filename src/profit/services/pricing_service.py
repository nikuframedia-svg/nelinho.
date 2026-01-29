"""
ProdPlan ONE - Pricing Service
===============================

Business logic for pricing recommendations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.models.cost import CostCalculation, PricingRecommendation, PricingStrategy
from src.profit.calculators.pricing_engine import PricingEngine, PricingResult, DynamicFactors
from src.shared.kafka_client import publish_event, Topics
from src.shared.events import PricingRecommendedEvent


class PricingService:
    """
    Service for pricing recommendations.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._engine = PricingEngine()
    
    async def recommend_pricing(
        self,
        order_id: str,
        base_markup_percent: Decimal = Decimal("40"),
        target_margin_percent: Decimal = Decimal("30"),
        demand_pressure: Decimal = Decimal("1.0"),
        inventory_factor: Decimal = Decimal("1.0"),
        competitor_factor: Decimal = Decimal("1.0"),
        seasonality_factor: Decimal = Decimal("1.0"),
        save: bool = True,
    ) -> PricingResult:
        """
        Generate pricing recommendations for an order.
        
        Uses the latest COGS calculation as base.
        """
        # Get latest COGS
        result = await self.session.execute(
            select(CostCalculation).where(
                and_(
                    CostCalculation.order_id == order_id,
                    CostCalculation.tenant_id == self.tenant_id,
                )
            ).order_by(CostCalculation.calculation_version.desc()).limit(1)
        )
        calculation = result.scalar_one_or_none()
        
        if not calculation:
            raise ValueError(f"No COGS calculation found for order {order_id}")
        
        # Build dynamic factors
        factors = DynamicFactors(
            demand_pressure=demand_pressure,
            inventory_factor=inventory_factor,
            competitor_factor=competitor_factor,
            seasonality_factor=seasonality_factor,
        )
        
        # Generate recommendations
        pricing_result = self._engine.recommend(
            order_id=order_id,
            cogs_per_unit=calculation.cogs_per_unit,
            base_markup_percent=base_markup_percent,
            target_margin_percent=target_margin_percent,
            dynamic_factors=factors,
        )
        
        if save:
            await self._save_recommendations(pricing_result, calculation.id)
        
        # Publish event
        await publish_event(
            Topics.PRICING_RECOMMENDED,
            PricingRecommendedEvent(
                tenant_id=self.tenant_id,
                payload={
                    "order_id": order_id,
                    "strategy": pricing_result.recommended_strategy.value,
                    "recommended_price": float(pricing_result.recommended_price),
                    "gross_margin_percent": float(
                        next(o for o in pricing_result.options if o.is_recommended).gross_margin_percent
                    ),
                    "valid_until": pricing_result.valid_until,
                },
            ),
        )
        
        return pricing_result
    
    async def _save_recommendations(
        self,
        result: PricingResult,
        cost_calculation_id: UUID,
    ) -> List[PricingRecommendation]:
        """Save pricing recommendations to database."""
        saved = []
        
        for option in result.options:
            rec = PricingRecommendation(
                tenant_id=self.tenant_id,
                cost_calculation_id=cost_calculation_id,
                strategy=PricingStrategy(option.strategy.value),
                base_price=option.price,
                adjusted_price=option.price,
                gross_margin_percent=option.gross_margin_percent,
                gross_profit_per_unit=option.gross_profit_per_unit,
                is_recommended=option.is_recommended,
                dynamic_factors=option.factors.to_dict() if option.factors else None,
                valid_until=datetime.fromisoformat(result.valid_until.replace("Z", "+00:00")) if result.valid_until else None,
                currency_code=result.currency,
            )
            self.session.add(rec)
            saved.append(rec)
        
        await self.session.flush()
        return saved
    
    async def get_recommendations(
        self,
        order_id: str = None,
        strategy: PricingStrategy = None,
        limit: int = 100,
    ) -> List[PricingRecommendation]:
        """Get pricing recommendations."""
        query = select(PricingRecommendation).where(
            PricingRecommendation.tenant_id == self.tenant_id
        )
        
        if order_id:
            # Join with cost calculation to filter by order
            query = query.join(CostCalculation).where(
                CostCalculation.order_id == order_id
            )
        
        if strategy:
            query = query.where(PricingRecommendation.strategy == strategy)
        
        query = query.order_by(PricingRecommendation.created_at.desc())
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def simulate_price_impact(
        self,
        order_id: str,
        prices: List[Decimal],
        quantity: int = None,
    ) -> List[Dict[str, Any]]:
        """Simulate impact of different prices."""
        # Get latest COGS
        result = await self.session.execute(
            select(CostCalculation).where(
                and_(
                    CostCalculation.order_id == order_id,
                    CostCalculation.tenant_id == self.tenant_id,
                )
            ).order_by(CostCalculation.calculation_version.desc()).limit(1)
        )
        calculation = result.scalar_one_or_none()
        
        if not calculation:
            raise ValueError(f"No COGS calculation found for order {order_id}")
        
        quantity = quantity or int(calculation.quantity)
        
        return self._engine.simulate_price_impact(
            cogs_per_unit=calculation.cogs_per_unit,
            quantity=quantity,
            price_options=prices,
        )










