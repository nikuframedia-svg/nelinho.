# ProdPlan ONE - PROFIT Module
"""
PROFIT Module - Cost & Pricing
==============================

Responsibilities:
- COGS calculation (6 components)
- Pricing strategies
- Margin analysis
- Scenario simulation
"""

# Sprint Q.12 — interface pública mínima.
from src.profit.calculators.cogs_calculator import COGSCalculator
from src.profit.calculators.pricing_engine import PricingEngine, PricingStrategy
from src.profit.calculators.scenario_simulator import ScenarioSimulator, CostMultipliers
from src.profit.services.margin_calculator import MarginCalculator, OrderMargin

__all__ = [
    "COGSCalculator",
    "PricingEngine",
    "PricingStrategy",
    "ScenarioSimulator",
    "CostMultipliers",
    "MarginCalculator",
    "OrderMargin",
]










