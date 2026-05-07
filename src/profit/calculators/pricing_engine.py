"""
ProdPlan ONE - Pricing Engine
==============================

Pricing strategies:
1. Cost-Plus: COGS × (1 + Markup%)
2. Dynamic: Base × demand × inventory × competitor × seasonality
3. Target Margin: COGS / (1 - Target Margin%)
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional


class PricingStrategy(str, Enum):
    """Pricing strategy types."""
    COST_PLUS = "cost_plus"
    DYNAMIC = "dynamic"
    TARGET_MARGIN = "target_margin"


@dataclass
class DynamicFactors:
    """Dynamic pricing factors."""
    demand_pressure: Decimal = Decimal("1.0")  # >1 high demand, <1 low demand
    inventory_factor: Decimal = Decimal("1.0")  # <1 high stock, >1 low stock
    competitor_factor: Decimal = Decimal("1.0")  # <1 competitor cheaper, >1 more expensive
    seasonality_factor: Decimal = Decimal("1.0")  # >1 peak season
    
    def combined_factor(self) -> Decimal:
        """Calculate combined adjustment factor."""
        return (
            self.demand_pressure *
            self.inventory_factor *
            self.competitor_factor *
            self.seasonality_factor
        )
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "demand_pressure": float(self.demand_pressure),
            "inventory_factor": float(self.inventory_factor),
            "competitor_factor": float(self.competitor_factor),
            "seasonality_factor": float(self.seasonality_factor),
            "combined": float(self.combined_factor()),
        }


@dataclass
class PricingOption:
    """A single pricing option."""
    strategy: PricingStrategy
    price: Decimal
    gross_margin_percent: Decimal
    gross_profit_per_unit: Decimal
    is_recommended: bool = False
    factors: Optional[DynamicFactors] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "strategy": self.strategy.value,
            "price": float(self.price),
            "gross_margin_percent": float(self.gross_margin_percent),
            "gross_profit_per_unit": float(self.gross_profit_per_unit),
            "is_recommended": self.is_recommended,
        }
        if self.factors:
            result["factors"] = self.factors.to_dict()
        return result


@dataclass
class PricingResult:
    """Complete pricing recommendation."""
    order_id: str
    cogs_per_unit: Decimal
    options: List[PricingOption]
    recommended_price: Decimal
    recommended_strategy: PricingStrategy
    currency: str = "EUR"
    valid_until: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "cogs_per_unit": float(self.cogs_per_unit),
            "options": [o.to_dict() for o in self.options],
            "recommended_price": float(self.recommended_price),
            "recommended_strategy": self.recommended_strategy.value,
            "currency": self.currency,
            "valid_until": self.valid_until,
        }


class PricingEngine:
    """
    Pricing Engine.
    
    Generates pricing recommendations using multiple strategies.
    """
    
    def __init__(self, currency: str = "EUR"):
        self.currency = currency
    
    def recommend(
        self,
        order_id: str,
        cogs_per_unit: Decimal,
        base_markup_percent: Decimal = Decimal("40"),
        target_margin_percent: Decimal = Decimal("30"),
        dynamic_factors: DynamicFactors = None,
        validity_days: int = 7,
    ) -> PricingResult:
        """
        Generate pricing recommendations.
        
        Args:
            order_id: Order ID
            cogs_per_unit: Cost per unit
            base_markup_percent: Markup for cost-plus (e.g., 40 = 40%)
            target_margin_percent: Target gross margin (e.g., 30 = 30%)
            dynamic_factors: Market condition factors
            validity_days: How long the pricing is valid
        
        Returns:
            PricingResult with all options and recommendation
        """
        from datetime import datetime, timedelta
        
        cogs_per_unit = Decimal(str(cogs_per_unit))
        base_markup_percent = Decimal(str(base_markup_percent))
        target_margin_percent = Decimal(str(target_margin_percent))
        dynamic_factors = dynamic_factors or DynamicFactors()
        
        options = []
        
        # 1. Cost-Plus Pricing
        cost_plus_price = self._calculate_cost_plus(
            cogs_per_unit, base_markup_percent
        )
        cost_plus_margin = self._calculate_margin(cogs_per_unit, cost_plus_price)
        cost_plus_profit = cost_plus_price - cogs_per_unit
        
        options.append(PricingOption(
            strategy=PricingStrategy.COST_PLUS,
            price=cost_plus_price,
            gross_margin_percent=cost_plus_margin,
            gross_profit_per_unit=cost_plus_profit,
            is_recommended=False,
        ))
        
        # 2. Dynamic Pricing
        dynamic_price = self._calculate_dynamic(
            cost_plus_price, dynamic_factors, cogs_per_unit
        )
        dynamic_margin = self._calculate_margin(cogs_per_unit, dynamic_price)
        dynamic_profit = dynamic_price - cogs_per_unit
        
        options.append(PricingOption(
            strategy=PricingStrategy.DYNAMIC,
            price=dynamic_price,
            gross_margin_percent=dynamic_margin,
            gross_profit_per_unit=dynamic_profit,
            is_recommended=True,  # Default recommendation
            factors=dynamic_factors,
        ))
        
        # 3. Target Margin Pricing
        target_price = self._calculate_target_margin(
            cogs_per_unit, target_margin_percent
        )
        target_actual_margin = self._calculate_margin(cogs_per_unit, target_price)
        target_profit = target_price - cogs_per_unit
        
        options.append(PricingOption(
            strategy=PricingStrategy.TARGET_MARGIN,
            price=target_price,
            gross_margin_percent=target_actual_margin,
            gross_profit_per_unit=target_profit,
            is_recommended=False,
        ))
        
        # Find recommended option
        recommended = next((o for o in options if o.is_recommended), options[0])
        
        valid_until = (datetime.utcnow() + timedelta(days=validity_days)).isoformat()
        
        return PricingResult(
            order_id=order_id,
            cogs_per_unit=cogs_per_unit,
            options=options,
            recommended_price=recommended.price,
            recommended_strategy=recommended.strategy,
            currency=self.currency,
            valid_until=valid_until,
        )
    
    # Sprint Q.12 — preço mínimo nunca abaixo do COGS + 1%. Antes o
    # engine recomendava preços negativos / abaixo do custo silenciosamente.
    MIN_MARKUP_OVER_COGS = Decimal("1.01")

    def _enforce_min_price(self, cogs: Decimal, price: Decimal) -> Decimal:
        """Refuse to sell below cost — clamp to ``cogs * 1.01`` minimum."""
        floor = (cogs * self.MIN_MARKUP_OVER_COGS).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return max(price, floor)

    def _calculate_cost_plus(
        self,
        cogs: Decimal,
        markup_percent: Decimal,
    ) -> Decimal:
        """
        Cost-Plus pricing.

        Price = COGS × (1 + Markup%)
        """
        markup = markup_percent / 100
        price = cogs * (1 + markup)
        price = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return self._enforce_min_price(cogs, price)

    def _calculate_dynamic(
        self,
        base_price: Decimal,
        factors: DynamicFactors,
        cogs: Decimal,
    ) -> Decimal:
        """
        Dynamic pricing.

        Price = Base × Combined Factors
        """
        combined = factors.combined_factor()
        price = base_price * combined
        price = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return self._enforce_min_price(cogs, price)

    def _calculate_target_margin(
        self,
        cogs: Decimal,
        margin_percent: Decimal,
    ) -> Decimal:
        """
        Target margin pricing.

        Price = COGS / (1 - Margin%)

        Margens >95% são rejeitadas (sprint Q.12) — antes faziam cap
        silencioso a 99%, devolvendo preços absurdos sem o utilizador
        perceber.
        """
        if margin_percent < 0:
            raise ValueError(f"target_margin_percent must be >= 0, got {margin_percent}")
        if margin_percent > Decimal("95"):
            raise ValueError(
                f"target_margin_percent {margin_percent}% irrealista (máx 95%)"
            )

        margin = margin_percent / 100
        price = cogs / (1 - margin)
        price = price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return self._enforce_min_price(cogs, price)

    def _calculate_margin(
        self,
        cogs: Decimal,
        price: Decimal,
    ) -> Decimal:
        """
        Calculate gross margin percentage.

        Margin = (Price - COGS) / Price × 100
        """
        if price <= 0:
            return Decimal("0")

        margin = (price - cogs) / price * 100
        return margin.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    
    def simulate_price_impact(
        self,
        cogs_per_unit: Decimal,
        quantity: int,
        price_options: List[Decimal],
    ) -> List[Dict[str, Any]]:
        """
        Simulate impact of different prices.
        
        Returns revenue and profit projections.
        """
        results = []
        
        for price in price_options:
            price = Decimal(str(price))
            revenue = price * quantity
            cogs = cogs_per_unit * quantity
            profit = revenue - cogs
            margin = self._calculate_margin(cogs_per_unit, price)
            
            results.append({
                "price": float(price),
                "quantity": quantity,
                "revenue": float(revenue),
                "cogs": float(cogs),
                "gross_profit": float(profit),
                "margin_percent": float(margin),
            })
        
        return results










