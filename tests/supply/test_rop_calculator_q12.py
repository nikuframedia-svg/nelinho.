"""Sprint Q.12 — ROPCalculator regression tests.

Antes não havia cobertura. O endpoint da API agora rejeita
`lead_time_days < 0` e `service_level` fora de {0.90, 0.95, 0.99}.
"""

from __future__ import annotations

import math

from src.supply.rop_calculator import ROPCalculator


def test_basic_rop_with_zero_variance() -> None:
    """Sem variância, safety_stock = 0 e ROP = avg × lead_time."""
    calc = ROPCalculator()
    result = calc.calculate_rop(
        avg_daily_demand=10.0,
        lead_time_days=7,
        lead_time_std_dev=0.0,
        service_level=0.95,
    )
    assert result["base_rop"] == 70.0
    assert result["safety_stock"] == 0.0
    assert result["rop"] == 70.0
    assert result["z_score"] == 1.645


def test_safety_stock_positive_with_variance() -> None:
    calc = ROPCalculator()
    result = calc.calculate_rop(
        avg_daily_demand=10.0,
        lead_time_days=9,
        lead_time_std_dev=2.0,
        service_level=0.95,
    )
    # safety = 1.645 * 2 * sqrt(9) = 1.645 * 6 = 9.87
    assert math.isclose(result["safety_stock"], 9.87, abs_tol=0.05)
    assert result["rop"] > result["base_rop"]


def test_z_score_99_higher_than_90() -> None:
    calc = ROPCalculator()
    r90 = calc.calculate_rop(10.0, 7, 1.0, 0.90)
    r99 = calc.calculate_rop(10.0, 7, 1.0, 0.99)
    assert r99["safety_stock"] > r90["safety_stock"]
    assert r99["z_score"] > r90["z_score"]


def test_zero_demand_zero_lead_time_returns_zero_rop() -> None:
    calc = ROPCalculator()
    result = calc.calculate_rop(0.0, 0, 0.0, 0.95)
    assert result["rop"] == 0.0
    assert result["base_rop"] == 0.0
    assert result["safety_stock"] == 0.0
