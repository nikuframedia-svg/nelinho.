"""Q.31.A — drill-down de lucro: GET /v1/profit/orders/margins + /margin-summary.

Junta `ProductionOrder` + `CostCalculation` (Q.26) + `OrderRevenue`. Ordens
sem cálculo aparecem com `calculated=false` — honesto, sem inventar margens.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.plan.models.order import OrderStatus, ProductionOrder
from src.profit.api.dashboard import list_order_margins, order_margin_summary
from src.profit.models.cost import CalculationStatus, CostCalculation
from src.profit.models.pricing import OrderRevenue

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _order(hull: int) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=hull,
        product_name=f"K1 Vanquish {hull}",
        product_type="K1",
        current_phase_name="Acabamento",
        status=OrderStatus.IN_PROGRESS,
    )


def _cost(hull: int, total_cogs: str, version: int = 1) -> CostCalculation:
    return CostCalculation(
        id=uuid4(),
        tenant_id=TENANT,
        order_id=str(hull),
        product_id=uuid4(),
        quantity=Decimal("1"),
        calculation_version=version,
        total_cogs=Decimal(total_cogs),
        cogs_per_unit=Decimal(total_cogs),
        status=CalculationStatus.CALCULATED,
    )


def _revenue(hull: int, total: str) -> OrderRevenue:
    return OrderRevenue(
        id=uuid4(),
        tenant_id=TENANT,
        order_id=str(hull),
        quantity=Decimal("1"),
        unit_price_eur=Decimal(total),
        total_revenue_eur=Decimal(total),
    )


@pytest.mark.asyncio
async def test_margins_mixes_calculated_and_uncalculated(fake_session):
    o_calc, o_raw = _order(4272), _order(4271)
    fake_session.queue_scalars([o_calc, o_raw])      # 1: ordens
    fake_session.queue_scalars([_cost(4272, "8000")])  # 2: cost calculations
    fake_session.queue_scalars([_revenue(4272, "12000")])  # 3: revenue

    out = await list_order_margins(
        date_from=None, date_to=None, limit=50,
        tenant_id=TENANT, session=fake_session,
    )

    assert out["count"] == 2
    by_hull = {r["hull"]: r for r in out["items"]}

    calc = by_hull["4272"]
    assert calc["calculated"] is True
    assert calc["revenue_eur"] == 12000.0
    assert calc["total_cogs"] == 8000.0
    assert calc["margin_eur"] == 4000.0
    assert calc["margin_pct"] == pytest.approx(0.3333, abs=1e-4)

    # Sem CostCalculation → calculated=false, margens null (nada inventado).
    raw = by_hull["4271"]
    assert raw["calculated"] is False
    assert raw["total_cogs"] is None
    assert raw["margin_eur"] is None
    assert raw["margin_pct"] is None


@pytest.mark.asyncio
async def test_margins_highest_cost_version_wins(fake_session):
    fake_session.queue_scalars([_order(4272)])
    # Versões 1 e 2 da mesma ordem — a query ordena por versão, a 2 ganha.
    fake_session.queue_scalars([
        _cost(4272, "8000", version=1),
        _cost(4272, "9000", version=2),
    ])
    fake_session.queue_scalars([_revenue(4272, "12000")])

    out = await list_order_margins(
        date_from=None, date_to=None, limit=50,
        tenant_id=TENANT, session=fake_session,
    )
    assert out["items"][0]["total_cogs"] == 9000.0
    assert out["items"][0]["margin_eur"] == 3000.0


@pytest.mark.asyncio
async def test_margins_empty_when_no_orders(fake_session):
    fake_session.queue_scalars([])  # sem ordens — sem queries de custo/receita

    out = await list_order_margins(
        date_from=None, date_to=None, limit=50,
        tenant_id=TENANT, session=fake_session,
    )
    assert out == {"count": 0, "items": []}


@pytest.mark.asyncio
async def test_margin_summary_aggregates(fake_session):
    # 3 ordens; 2 com margem calculável (+4000 e -1000), 1 sem cálculo.
    fake_session.queue_scalars([_order(4272), _order(4271), _order(4270)])
    fake_session.queue_scalars([_cost(4272, "8000"), _cost(4271, "13000")])
    fake_session.queue_scalars([
        _revenue(4272, "12000"), _revenue(4271, "12000"),
    ])

    out = await order_margin_summary(
        days=30, tenant_id=TENANT, session=fake_session,
    )

    assert out["order_count"] == 2          # só as 2 com margem
    assert out["avg_margin_eur"] == 1500.0  # (4000 + -1000) / 2
    assert out["median_margin_eur"] == 1500.0
    assert out["negative_count"] == 1       # a ordem 4271


@pytest.mark.asyncio
async def test_margin_summary_empty(fake_session):
    fake_session.queue_scalars([])  # sem ordens

    out = await order_margin_summary(
        days=30, tenant_id=TENANT, session=fake_session,
    )
    assert out["order_count"] == 0
    assert out["avg_margin_eur"] is None
    assert out["negative_count"] == 0
