"""Q.53.C — GET /v1/profit/cost-ledger.

Consolidation layer for the future Custos page: cost-by-center, COGS
detail per boat, margin-by-product and a cost-driver ranking. Built only
from persisted `CostCalculation` + `OrderRevenue` + `ProductionOrder`;
orders without a calculation are reported `calculated=false`, never
imputed.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.plan.models.order import OrderStatus, ProductionOrder
from src.profit.models.cost import CalculationStatus, CostCalculation
from src.profit.models.pricing import OrderRevenue
from src.profit.services.cost_ledger_service import CostLedgerService

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _order(hull: int, ptype: str = "K1") -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=hull,
        product_name=f"{ptype} Vanquish {hull}",
        product_type=ptype,
        current_phase_name="Laminagem",
        status=OrderStatus.IN_PROGRESS,
    )


def _cost(hull: int, *, material, labor, overhead, version: int = 1) -> CostCalculation:
    total = Decimal(material) + Decimal(labor) + Decimal(overhead)
    return CostCalculation(
        id=uuid4(),
        tenant_id=TENANT,
        order_id=str(hull),
        product_id=uuid4(),
        quantity=Decimal("1"),
        calculation_version=version,
        material_cost=Decimal(material),
        labor_cost=Decimal(labor),
        machine_cost=Decimal("0"),
        setup_cost=Decimal("0"),
        overhead_cost=Decimal(overhead),
        scrap_cost=Decimal("0"),
        total_cogs=total,
        cogs_per_unit=total,
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
async def test_empty_ledger_when_no_orders(fake_session):
    fake_session.queue_scalars([])  # no orders → no cost/revenue queries

    out = await CostLedgerService(fake_session, TENANT).ledger()
    assert out["summary"]["orders_total"] == 0
    assert out["cost_by_center"] == []
    assert out["per_boat"] == []
    assert out["margin_by_product"] == []


@pytest.mark.asyncio
async def test_cost_by_center_sums_components(fake_session):
    fake_session.queue_scalars([_order(4001), _order(4002)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="1000"),
        _cost(4002, material="6000", labor="2000", overhead="2000"),
    ])
    fake_session.queue_scalars([])  # no revenue

    out = await CostLedgerService(fake_session, TENANT).ledger()
    centers = {c["cost_center"]: c for c in out["cost_by_center"]}
    assert centers["material"]["total_eur"] == 11000.0
    assert centers["labor"]["total_eur"] == 5000.0
    assert centers["overhead"]["total_eur"] == 3000.0
    # 11000 / (11000+5000+3000) = 0.5789
    assert centers["material"]["share_pct"] == pytest.approx(0.5789, abs=1e-4)
    assert out["summary"]["total_cogs_eur"] == 19000.0


@pytest.mark.asyncio
async def test_cost_drivers_ranked_by_spend(fake_session):
    fake_session.queue_scalars([_order(4001)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="1000"),
    ])
    fake_session.queue_scalars([])

    out = await CostLedgerService(fake_session, TENANT).ledger()
    drivers = out["cost_drivers"]
    assert drivers[0]["cost_center"] == "material"
    assert drivers[0]["rank"] == 1
    assert drivers[1]["cost_center"] == "labor"
    assert drivers[2]["cost_center"] == "overhead"
    # Zero-spend centres (machine/setup/scrap) are not ranked.
    assert all(d["total_eur"] > 0 for d in drivers)


@pytest.mark.asyncio
async def test_per_boat_mixes_calculated_and_uncalculated(fake_session):
    fake_session.queue_scalars([_order(4001), _order(4002)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="0"),
    ])
    fake_session.queue_scalars([_revenue(4001, "12000")])

    out = await CostLedgerService(fake_session, TENANT).ledger()
    by_hull = {b["hull"]: b for b in out["per_boat"]}

    calc = by_hull["4001"]
    assert calc["calculated"] is True
    assert calc["total_cogs_eur"] == 8000.0
    assert calc["cogs_breakdown"]["material"] == 5000.0
    assert calc["margin_eur"] == 4000.0
    assert calc["margin_pct"] == pytest.approx(0.3333, abs=1e-4)

    raw = by_hull["4002"]
    assert raw["calculated"] is False
    assert raw["total_cogs_eur"] is None
    assert raw["margin_eur"] is None


@pytest.mark.asyncio
async def test_margin_by_product_groups_by_type(fake_session):
    fake_session.queue_scalars([
        _order(4001, "K1"), _order(4002, "K1"), _order(4003, "K4"),
    ])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="0"),
        _cost(4002, material="4000", labor="3000", overhead="0"),
        _cost(4003, material="9000", labor="5000", overhead="0"),
    ])
    fake_session.queue_scalars([
        _revenue(4001, "12000"), _revenue(4002, "11000"),
        _revenue(4003, "20000"),
    ])

    out = await CostLedgerService(fake_session, TENANT).ledger()
    by_type = {m["product_type"]: m for m in out["margin_by_product"]}

    k1 = by_type["K1"]
    assert k1["order_count"] == 2
    assert k1["total_cogs_eur"] == 15000.0
    assert k1["total_revenue_eur"] == 23000.0
    assert k1["margin_eur"] == 8000.0

    k4 = by_type["K4"]
    assert k4["total_cogs_eur"] == 14000.0
    assert k4["margin_eur"] == 6000.0
    # Sorted by COGS desc → K1 (15000) before K4 (14000).
    assert out["margin_by_product"][0]["product_type"] == "K1"


@pytest.mark.asyncio
async def test_highest_cost_version_wins(fake_session):
    fake_session.queue_scalars([_order(4001)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="0", version=1),
        _cost(4001, material="6000", labor="3000", overhead="0", version=2),
    ])
    fake_session.queue_scalars([])

    out = await CostLedgerService(fake_session, TENANT).ledger()
    assert out["summary"]["total_cogs_eur"] == 9000.0


# ─── Q.54.H — revenue_eur backfill from the live NELO ERP ────────────────


def _erp_order(work_order_id: int, sale: float):
    """Minimal NELO `OrderRow` stand-in — only the fields the backfill reads."""
    from types import SimpleNamespace

    return SimpleNamespace(work_order_id=work_order_id, sale_price=sale)


@pytest.mark.asyncio
async def test_revenue_backfilled_from_nelo_when_table_empty(
    fake_session, monkeypatch
):
    """`order_revenue` empty → revenue_eur comes from OF_PRECOVENDA.

    The Q.54.H bug: cost-ledger returned revenue_eur:null for every boat
    while margin-by-segment already had the real ERP revenue. The ledger
    now backfills from the same NELO source so margin per boat computes.
    """
    fake_session.queue_scalars([_order(4001), _order(4002)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="0"),
        _cost(4002, material="4000", labor="3000", overhead="0"),
    ])
    fake_session.queue_scalars([])  # profit.order_revenue empty

    async def _fake_erp(limit):
        return [_erp_order(4001, 12000.0), _erp_order(4002, 11000.0)]

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _fake_erp)

    out = await CostLedgerService(fake_session, TENANT).ledger()
    by_hull = {b["hull"]: b for b in out["per_boat"]}

    assert by_hull["4001"]["revenue_eur"] == 12000.0
    assert by_hull["4001"]["margin_eur"] == 4000.0  # 12000 - 8000
    assert by_hull["4002"]["revenue_eur"] == 11000.0
    assert by_hull["4002"]["margin_eur"] == 4000.0  # 11000 - 7000
    assert out["revenue_source"]["from_nelo_erp"] == 2
    assert out["revenue_source"]["erp_available"] is True


@pytest.mark.asyncio
async def test_order_revenue_table_takes_precedence_over_nelo(
    fake_session, monkeypatch
):
    """A boat with a Postgres `OrderRevenue` row is not overwritten."""
    fake_session.queue_scalars([_order(4001), _order(4002)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="0"),
        _cost(4002, material="4000", labor="3000", overhead="0"),
    ])
    fake_session.queue_scalars([_revenue(4001, "15000")])  # 4001 has a row

    async def _fake_erp(limit):
        # ERP would say 9000 for 4001 — must be ignored (table wins).
        return [_erp_order(4001, 9000.0), _erp_order(4002, 11000.0)]

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _fake_erp)

    out = await CostLedgerService(fake_session, TENANT).ledger()
    by_hull = {b["hull"]: b for b in out["per_boat"]}

    assert by_hull["4001"]["revenue_eur"] == 15000.0  # from the table
    assert by_hull["4002"]["revenue_eur"] == 11000.0  # backfilled
    assert out["revenue_source"]["from_order_revenue"] == 1
    assert out["revenue_source"]["from_nelo_erp"] == 1


@pytest.mark.asyncio
async def test_revenue_null_when_erp_offline_and_table_empty(
    fake_session, monkeypatch
):
    """ERP offline + empty table → revenue_eur stays null, flagged honestly."""
    fake_session.queue_scalars([_order(4001)])
    fake_session.queue_scalars([
        _cost(4001, material="5000", labor="3000", overhead="0"),
    ])
    fake_session.queue_scalars([])  # empty table

    async def _boom(limit):
        raise RuntimeError("SQL Server não configurado")

    import src.adapters.nelo.services as nelo
    monkeypatch.setattr(nelo, "list_open_orders", _boom)

    out = await CostLedgerService(fake_session, TENANT).ledger()
    boat = out["per_boat"][0]
    assert boat["revenue_eur"] is None  # never invented
    assert boat["margin_eur"] is None
    assert out["revenue_source"]["erp_available"] is False
    assert "ERP NELO" in out["revenue_source"]["unavailable_reason"]
