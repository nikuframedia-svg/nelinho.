"""
ProdPlan ONE - Cost Models
===========================
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import String, Numeric, Integer, Enum as SQLEnum, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class CalculationStatus(str, Enum):
    """Cost calculation status."""
    PENDING = "PENDING"
    CALCULATED = "CALCULATED"
    APPROVED = "APPROVED"
    RECONCILED = "RECONCILED"


class CostCalculation(TenantBase):
    """
    Cost Calculation entity.
    
    Stores complete COGS breakdown for an order.
    """
    
    __tablename__ = "cost_calculations"
    __table_args__ = {"schema": "profit"}
    
    # Order reference
    order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Product & Quantity
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.products.id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    
    # Version
    calculation_version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Cost components
    material_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    machine_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    setup_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    scrap_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    
    # Totals
    total_cogs: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    cogs_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    
    # Breakdown details (JSON)
    breakdown_details: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Status
    status: Mapped[CalculationStatus] = mapped_column(
        SQLEnum(CalculationStatus, name="calculation_status"),
        default=CalculationStatus.PENDING,
    )
    
    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    # Metadata
    calculated_at: Mapped[Optional[datetime]] = mapped_column()
    calculated_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    
    # Validity
    valid_from: Mapped[Optional[datetime]] = mapped_column()
    valid_until: Mapped[Optional[datetime]] = mapped_column()
    
    # Assumptions used
    assumptions: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    def __repr__(self) -> str:
        return f"<CostCalc {self.order_id}: {self.total_cogs} EUR>"


class PricingStrategy(str, Enum):
    """Pricing strategy."""
    COST_PLUS = "cost_plus"
    DYNAMIC = "dynamic"
    TARGET_MARGIN = "target_margin"
    COMPETITIVE = "competitive"


class PricingRecommendation(TenantBase):
    """
    Pricing Recommendation entity.
    
    Stores recommended selling prices for orders.
    """
    
    __tablename__ = "pricing_recommendations"
    __table_args__ = {"schema": "profit"}
    
    # Link to cost calculation
    cost_calculation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profit.cost_calculations.id"),
        nullable=False,
    )
    
    # Strategy
    strategy: Mapped[PricingStrategy] = mapped_column(
        SQLEnum(PricingStrategy, name="pricing_strategy"),
        nullable=False,
    )
    
    # Pricing
    base_markup_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    base_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    
    # Dynamic factors (JSON)
    dynamic_factors: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Adjusted price
    adjusted_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    
    # Margins
    gross_margin_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    gross_profit_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    
    # Recommendation
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Validity
    valid_from: Mapped[Optional[datetime]] = mapped_column()
    valid_until: Mapped[Optional[datetime]] = mapped_column()
    
    # Currency
    currency_code: Mapped[str] = mapped_column(String(3), default="EUR")
    
    def __repr__(self) -> str:
        return f"<Pricing {self.strategy.value}: {self.adjusted_price}>"


class ProfitScenario(TenantBase):
    """
    Profit Scenario entity.
    
    Stores what-if scenario simulations.
    """
    
    __tablename__ = "profit_scenarios"
    __table_args__ = {"schema": "profit"}
    
    # Scenario info
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Base order reference
    base_order_id: Mapped[Optional[str]] = mapped_column(String(50))
    base_cost_calculation_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profit.cost_calculations.id"),
    )
    
    # Multipliers (JSON)
    cost_multipliers: Mapped[Optional[dict]] = mapped_column(JSONB)
    volume_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.0"))
    
    # Results
    base_cogs_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    scenario_cogs_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    delta_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    
    # Impact analysis (JSON)
    impact_analysis: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Recommendation
    recommendation: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    simulated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    simulated_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    
    def __repr__(self) -> str:
        return f"<Scenario {self.scenario_name}: {self.delta_percent}%>"










