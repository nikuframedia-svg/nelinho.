"""Q.30.0.1 — regressão: simulação de cenário sobre ordem com quantity=0.

Antes, `simulate_scenario` / `run_sensitivity_analysis` reconstruíam o
`COGSResult` dividindo `*_cost / calculation.quantity` sem guarda — uma
ordem persistida com `quantity=0` rebentava com `ZeroDivisionError`
(HTTP 500). Agora a reconstrução é guardada; a quantidade zero passa a
ser apanhada pela guarda explícita do simulator (Q.12) como `ValueError`.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.profit.services.cost_service import CostService

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _calculation(quantity: Decimal) -> SimpleNamespace:
    """CostCalculation persistida mínima — só os campos que o reconstrutor lê."""
    return SimpleNamespace(
        order_id="PO-9000",
        product_id=uuid4(),
        quantity=quantity,
        total_cogs=Decimal("180"),
        cogs_per_unit=Decimal("1.8"),
        material_cost=Decimal("50"),
        labor_cost=Decimal("88"),
        machine_cost=Decimal("0"),
        setup_cost=Decimal("2"),
        overhead_cost=Decimal("40"),
        scrap_cost=Decimal("0"),
        currency_code="EUR",
    )


@pytest.mark.asyncio
async def test_simulate_scenario_zero_quantity_raises_value_error_not_zerodiv(monkeypatch):
    async def _fake_get(self, order_id):
        return _calculation(Decimal("0"))

    monkeypatch.setattr(CostService, "get_calculation", _fake_get)
    svc = CostService(session=None, tenant_id=TENANT)

    with pytest.raises(ValueError, match="new_quantity must be > 0"):
        await svc.simulate_scenario(base_order_id="PO-9000")


@pytest.mark.asyncio
async def test_run_sensitivity_zero_quantity_raises_value_error_not_zerodiv(monkeypatch):
    async def _fake_get(self, order_id):
        return _calculation(Decimal("0"))

    monkeypatch.setattr(CostService, "get_calculation", _fake_get)
    svc = CostService(session=None, tenant_id=TENANT)

    with pytest.raises(ValueError):
        await svc.run_sensitivity_analysis(base_order_id="PO-9000", component="material")
