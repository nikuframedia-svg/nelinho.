"""Sprint Q.12 — ScenarioSimulator zero-volume regression test.

Antes, `volume_multiplier=0` resultava em divisão por zero (`new_quantity=0`)
com 500 IS para o chamador. Agora levanta `ValueError` claro.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.profit.calculators.scenario_simulator import CostMultipliers, ScenarioSimulator


def _fake_breakdown():
    """Mínimo para alimentar o simulator — campos `total` por componente."""
    return SimpleNamespace(
        material=SimpleNamespace(total=Decimal("100"), per_unit=Decimal("1")),
        labor=SimpleNamespace(total=Decimal("50"), per_unit=Decimal("0.5")),
        machine=SimpleNamespace(total=Decimal("30"), per_unit=Decimal("0.3")),
        setup=SimpleNamespace(total=Decimal("20"), per_unit=Decimal("0.2")),
        overhead=SimpleNamespace(total=Decimal("40"), per_unit=Decimal("0.4")),
        scrap=SimpleNamespace(total=Decimal("10"), per_unit=Decimal("0.1")),
    )


def _fake_base_result():
    return SimpleNamespace(
        order_id="PO-100",
        product_id="K1-X",
        quantity=Decimal("100"),
        cogs_per_unit=Decimal("2.5"),
        currency="EUR",
        breakdown=_fake_breakdown(),
    )


def test_volume_zero_raises_value_error() -> None:
    sim = ScenarioSimulator()
    with pytest.raises(ValueError, match="new_quantity must be > 0"):
        sim.simulate(
            base_result=_fake_base_result(),
            scenario_name="prod-zero",
            multipliers=CostMultipliers(),
            volume_multiplier=Decimal("0"),
        )


def test_volume_negative_raises_value_error() -> None:
    sim = ScenarioSimulator()
    with pytest.raises(ValueError):
        sim.simulate(
            base_result=_fake_base_result(),
            scenario_name="prod-neg",
            multipliers=CostMultipliers(),
            volume_multiplier=Decimal("-1"),
        )
