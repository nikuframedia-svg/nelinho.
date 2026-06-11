"""
Tests for FactoryMapService (Sprint N.1-N.6) — shape + behaviour.

All sources are mocked (FakeSession + a tiny stub semantic service).
Integration against real curated data lands in Sprint V.2.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.factory_data_product.services.factory_map_service import (
    Availability,
    FactoryMapService,
    RiskFlag,
)
from tests.conftest import FakeSession, TEST_TENANT_ID


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch):
    async def fake(_t, _e):
        return True

    monkeypatch.setattr(
        "src.shared.kafka_client.publish_event", fake, raising=True,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    from src.core.services.tenant_config_service import _reset_cache_for_tests
    from src.factory_data_product.services.factory_map_service import (
        _reset_snapshot_cache_for_tests,
    )
    _reset_cache_for_tests()
    _reset_snapshot_cache_for_tests()


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
async def test_kpis_throughput_eur_day_reports_real_or_unavailable(fake_session):
    """`kpis()` monta o dicionário a partir dos seus blocos.

    As partes pesadas e de ordenação variável (bottlenecks, throughput)
    são patched — o teste verifica a montagem, não a sequência de queries.
    `_orders_summary` consome a 1ª query; `_completed_count_today` a 2ª.
    """
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 7)])
    _queue(fake_session, scalar=2)                              # completed_today

    svc = FactoryMapService(
        fake_session, TEST_TENANT_ID,
        semantic_service=StubSemantic(quality={"total_errors": 5}),
    )
    with patch.object(svc, "_bottlenecks_from_db", new=AsyncMock(return_value=[])), \
         patch.object(
             svc, "_throughput_eur_day",
             new=AsyncMock(return_value={"status": "unavailable"}),
         ):
        k = await svc.kpis()
    assert k["wip"] == 3
    assert k["orders_total"] == 10
    assert k["completed_today"] == 2
    # Semantic quality presente → defect_rate = total_errors / orders_total.
    assert k["defect_rate"] == 0.5
    throughput = k["throughput_eur_day"]
    assert "today" in throughput or throughput.get("status") == "unavailable"


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
# Q.172 (F4.E) — projection (N.3) e boat_view (N.2) removidos com o
# TrajectoryMixin (endpoints órfãos, zero consumo frontend). O serviço já
# não expõe estes métodos — guard explícito contra regressão silenciosa.
# ---------------------------------------------------------------------------

def test_trajectory_methods_removed(fake_session):
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    assert not hasattr(svc, "boat_view")
    assert not hasattr(svc, "projection")


# ---------------------------------------------------------------------------
# snapshot (N.1) — end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_aggregates_all_sources(fake_session):
    # Fake queue is generous — Sprint Q's throughput branch adds a handful
    # of extra execute() calls beyond the originals. We queue plenty of
    # empties so none of them consume data from elsewhere.
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 10)])  # _orders_summary
    _queue(fake_session, scalars=[(False, 8), (True, 2)])                   # _molds_summary
    _queue(fake_session, scalars=[])                                        # trust weights → defaults
    _queue(fake_session, scalars=[])                                        # line_load
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 10)])   # kpis._orders_summary
    _queue(fake_session, scalar=1)                                          # _completed_count_today
    # Throughput service — 5 more execute calls (cfg, today, mtd, ytd, trend).
    for _ in range(8):
        _queue(fake_session, scalars=[])

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
    throughput = snap["kpis"]["throughput_eur_day"]
    assert "today" in throughput or throughput.get("status") == "unavailable"
    assert "composite" in snap["trust"]
    # Q.54.E — kpis payload must not leak the private `_bottlenecks_db` key.
    assert not any(k.startswith("_") for k in snap["kpis"])


# ---------------------------------------------------------------------------
# Q.54.C — snapshot in-memory cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_second_call_served_from_cache(fake_session):
    """First snapshot computes; the second one (same tenant) is cached.

    The cached call performs zero DB work — proven by giving the second
    call a FakeSession with an empty queue and still getting the same
    payload back, flagged `cached=True`.
    """
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 10)])
    _queue(fake_session, scalars=[(False, 8), (True, 2)])
    _queue(fake_session, scalars=[])
    _queue(fake_session, scalars=[])
    _queue(fake_session, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 10)])
    _queue(fake_session, scalar=1)
    for _ in range(8):
        _queue(fake_session, scalars=[])

    svc = FactoryMapService(
        fake_session, TEST_TENANT_ID, semantic_service=StubSemantic(),
    )
    first = await svc.snapshot()
    assert first.get("cached") is not True
    assert first["boats"]["total"] == 13

    # Second call — fresh empty session, would yield total=0 if it hit
    # the DB. Cache must serve the first payload instead.
    svc2 = FactoryMapService(FakeSession(), TEST_TENANT_ID)
    second = await svc2.snapshot()
    assert second.get("cached") is True
    assert second["boats"]["total"] == 13


@pytest.mark.asyncio
async def test_snapshot_use_cache_false_bypasses_cache(fake_session):
    """`use_cache=False` always recomputes — needed for forced refresh."""
    _queue(fake_session, scalars=[("IN_PROGRESS", 1)])
    for _ in range(14):
        _queue(fake_session, scalars=[])
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    snap = await svc.snapshot(use_cache=False)
    assert snap.get("cached") is not True


# ---------------------------------------------------------------------------
# Q.54.E — defect_rate + bottlenecks computed directly from the DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_defect_rate_from_db_counts_orders_with_rework(fake_session):
    """defect_rate = ordens com ≥1 retrabalho ÷ total de ordens (0..1).

    `_defect_rate_from_db` faz 2 queries: total de `ProductionOrder` e
    nº distinto de OFs com retrabalho na janela. 3/20 = 0,15.
    """
    _queue(fake_session, scalar=20)       # total ProductionOrder
    _queue(fake_session, scalar=3)        # distinct OFs com retrabalho

    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    rate = await svc._defect_rate_from_db(orders_total=0)
    assert rate == 0.15


@pytest.mark.asyncio
async def test_defect_rate_from_db_none_when_no_orders(fake_session):
    """Sem ordens não há taxa de defeito honesta — devolve None."""
    _queue(fake_session, scalar=0)        # total ProductionOrder = 0
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    assert await svc._defect_rate_from_db(orders_total=0) is None


@pytest.mark.asyncio
async def test_defect_rate_from_db_clamped_to_one(fake_session):
    """A taxa nunca passa de 1.0 mesmo que o numerador a ultrapasse."""
    _queue(fake_session, scalar=10)       # total ProductionOrder
    _queue(fake_session, scalar=14)       # OFs com retrabalho > total
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    assert await svc._defect_rate_from_db(orders_total=0) == 1.0


@pytest.mark.asyncio
async def test_bottlenecks_from_db_scores_phases(fake_session):
    """Bottleneck score = backlog hours / capacity hours, sorted desc."""
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    # backlog rows: (fase_id, fase_nome, n_open, horas_finais, horas_prev)
    fake_session.queue_scalars([
        ("F1", "Laminagem", 10, Decimal("400"), Decimal("0")),
        ("F2", "Pintura", 4, Decimal("40"), Decimal("0")),
    ])
    # capacity rows: (fase_id, capacidade_horas)
    fake_session.queue_scalars([
        ("F1", Decimal("40")),
        ("F2", Decimal("80")),
    ])
    result = await svc._bottlenecks_from_db()
    assert len(result) == 2
    # F1: 400/40 = 10.0 > F2: 40/80 = 0.5
    assert result[0]["fase_id"] == "F1"
    assert result[0]["score"] == 10.0
    assert result[0]["is_critical"] is True
    assert result[1]["fase_id"] == "F2"
    assert result[1]["is_critical"] is False


@pytest.mark.asyncio
async def test_bottlenecks_from_db_empty_when_no_phase_data(fake_session):
    svc = FactoryMapService(fake_session, TEST_TENANT_ID)
    fake_session.queue_scalars([])  # no backlog rows
    result = await svc._bottlenecks_from_db()
    assert result == []
