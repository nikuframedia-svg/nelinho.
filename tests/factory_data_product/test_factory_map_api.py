"""
Thin TestClient smoke tests for the Factory Map router (Sprint N).

We do NOT re-verify the service arithmetic here (`test_factory_map_service.py`
already covers that) — these tests assert wiring, auth headers, and 404 paths.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.factory_data_product.api.factory_map import router as factory_map_router
from src.shared.database import get_session
from tests.conftest import TEST_TENANT_ID, FakeSession


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
    _reset_cache_for_tests()


@pytest.fixture(autouse=True)
def _no_redis_cache(monkeypatch):
    """Kill the Redis cache path so tests exercise the service every call."""
    async def fake_get_redis():
        class _NoRedis:
            async def get(self, _key):
                return None

            async def setex(self, _k, _t, _v):
                return True

        return _NoRedis()

    monkeypatch.setattr(
        "src.shared.redis_client.get_redis", fake_get_redis, raising=True,
    )


def _client(session: FakeSession) -> TestClient:
    async def _override():
        yield session

    app = FastAPI()
    app.include_router(factory_map_router)
    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _queue(s, *, scalar=None, scalars=None):
    s.queue_scalar(scalar)
    s.queue_scalars(scalars if scalars is not None else [])


_HEADERS = {"X-Tenant-Id": str(TEST_TENANT_ID)}


# ---------------------------------------------------------------------------
# GET /kpis — simplest happy path
# ---------------------------------------------------------------------------

def test_kpis_requires_tenant_header():
    s = FakeSession()
    resp = _client(s).get("/v1/factory-map/kpis")
    assert resp.status_code == 422


def test_kpis_happy_path():
    s = FakeSession()
    _queue(s, scalars=[("IN_PROGRESS", 3), ("COMPLETED", 5)])
    _queue(s, scalar=1)
    # Sprint Q ThroughputService now runs on the back of kpis(); pad queue.
    for _ in range(8):
        _queue(s, scalars=[])
    resp = _client(s).get("/v1/factory-map/kpis", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["wip"] == 3
    throughput = body["throughput_eur_day"]
    assert "today" in throughput or throughput.get("status") == "unavailable"


# ---------------------------------------------------------------------------
# GET /line-load, /shortage-risks, /projection — shape smoke
# ---------------------------------------------------------------------------

def test_line_load_empty():
    s = FakeSession()
    _queue(s, scalars=[])
    resp = _client(s).get("/v1/factory-map/line-load?horizon_days=7", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is False
    assert body["points"] == []


def test_shortage_risks_empty():
    s = FakeSession()
    _queue(s, scalars=[])
    resp = _client(s).get("/v1/factory-map/shortage-risks", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_projection_with_open_orders():
    s = FakeSession()
    # historical medians
    _queue(s, scalars=[("Laminagem", 8.0, 100)])
    # open orders
    order = SimpleNamespace(
        current_phase_name="Laminagem",
        completed_date=None,
    )
    _queue(s, scalars=[order])
    resp = _client(s).get("/v1/factory-map/projection?days_ahead=3", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "historical_avg_durations"
    assert body["days_ahead"] == 3
    assert body["open_orders_projected"] == 1


# ---------------------------------------------------------------------------
# GET /boats/{of_id}
# ---------------------------------------------------------------------------

def test_boat_not_found_returns_404():
    s = FakeSession()
    _queue(s, scalar=None)
    resp = _client(s).get("/v1/factory-map/boats/99999", headers=_HEADERS)
    assert resp.status_code == 404


def test_boat_happy_path():
    s = FakeSession()
    order = SimpleNamespace(
        legacy_id=42,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name="Laminagem",
        status="IN_PROGRESS",
        created_date=date.today() - timedelta(days=10),
        completed_date=None,
        transport_date=date.today() + timedelta(days=10),
    )
    _queue(s, scalar=order)
    _queue(s, scalars=[])
    resp = _client(s).get("/v1/factory-map/boats/42", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["of_id"] == "42"
    assert body["trajectory"] == []
    assert body["risk_flags"] == []


# ---------------------------------------------------------------------------
# GET /snapshot — full chain exercised via service
# ---------------------------------------------------------------------------

def test_snapshot_full_chain():
    s = FakeSession()
    # Snapshot internal execute sequence:
    #   _orders_summary + _molds_summary + trust weights + line_load +
    #   kpis._orders_summary + kpis._completed_count_today.
    # Trust Index consults trust config in addition; queue empties + defaults.
    _queue(s, scalars=[("IN_PROGRESS", 3)])                # _orders_summary
    _queue(s, scalars=[(False, 4)])                        # _molds_summary
    _queue(s, scalars=[])                                  # trust weights
    _queue(s, scalars=[])                                  # line_load (empty)
    _queue(s, scalars=[("IN_PROGRESS", 3)])                # kpis._orders_summary
    _queue(s, scalar=0)                                    # _completed_count_today
    resp = _client(s).get("/v1/factory-map/snapshot", headers=_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "timestamp" in body
    assert "trust" in body
    assert body["boats"]["in_progress"] == 3
    assert body["molds"]["total"] == 4
