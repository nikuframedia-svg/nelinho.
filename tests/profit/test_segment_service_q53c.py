"""Q.53.C — GET /v1/profit/margin-by-segment.

Margin broken down by a business dimension (country / agent). Data comes
from the live NELO adapter; the service degrades honestly with
`erp_available=false` when the adapter is offline, and flags a dimension
that exists but is unpopulated.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.profit.services.segment_service import MarginSegmentService


def _order(*, country=None, reference=None, sale=0.0, cost=0.0):
    return SimpleNamespace(
        customer_country=country,
        reference=reference,
        sale_price=sale,
        cost_price=cost,
    )


@pytest.mark.asyncio
async def test_invalid_dimension_raises():
    svc = MarginSegmentService()
    with pytest.raises(ValueError, match="dimension inválida"):
        await svc.margin_by_segment("planet")


@pytest.mark.asyncio
async def test_country_segmentation_aggregates(monkeypatch):
    orders = [
        _order(country="Portugal", sale=12000, cost=8000),
        _order(country="Portugal", sale=10000, cost=7000),
        _order(country="Espanha", sale=20000, cost=12000),
    ]

    async def _fake(limit):
        return orders

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _fake)

    out = await MarginSegmentService().margin_by_segment("country")

    assert out["erp_available"] is True
    by_seg = {s["segment"]: s for s in out["segments"]}
    pt = by_seg["Portugal"]
    assert pt["order_count"] == 2
    assert pt["revenue_eur"] == 22000.0
    assert pt["cogs_eur"] == 15000.0
    assert pt["margin_eur"] == 7000.0
    # Segments are sorted by margin desc — Espanha (8000) before PT (7000).
    assert out["segments"][0]["segment"] == "Espanha"
    assert out["total"]["margin_eur"] == 15000.0


@pytest.mark.asyncio
async def test_country_casing_collapses_into_one_segment(monkeypatch):
    """The ERP free-texts the country — "SPAIN"/"Spain"/"spain" are one."""
    orders = [
        _order(country="SPAIN", sale=10000, cost=4000),
        _order(country="Spain", sale=6000, cost=2000),
        _order(country="spain", sale=4000, cost=1000),
    ]

    async def _fake(limit):
        return orders

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _fake)

    out = await MarginSegmentService().margin_by_segment("country")

    assert len(out["segments"]) == 1
    spain = out["segments"][0]
    assert spain["segment"] == "Spain"
    assert spain["order_count"] == 3
    assert spain["revenue_eur"] == 20000.0


@pytest.mark.asyncio
async def test_agent_segmentation_uses_reference(monkeypatch):
    orders = [
        _order(reference="AG-NORTE", sale=5000, cost=3000),
        _order(reference="AG-NORTE", sale=5000, cost=4000),
    ]

    async def _fake(limit):
        return orders

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _fake)

    out = await MarginSegmentService().margin_by_segment("agent")
    assert out["segments"][0]["segment"] == "AG-NORTE"
    assert out["segments"][0]["margin_eur"] == 3000.0


@pytest.mark.asyncio
async def test_unpopulated_dimension_degrades_honestly(monkeypatch):
    """ERP responds, but no order has the dimension filled — no fake data."""
    orders = [_order(country=None, sale=9000, cost=5000)]

    async def _fake(limit):
        return orders

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _fake)

    out = await MarginSegmentService().margin_by_segment("country")
    assert out["erp_available"] is True
    assert out["segments"] == []
    assert out["skipped_no_dimension"] == 1
    assert "nenhuma ordem" in out["unavailable_reason"]


@pytest.mark.asyncio
async def test_erp_offline_degrades_with_flag(monkeypatch):
    async def _boom(limit):
        raise RuntimeError("SQL Server não configurado")

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _boom)

    out = await MarginSegmentService().margin_by_segment("country")
    assert out["erp_available"] is False
    assert out["segments"] == []
    assert "ERP NELO" in out["unavailable_reason"]
    assert out["total"]["margin_eur"] == 0.0
