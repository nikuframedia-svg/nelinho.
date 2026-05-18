"""Unit tests for MarginSegmentService — Sprint Q.43.A (F7).

Synthetic ``OrderRow`` fixtures, no live DB. The service takes a
``fetcher`` callable so tests inject canned ERP orders.
"""

from __future__ import annotations

import pytest

from src.adapters.nelo.schemas import OrderRow
from src.profit.services.margin_segment_service import (
    AGENT_PENDING_REASON,
    MarginSegmentService,
)


def _order(
    *,
    wo_id: int = 1,
    sale_price: float = 5000.0,
    cost_price: float = 3000.0,
    customer_full_name: str | None = "Clube Náutico do Porto",
    customer_name: str | None = "CN Porto",
    customer_country: str | None = "Portugal",
) -> OrderRow:
    return OrderRow(
        work_order_id=wo_id,
        ordered_at=None,
        transport_date=None,
        delivery_date=None,
        start_date=None,
        end_date=None,
        customer_name=customer_name,
        reference=f"REF-{wo_id}",
        cost_price=cost_price,
        sale_price=sale_price,
        discount=0.0,
        paid_amount=0.0,
        coefficient_eur=0.0,
        is_paid=False,
        supervised=False,
        sequence=1,
        product_id=100,
        customer_entity_id=10,
        current_phase_id=1,
        warehouse_id=1,
        encomenda_id=None,
        encomenda_state=None,
        customer_full_name=customer_full_name,
        customer_country=customer_country,
    )


def _fetcher(orders: list[OrderRow]):
    async def _fetch(max_orders: int) -> list[OrderRow]:
        return orders

    return _fetch


# ─── customer dimension ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_by_customer_aggregates_margin_per_real_customer():
    """Two customers, each with one order — margin sums per customer."""
    orders = [
        _order(wo_id=1, sale_price=5000.0, cost_price=3000.0,
               customer_full_name="Clube A"),
        _order(wo_id=2, sale_price=8000.0, cost_price=7500.0,
               customer_full_name="Clube B"),
    ]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("customer")

    assert result.dimension == "customer"
    assert result.dimension_available is True
    assert result.order_count == 2
    by_name = {r.segment_value: r for r in result.rows}
    assert by_name["Clube A"].margin_eur == 2000.0
    assert by_name["Clube B"].margin_eur == 500.0
    # Lowest margin first — CEO sees the loss-leaders at the top.
    assert result.rows[0].segment_value == "Clube B"


@pytest.mark.asyncio
async def test_by_customer_sums_multiple_orders_for_same_customer():
    """Three orders, two share a customer — counts and euros add up."""
    orders = [
        _order(wo_id=1, sale_price=5000.0, cost_price=3000.0,
               customer_full_name="Clube A"),
        _order(wo_id=2, sale_price=6000.0, cost_price=4000.0,
               customer_full_name="Clube A"),
        _order(wo_id=3, sale_price=9000.0, cost_price=8000.0,
               customer_full_name="Clube B"),
    ]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("customer")

    by_name = {r.segment_value: r for r in result.rows}
    assert by_name["Clube A"].order_count == 2
    assert by_name["Clube A"].revenue_eur == 11000.0
    assert by_name["Clube A"].margin_eur == 4000.0
    assert by_name["Clube A"].avg_margin_eur == 2000.0
    assert by_name["Clube A"].margin_pct == round(4000.0 / 11000.0, 4)


@pytest.mark.asyncio
async def test_by_customer_falls_back_to_work_order_name_when_no_entity():
    """No ENTIDADE FK → use the free-text OF_NOME, never blank it out."""
    orders = [
        _order(wo_id=1, customer_full_name=None, customer_name="Particular X"),
    ]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("customer")

    assert result.rows[0].segment_value == "Particular X"


@pytest.mark.asyncio
async def test_by_customer_unknown_label_when_both_names_missing():
    orders = [_order(wo_id=1, customer_full_name=None, customer_name=None)]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("customer")

    assert result.rows[0].segment_value == "—"


# ─── country dimension ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_by_country_aggregates_margin_per_country():
    orders = [
        _order(wo_id=1, sale_price=5000.0, cost_price=3000.0,
               customer_country="Portugal"),
        _order(wo_id=2, sale_price=7000.0, cost_price=4000.0,
               customer_country="Espanha"),
        _order(wo_id=3, sale_price=6000.0, cost_price=5500.0,
               customer_country="Portugal"),
    ]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("country")

    by_country = {r.segment_value: r for r in result.rows}
    assert by_country["Portugal"].order_count == 2
    assert by_country["Portugal"].margin_eur == 2500.0
    assert by_country["Espanha"].margin_eur == 3000.0
    assert result.total_margin_eur == 5500.0


@pytest.mark.asyncio
async def test_by_country_unknown_label_when_country_missing():
    orders = [_order(wo_id=1, customer_country=None)]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("country")

    assert result.rows[0].segment_value == "—"


# ─── agent dimension — pending ERP sync ─────────────────────────────────


@pytest.mark.asyncio
async def test_by_agent_returns_explicit_empty_pending_erp_sync():
    """Agente comercial has no adapter reader — structured empty result,
    NOT invented data. ZERO MOCKS."""
    # The fetcher must never even be called for the agent dimension.
    async def _explode(max_orders: int):  # pragma: no cover
        raise AssertionError("fetcher must not run for agent dimension")

    svc = MarginSegmentService(fetcher=_explode)
    result = await svc.by_segment("agent")

    assert result.dimension == "agent"
    assert result.dimension_available is False
    assert result.rows == []
    assert result.order_count == 0
    assert result.total_margin_eur == 0.0
    assert result.reason == AGENT_PENDING_REASON


# ─── edge cases ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_order_list_yields_empty_result():
    svc = MarginSegmentService(fetcher=_fetcher([]))
    result = await svc.by_segment("customer")

    assert result.dimension_available is True
    assert result.rows == []
    assert result.order_count == 0
    assert result.total_margin_eur == 0.0


@pytest.mark.asyncio
async def test_negative_margin_order_is_surfaced():
    """An order sold below cost shows a negative margin — honest."""
    orders = [
        _order(wo_id=1, sale_price=3000.0, cost_price=4000.0,
               customer_full_name="Clube no Vermelho"),
    ]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("customer")

    row = result.rows[0]
    assert row.margin_eur == -1000.0
    assert row.margin_pct == round(-1000.0 / 3000.0, 4)


@pytest.mark.asyncio
async def test_zero_revenue_order_has_null_margin_pct():
    orders = [_order(wo_id=1, sale_price=0.0, cost_price=500.0)]
    svc = MarginSegmentService(fetcher=_fetcher(orders))
    result = await svc.by_segment("customer")

    row = result.rows[0]
    assert row.margin_eur == -500.0
    assert row.margin_pct is None


@pytest.mark.asyncio
async def test_unknown_dimension_rejected():
    svc = MarginSegmentService(fetcher=_fetcher([]))
    with pytest.raises(ValueError, match="Unknown dimension"):
        await svc.by_segment("region")  # type: ignore[arg-type]
