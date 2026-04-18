"""
Tests for FactoryMapService (Sprint N.1-N.6) — shape + behaviour.

All sources are mocked (FakeSession + a tiny stub semantic service).
Integration against real curated data lands in Sprint V.2.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.factory_data_product.services.factory_map_service import (
    Availability,
    FactoryMapService,
    RiskFlag,
)
from tests.conftest import TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

class StubSemantic:
    """In-memory stand-in for `SemanticQueriesInMemory`. Each method returns
    a canned dict so tests can assert what the aggregator passes through."""

    def __init__(self, *, wip=None, bottlenecks=None, skills_risk=None, quality=None):
        self._wip = wip or {"open_phases_total": 42}
        self._bottlenecks = bottlenecks or {"bottlenecks": [{"phase_id": "P1"}]}
        self._skills_risk = skills_risk or {"at_risk_phases": []}
        self._quality = quality or {"total_errors": 10}

    def get_wip(self):
        return self._wip

    def get_bottlenecks(self):
        return self._bottlenecks

    def get_skills_risk(self):
        return self._skills_risk

    def get_quality(self):
        return self._quality


def _queue(session, *, scalar=None, scalars=None):
    """FakeSession.execute pops both per call — match callers in lockstep."""
    session.queue_scalar(scalar)
    session.queue_scalars(scalars if scalars is not None else [])


# ---------------------------------------------------------------------------
# Availability + RiskFlag value objects
# ---------------------------------------------------------------------------

def test_availability_as_dict_round_trip():
    a = Availability(semantic=True, orders=False)
    d = a.as_dict()
    assert d["semantic"] is True
    assert d["orders"] is False
    # Every declared flag is in the dict.
    assert set(d.keys()) == {
        "semantic", "orders", "schedule", "molds", "inventory", "pricing",
    }


def test_risk_flag_defaults():
    flag = RiskFlag(code="X", severity="MED", message="msg")
    assert flag.evidence == {}


# ---------------------------------------------------------------------------
# _orders_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orders_summary_groups_by_status(fake_session):
    _queue(fake_session, scalars=[
        ("IN_PROGRESS", 5),
        ("COMPLETED", 20),
        ("CANCELLED", 1),
    ])
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    s = await svc._orders_summary()
    assert s == {
        "total": 26,
        "in_progress": 5,
        "completed": 20,
        "cancelled": 1,
    }


@pytest.mark.asyncio
async def test_orders_summary_empty_tenant(fake_session):
    _queue(fake_session, scalars=[])
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    s = await svc._orders_summary()
    assert s["total"] == 0


# ---------------------------------------------------------------------------
# kpis (N.6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kpis_throughput_eur_day_is_unavailable_until_q0(fake_session):
    # _orders_summary query
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 7)])
    # _completed_count_today query
    _queue(fake_session, scalar=2)

    svc = FactoryMapService(
        fake_session, TEST_TENANT_ID,
        semantic_service=StubSemantic(quality={"total_errors": 5}),
    )
    k = await svc.kpis()
    assert k["wip"] == 3
    assert k["orders_total"] == 10
    assert k["completed_today"] == 2
    # defect_rate = 5 errors / 10 orders = 0.5
    assert k["defect_rate"] == 0.5
    assert k["throughput_eur_day"]["status"] == "unavailable"
    assert "Sprint Q.0" in k["throughput_eur_day"]["reason"]


@pytest.mark.asyncio
async def test_kpis_without_semantic_service_still_works(fake_session):
    _queue(fake_session, scalars=[])
    _queue(fake_session, scalar=0)

    svc = FactoryMapService(fake_session, TEST_TENANT_ID)  # no semantic injected
    k = await svc.kpis()
    # With zero orders, defect_rate is None (cannot divide)
    assert k["defect_rate"] is None


# ---------------------------------------------------------------------------
# shortage_risks (N.4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_shortage_risks_sorts_and_classifies(fake_session):
    rows = [
        # (sku_id, rop, avg_daily_demand, lead_time_days, qty_closing)
        ("SKU-A", Decimal("100"), Decimal("10"), 7, Decimal("40")),  # HIGH: < rop/2
        ("SKU-B", Decimal("100"), Decimal("10"), 7, Decimal("80")),  # MED: <= rop
        ("SKU-C", Decimal("100"), Decimal("10"), 7, Decimal("200")), # LOW
        ("SKU-D", Decimal("100"), Decimal("0"), 7, Decimal("50")),  # MED, no demand
    ]
    _queue(fake_session, scalars=rows)

    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    result = await svc.shortage_risks()
    items = result["items"]
    # Sorted: HIGH first, then MED, then LOW — on_hand as secondary
    assert items[0]["sku_id"] == "SKU-A"
    assert items[0]["severity"] == "HIGH"
    assert result["counts"]["high"] == 1
    assert result["counts"]["med"] == 2
    assert result["counts"]["low"] == 1
    # Days-to-stockout undefined when demand is zero
    d = next(i for i in items if i["sku_id"] == "SKU-D")
    assert d["days_to_stockout"] is None


@pytest.mark.asyncio
async def test_shortage_risks_empty(fake_session):
    _queue(fake_session, scalars=[])
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    result = await svc.shortage_risks()
    assert result == {
        "horizon_days": 14,
        "items": [],
        "counts": {"high": 0, "med": 0, "low": 0},
    }


# ---------------------------------------------------------------------------
# line_load (N.5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_line_load_shape(fake_session):
    op_id = uuid4()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    _queue(fake_session, scalars=[
        (op_id, today, Decimal("8.5")),
        (op_id, tomorrow, Decimal("16.0")),
    ])
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    result = await svc.line_load(horizon_days=7)
    assert result["has_data"] is True
    assert len(result["points"]) == 2
    assert result["points"][0]["load_hours"] == 8.5


# ---------------------------------------------------------------------------
# projection (N.3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_projection_uses_historical_averages(fake_session):
    # Historical per-phase averages
    _queue(fake_session, scalars=[
        ("Laminagem", 8.0, 100),
        ("Pintura", 4.0, 50),
    ])
    # Open orders
    order = SimpleNamespace(
        current_phase_name="Laminagem",
        completed_date=None,
        tenant_id=TEST_TENANT_ID,
    )
    _queue(fake_session, scalars=[order])

    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    result = await svc.projection(days_ahead=7)
    assert result["method"] == "historical_avg_durations"
    assert result["open_orders_projected"] == 1
    assert result["sample_size_per_phase"]["Laminagem"] == 100
    assert any(p["phase_id"] == "Laminagem" for p in result["points"])


# ---------------------------------------------------------------------------
# boat_view (N.2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_boat_view_returns_none_when_order_not_found(fake_session):
    _queue(fake_session, scalar=None)
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    assert await svc.boat_view(of_id="12345") is None


@pytest.mark.asyncio
async def test_boat_view_flags_late_vs_transport(fake_session):
    order = SimpleNamespace(
        legacy_id=12345,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name="Laminagem",
        status="IN_PROGRESS",
        created_date=date.today() - timedelta(days=30),
        completed_date=None,
        transport_date=date.today() - timedelta(days=2),  # OVERDUE
    )
    _queue(fake_session, scalar=order)       # ProductionOrder select
    _queue(fake_session, scalars=[])         # empty trajectory
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    result = await svc.boat_view(of_id="12345")
    assert result is not None
    codes = [f["code"] for f in result["risk_flags"]]
    assert "LATE_VS_TRANSPORT" in codes
    high_flag = next(f for f in result["risk_flags"] if f["code"] == "LATE_VS_TRANSPORT")
    assert high_flag["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_boat_view_at_risk_when_transport_close_and_open_phases(fake_session):
    order = SimpleNamespace(
        legacy_id=99,
        product_name="K4",
        product_type="K4",
        current_phase_name="Pintura",
        status="IN_PROGRESS",
        created_date=date.today() - timedelta(days=10),
        completed_date=None,
        transport_date=date.today() + timedelta(days=2),
    )
    phase = SimpleNamespace(
        fase_id="F1", fase_nome="Pintura", ordem=1,
        data_inicio=date.today(), data_fim=None,
        horas_reais=None, horas_previstas=Decimal("2.0"),
        estado="OPEN", molde_id=None,
    )
    _queue(fake_session, scalar=order)
    _queue(fake_session, scalars=[phase])
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    result = await svc.boat_view(of_id="99")
    codes = [f["code"] for f in result["risk_flags"]]
    assert "AT_RISK_VS_TRANSPORT" in codes


# ---------------------------------------------------------------------------
# snapshot (N.1) — end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_aggregates_all_sources(fake_session):
    # Snapshot makes these DB reads in order:
    #   1. _orders_summary               → scalars (status, count)
    #   2. _molds_summary                → scalars (flag, count)
    #   3. _trust_payload.load_weights   → scalars (empty — defaults)
    #   4. line_load preview             → scalars (load points)
    #   5. kpis._orders_summary          → scalars (status, count)
    #   6. kpis._completed_count_today   → scalar count
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 10)])  # _orders_summary
    _queue(fake_session, scalars=[(False, 8), (True, 2)])                   # _molds_summary
    _queue(fake_session, scalars=[])                                        # trust weights → defaults
    _queue(fake_session, scalars=[])                                        # line_load
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 10)])   # kpis._orders_summary
    _queue(fake_session, scalar=1)                                          # _completed_count_today

    svc = FactoryMapService(
        fake_session, TEST_TENANT_ID,
        semantic_service=StubSemantic(),
    )
    snap = await svc.snapshot()

    assert snap["availability"]["semantic"] is True
    assert snap["availability"]["orders"] is True
    assert snap["availability"]["molds"] is True
    assert snap["boats"]["total"] == 13
    assert snap["molds"] == {"total": 10, "active": 8, "in_maintenance": 2}
    assert snap["kpis"]["throughput_eur_day"]["status"] == "unavailable"
    assert "composite" in snap["trust"]
