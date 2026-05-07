"""Sprint Q.12 — PricingEngine regression tests.

Cobre os fixes críticos:
* Margens negativas (price < cogs) eram silenciosamente permitidas.
* `_calculate_target_margin` aceitava margens absurdas (>95%) com cap
  silencioso a 99%.
* `_calculate_dynamic` não respeitava preço mínimo após aplicar factores.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.profit.calculators.pricing_engine import (
    DynamicFactors,
    PricingEngine,
    PricingStrategy,
)


@pytest.fixture()
def engine() -> PricingEngine:
    return PricingEngine()


def test_cost_plus_basic_markup(engine: PricingEngine) -> None:
    result = engine.recommend(
        order_id="PO-001",
        cogs_per_unit=Decimal("100"),
        base_markup_percent=Decimal("40"),
    )
    cost_plus = next(o for o in result.options if o.strategy == PricingStrategy.COST_PLUS)
    assert cost_plus.price == Decimal("140.00")
    assert cost_plus.gross_margin_percent > Decimal("0")


def test_cost_plus_min_price_floor_when_markup_zero(engine: PricingEngine) -> None:
    """Markup 0% deve cair no chão de cogs * 1.01, não ficar igual ao COGS."""
    result = engine.recommend(
        order_id="PO-002",
        cogs_per_unit=Decimal("100"),
        base_markup_percent=Decimal("0"),
    )
    cost_plus = next(o for o in result.options if o.strategy == PricingStrategy.COST_PLUS)
    assert cost_plus.price >= Decimal("101.00")
    assert cost_plus.gross_profit_per_unit > Decimal("0")


def test_dynamic_below_cost_clamped_to_floor(engine: PricingEngine) -> None:
    """Factores agressivos não podem empurrar o preço abaixo do COGS."""
    factors = DynamicFactors(
        demand_pressure=Decimal("0.1"),
        inventory_factor=Decimal("0.1"),
        competitor_factor=Decimal("0.1"),
        seasonality_factor=Decimal("0.1"),
    )
    result = engine.recommend(
        order_id="PO-003",
        cogs_per_unit=Decimal("100"),
        base_markup_percent=Decimal("40"),
        dynamic_factors=factors,
    )
    dynamic = next(o for o in result.options if o.strategy == PricingStrategy.DYNAMIC)
    assert dynamic.price >= Decimal("101.00")


def test_target_margin_rejects_above_95_percent(engine: PricingEngine) -> None:
    """Margens absurdas (>95%) devem dar erro explícito."""
    with pytest.raises(ValueError, match="irrealista"):
        engine.recommend(
            order_id="PO-004",
            cogs_per_unit=Decimal("100"),
            target_margin_percent=Decimal("99"),
        )


def test_target_margin_rejects_negative(engine: PricingEngine) -> None:
    with pytest.raises(ValueError):
        engine.recommend(
            order_id="PO-005",
            cogs_per_unit=Decimal("100"),
            target_margin_percent=Decimal("-5"),
        )


def test_target_margin_30_percent_yields_correct_price(engine: PricingEngine) -> None:
    result = engine.recommend(
        order_id="PO-006",
        cogs_per_unit=Decimal("70"),
        target_margin_percent=Decimal("30"),
    )
    target = next(o for o in result.options if o.strategy == PricingStrategy.TARGET_MARGIN)
    # 70 / (1 - 0.30) = 100.00
    assert target.price == Decimal("100.00")


def test_cogs_zero_handled_gracefully(engine: PricingEngine) -> None:
    """COGS=0 não deve estoirar — cost_plus volta zero, target_margin usa floor."""
    result = engine.recommend(
        order_id="PO-007",
        cogs_per_unit=Decimal("0"),
        base_markup_percent=Decimal("40"),
        target_margin_percent=Decimal("30"),
    )
    # Não deve haver preços negativos.
    for opt in result.options:
        assert opt.price >= Decimal("0")
