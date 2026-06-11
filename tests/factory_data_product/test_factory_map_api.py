"""
Thin TestClient smoke tests for the Factory Map router (Sprint N).

We do NOT re-verify the service arithmetic here (`test_factory_map_service.py`
already covers that) — these tests assert wiring, auth headers, and 404 paths.
"""

from __future__ import annotations

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
    from src.factory_data_product.services.factory_map_service import (
        _reset_snapshot_cache_for_tests,
    )
    _reset_cache_for_tests()
    _reset_snapshot_cache_for_tests()


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
# Tenant gate — require_tenant_header em todos os endpoints do router
# ---------------------------------------------------------------------------

def test_shortage_risks_requires_tenant_header():
    s = FakeSession()
    resp = _client(s).get("/v1/factory-map/shortage-risks")
    # require_tenant_header (canónico) → 401 sem tenant (auth), não 422 (validação)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Q.172 (F4.E) — endpoints órfãos removidos devolvem 404
# (/boats/{of_id}, /projection, /line-load, /kpis — zero consumo frontend)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/v1/factory-map/boats/42",
    "/v1/factory-map/projection",
    "/v1/factory-map/line-load",
    "/v1/factory-map/kpis",
])
def test_orphan_endpoints_removed(path):
    s = FakeSession()
    resp = _client(s).get(path, headers=_HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /shortage-risks — shape smoke
# ---------------------------------------------------------------------------

def test_shortage_risks_empty():
    s = FakeSession()
    _queue(s, scalars=[])
    resp = _client(s).get("/v1/factory-map/shortage-risks", headers=_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


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
