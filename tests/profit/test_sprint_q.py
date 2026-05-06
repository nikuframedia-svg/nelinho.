"""
Sprint Q focused tests — margin, throughput, order cost, priority report.

All DB reads mocked via FakeSession. Integration lives in Sprint V.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.services.tenant_config_service import _reset_cache_for_tests
from src.plan.cpo.greedy_pipeline import (
    GreedyPipeline,
    _estimate_throughput_eur_day,
)
from src.plan.api.priority_report import (
    _count_inversions,
    _order_first_index,
    _rank_by_revenue,
)
from src.profit.calculators.cogs_calculator import (
    CostBreakdown,
    CostComponent,
)
from src.profit.models.pricing import (
    OrderRevenue,
    ProductPricing,
    ShippingRate,
)
from src.profit.services.margin_calculator import (
    MarginCalculator,
    OrderMargin,
    compute_throughput_eur_day,
)
from src.profit.services.order_cost_service import (
    OrderCost,
    OrderCostService,
)
from src.profit.services.throughput_service import (
    ThroughputService,
    on_target_band,
)
from tests.conftest import TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    _reset_cache_for_tests()


def _queue(session, *, scalar=None, scalars=None):
    session.queue_scalar(scalar)
    session.queue_scalars(scalars if scalars is not None else [])


def _rev_row(*, order_id: str, total: Decimal, at: date | None = None) -> OrderRevenue:
    return OrderRevenue(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        order_id=order_id,
        quantity=Decimal("1"),
        unit_price_eur=total,
        total_revenue_eur=total,
        recognised_at=at,
    )


def _ship(*, dest: str, category: str, cost: Decimal) -> ShippingRate:
    return ShippingRate(
        id=uuid4(),
        tenant_id=TEST_TENANT_ID,
        destination=dest,
        sku_category=category,
        flat_cost_eur=cost,
        active=True,
    )


# ---------------------------------------------------------------------------
# Q.1 — CostBreakdown per-piece
# ---------------------------------------------------------------------------

def _component(total: float, per_unit: float) -> CostComponent:
    return CostComponent(
        name="x", total=Decimal(str(total)), per_unit=Decimal(str(per_unit)),
    )


def test_cost_breakdown_per_piece_sums_to_total_per_unit():
    br = CostBreakdown(
        material=_component(100, 10),
        labor=_component(50, 5),
        machine=_component(20, 2),
        setup=_component(10, 1),
        overhead=_component(5, 0.5),
        scrap=_component(2, 0.2),
    )
    per_piece = br.per_piece_breakdown()
    assert abs(per_piece["total_per_unit"] - (10 + 5 + 2 + 1 + 0.5 + 0.2)) < 1e-6
    assert per_piece["material_per_unit"] == 10.0
    assert per_piece["scrap_per_unit"] == 0.2


# ---------------------------------------------------------------------------
# Q.2 — OrderCostService shipping resolution
# ---------------------------------------------------------------------------

class TestOrderCostService:
    @pytest.mark.asyncio
    async def test_cost_with_flat_shipping(self, fake_session):
        # 1. quantity lookup (OrderRevenue.quantity) — not provided, so service
        #    falls back to scanning OrderRevenue: one scalar call.
        # we pass quantity explicitly below so the call is skipped.

        # Shipping resolution tries (ANY, KAYAK) first.
        _queue(fake_session, scalar=_ship(dest="ANY", category="KAYAK", cost=Decimal("25")))

        svc = OrderCostService(fake_session, TEST_TENANT_ID)
        cost = await svc.compute(
            order_id="OF-1",
            cogs_per_unit_eur=Decimal("100"),
            quantity=Decimal("3"),
            destination=None,
            sku_category="KAYAK",
        )
        assert cost.cogs_eur == Decimal("300")
        assert cost.shipping_eur == Decimal("25")
        assert cost.total_eur == Decimal("325")

    @pytest.mark.asyncio
    async def test_cost_without_destination_or_category_skips_shipping(self, fake_session):
        svc = OrderCostService(fake_session, TEST_TENANT_ID)
        cost = await svc.compute(
            order_id="OF-2",
            cogs_per_unit_eur=Decimal("50"),
            quantity=Decimal("2"),
        )
        assert cost.shipping_eur == Decimal("0")
        assert cost.total_eur == Decimal("100")


# ---------------------------------------------------------------------------
# Q.3 — MarginCalculator
# ---------------------------------------------------------------------------

class TestMarginCalculator:
    def test_margin_math(self):
        m = OrderMargin(
            order_id="OF-1",
            revenue_eur=Decimal("1000"),
            cogs_eur=Decimal("600"),
            shipping_eur=Decimal("100"),
        )
        assert m.margin_eur == Decimal("300")
        # Sprint Q.12 — margin_pct passou a Decimal para preservar precisão
        # em agregações; comparar por igualdade em Decimal.
        assert m.margin_pct == Decimal("0.3000")

    def test_margin_pct_none_when_revenue_zero(self):
        m = OrderMargin(
            order_id="OF-0",
            revenue_eur=Decimal("0"),
            cogs_eur=Decimal("50"),
            shipping_eur=Decimal("10"),
        )
        assert m.margin_pct is None
        assert m.margin_eur == Decimal("-60")

    @pytest.mark.asyncio
    async def test_revenue_falls_back_to_product_pricing(self, fake_session):
        # 1. OrderRevenue lookup → None
        _queue(fake_session, scalar=None)
        # 2. ProductPricing lookup → 1200
        _queue(fake_session, scalar=Decimal("1200"))

        calc = MarginCalculator(fake_session, TEST_TENANT_ID)
        revenue = await calc.resolve_revenue(
            order_id="OF-X", product_id=uuid4(),
        )
        assert revenue == Decimal("1200")

    @pytest.mark.asyncio
    async def test_revenue_zero_when_nothing_set(self, fake_session):
        _queue(fake_session, scalar=None)  # OrderRevenue
        _queue(fake_session, scalar=None)  # ProductPricing
        calc = MarginCalculator(fake_session, TEST_TENANT_ID)
        revenue = await calc.resolve_revenue(
            order_id="OF-Y", product_id=uuid4(),
        )
        assert revenue == Decimal("0")


def test_compute_throughput_eur_day_divides_by_days():
    orders = [{"order_id": "o1"}, {"order_id": "o2"}]
    rev = {"o1": Decimal("10000"), "o2": Decimal("20000")}
    assert compute_throughput_eur_day(orders, revenue_by_order=rev, days=2) == Decimal("15000")


def test_compute_throughput_eur_day_zero_days():
    assert compute_throughput_eur_day([], revenue_by_order={}, days=0) == Decimal("0")


# ---------------------------------------------------------------------------
# Q.5 — ThroughputService
# ---------------------------------------------------------------------------

class TestThroughputService:
    @pytest.mark.asyncio
    async def test_dashboard_uses_targets(self, fake_session):
        # load_targets — empty cost category → defaults.
        _queue(fake_session, scalars=[])
        # throughput_today → sum query.
        _queue(fake_session, scalar=Decimal("32000"))
        # throughput_mtd.
        _queue(fake_session, scalar=Decimal("650000"))
        # throughput_ytd.
        _queue(fake_session, scalar=Decimal("4000000"))
        # throughput_trend buckets.
        _queue(fake_session, scalars=[])
        # top_skus.
        _queue(fake_session, scalars=[])

        svc = ThroughputService(fake_session, TEST_TENANT_ID)
        out = await svc.dashboard()

        assert out["throughput_eur"]["today"] == 32000.0
        assert out["throughput_eur"]["target_min"] == 30000.0
        assert out["throughput_eur"]["target_max"] == 35000.0
        assert out["throughput_eur"]["on_target"]["status"] == "within"
        assert out["trend_14d"]  # 14 days of zero-filled points
        assert len(out["trend_14d"]) == 14

    def test_on_target_band_classifies_correctly(self):
        assert on_target_band(Decimal("25000"), Decimal("30000"), Decimal("35000"))["status"] == "below"
        assert on_target_band(Decimal("32000"), Decimal("30000"), Decimal("35000"))["status"] == "within"
        assert on_target_band(Decimal("40000"), Decimal("30000"), Decimal("35000"))["status"] == "above"


# ---------------------------------------------------------------------------
# Q.6 — Priority report helpers
# ---------------------------------------------------------------------------

def test_order_first_index_picks_first_occurrence():
    ops = [
        {"order_id": "A"},
        {"order_id": "B"},
        {"order_id": "A"},  # duplicate — ignored
        {"order_id": "C"},
    ]
    assert _order_first_index(ops) == {"A": 0, "B": 1, "C": 3}


def test_rank_by_revenue_orders_descending():
    items = [
        {"order_id": "A", "first_op_index": 0, "revenue_eur": 100},
        {"order_id": "B", "first_op_index": 1, "revenue_eur": 300},
        {"order_id": "C", "first_op_index": 2, "revenue_eur": 200},
    ]
    ranks = _rank_by_revenue(items)
    # B should be rank 0 (highest revenue), C rank 1, A rank 2.
    assert ranks == [2, 0, 1]


def test_count_inversions_symmetric_case():
    # [2,0,1] has 2 inversions: (2,0), (2,1)
    assert _count_inversions([2, 0, 1]) == 2
    # Sorted → zero inversions
    assert _count_inversions([0, 1, 2, 3]) == 0


# ---------------------------------------------------------------------------
# Wire: greedy pipeline populates throughput_eur_day
# ---------------------------------------------------------------------------

def test_estimate_throughput_eur_day_divides_by_horizon_days():
    ops = [
        {"order_id": "O1", "end": "2026-04-20T12:00:00"},
        {"order_id": "O2", "end": "2026-04-20T14:00:00"},
    ]
    rev = {"O1": 5000, "O2": 5000}
    # makespan = 48h → 2 days
    assert _estimate_throughput_eur_day(ops, rev, 48.0) == 5000.0


def test_estimate_throughput_eur_day_zero_when_no_makespan():
    assert _estimate_throughput_eur_day([], {}, 0) == 0.0


def test_estimate_throughput_eur_day_deduplicates_orders():
    ops = [
        {"order_id": "O1"},
        {"order_id": "O1"},
        {"order_id": "O2"},
    ]
    # Each order counted once even if it has many ops.
    result = _estimate_throughput_eur_day(
        ops, {"O1": 10000, "O2": 5000}, 24.0,  # 1 day
    )
    assert result == 15000.0
