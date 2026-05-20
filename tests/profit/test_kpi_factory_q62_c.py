"""Q.62.C.2 — KPIFactory expoe team_defect_rate + product_defect_rate.

`defect_rate()` ambiguo foi removido. Cada call-site escolhe entre os 2
KPIs claros:
  * `team_defect_rate(window_days)`    — Hipotese A (comportamento equipa)
  * `product_defect_rate(window_days)` — Hipotese B (qualidade dos barcos)

Tests verificam que KPIFactory delega correctamente para os 2 servicos
canonicos sem misturar as semanticas.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.profit.kpi_factory import KPIFactory


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _factory() -> KPIFactory:
    return KPIFactory(session=AsyncMock(), tenant_id=_TENANT)


@pytest.mark.asyncio
async def test_team_defect_rate_delegates_to_employee_extras_service():
    """`KPIFactory.team_defect_rate` -> `EmployeeExtrasService.team_defect_rate`."""
    factory = _factory()
    with patch(
        "src.workforce.employee_extras_service.EmployeeExtrasService.team_defect_rate",
        new_callable=AsyncMock,
        return_value=0.0545,
    ) as mock_team:
        rate = await factory.team_defect_rate(window_days=30)

    mock_team.assert_awaited_once_with(window_days=30)
    assert isinstance(rate, Decimal)
    assert rate == Decimal("0.0545")


@pytest.mark.asyncio
async def test_product_defect_rate_delegates_to_factory_map_service():
    """`KPIFactory.product_defect_rate` -> `FactoryMapService._defect_rate_from_db`."""
    factory = _factory()

    with patch(
        "src.factory_data_product.services.factory_map_service.FactoryMapService._orders_summary",
        new_callable=AsyncMock,
        return_value={"total": 200, "in_progress": 50},
    ), patch(
        "src.factory_data_product.services.factory_map_service.FactoryMapService._defect_rate_from_db",
        new_callable=AsyncMock,
        return_value=0.15,
    ) as mock_db:
        rate = await factory.product_defect_rate(window_days=90)

    mock_db.assert_awaited_once_with(orders_total=200, window_days=90)
    assert isinstance(rate, Decimal)
    assert rate == Decimal("0.15")


@pytest.mark.asyncio
async def test_product_defect_rate_returns_none_when_no_orders():
    """Quando `_defect_rate_from_db` devolve None (sem ordens), o factory
    propaga None em vez de Decimal('None')."""
    factory = _factory()

    with patch(
        "src.factory_data_product.services.factory_map_service.FactoryMapService._orders_summary",
        new_callable=AsyncMock,
        return_value={"total": 0},
    ), patch(
        "src.factory_data_product.services.factory_map_service.FactoryMapService._defect_rate_from_db",
        new_callable=AsyncMock,
        return_value=None,
    ):
        rate = await factory.product_defect_rate(window_days=90)

    assert rate is None


def test_ambiguous_defect_rate_method_removed():
    """`KPIFactory.defect_rate(**kwargs)` (sem prefix team/product) NAO
    deve existir mais — call-sites tem que escolher explicitamente."""
    assert not hasattr(KPIFactory, "defect_rate"), (
        "KPIFactory.defect_rate ambiguo deve ter sido removido em Q.62.C.2; "
        "call-sites devem usar team_defect_rate ou product_defect_rate."
    )


def test_kpi_factory_has_team_and_product_defect_rate():
    """Sanity check — os 2 metodos novos existem e sao async."""
    import inspect

    assert hasattr(KPIFactory, "team_defect_rate")
    assert inspect.iscoroutinefunction(KPIFactory.team_defect_rate)
    assert hasattr(KPIFactory, "product_defect_rate")
    assert inspect.iscoroutinefunction(KPIFactory.product_defect_rate)


# ─── Q.62.C.3 — OEE + OTD (3 KPIs claros, sem `otd()` ambiguo) ───────


def test_ambiguous_otd_method_removed():
    """`KPIFactory.otd(**kwargs)` (sem prefix actual/risk) NAO deve
    existir — call-sites tem que escolher entre otd_actual_pct e
    otd_risk."""
    assert not hasattr(KPIFactory, "otd"), (
        "KPIFactory.otd ambiguo deve ter sido removido em Q.62.C.3"
    )


def test_kpi_factory_has_oee_otd_actual_otd_risk():
    """Sanity — os 3 metodos novos existem e sao async."""
    import inspect

    for name in ("oee", "otd_actual_pct", "otd_risk"):
        assert hasattr(KPIFactory, name), f"KPIFactory.{name} em falta"
        method = getattr(KPIFactory, name)
        assert inspect.iscoroutinefunction(method), f"{name} nao e async"


@pytest.mark.asyncio
async def test_oee_delegates_to_oee_service():
    """`KPIFactory.oee` -> `OEEService.calculate`."""
    from datetime import date

    factory = _factory()
    fake_result = MagicMock()
    fake_result.overall = MagicMock(oee=0.85)

    with patch(
        "src.profit.services.oee_service.OEEService.calculate",
        new_callable=AsyncMock,
        return_value=fake_result,
    ) as mock_calc:
        rate = await factory.oee(date_from=date(2026, 5, 1), date_to=date(2026, 5, 20))

    mock_calc.assert_awaited_once_with(
        date_from=date(2026, 5, 1), date_to=date(2026, 5, 20),
    )
    assert rate == Decimal("0.85")


@pytest.mark.asyncio
async def test_otd_actual_pct_delegates_to_dashboard_metrics():
    """`KPIFactory.otd_actual_pct` -> `DashboardMetricsService.otd`."""
    factory = _factory()
    fake_result = MagicMock(otd_pct=92.5)

    with patch(
        "src.profit.services.dashboard_metrics_service.DashboardMetricsService.otd",
        new_callable=AsyncMock,
        return_value=fake_result,
    ) as mock_otd:
        pct = await factory.otd_actual_pct(window_days=30)

    mock_otd.assert_awaited_once_with(window_days=30)
    assert pct == Decimal("92.5")


@pytest.mark.asyncio
async def test_otd_risk_delegates_to_otd_risk_service():
    """`KPIFactory.otd_risk` -> `OTDRiskService.otd_risk`."""
    factory = _factory()
    fake_payload = {"predictions": [], "model_available": True}

    with patch(
        "src.plan.services.otd_risk_service.OTDRiskService.otd_risk",
        new_callable=AsyncMock,
        return_value=fake_payload,
    ) as mock_risk:
        result = await factory.otd_risk(top_n=10)

    mock_risk.assert_awaited_once_with(top_n=10)
    assert result == fake_payload
