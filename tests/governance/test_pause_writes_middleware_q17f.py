"""Q.17.F.9 — tests for PauseWritesMiddleware.

A minimal FastAPI app with the middleware + a read and a write route is
enough; no DB or auth needed.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.governance.yaml_policy import pause_registry
from src.governance.yaml_policy.pause_writes_middleware import register


@pytest.fixture(autouse=True)
def _reset_registry():
    pause_registry.reset_for_tests()
    yield
    pause_registry.reset_for_tests()


def _make_app() -> FastAPI:
    app = FastAPI()
    register(app)

    @app.get("/v1/plan/cpo/schedule")
    async def _read():
        return {"ok": True}

    @app.post("/v1/plan/cpo/schedule")
    async def _write():
        return {"created": True}

    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_write_passes_when_no_pause():
    app = _make_app()
    async with _client(app) as c:
        resp = await c.post(
            "/v1/plan/cpo/schedule",
            headers={"X-Tenant-Id": str(uuid4())},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_write_blocked_with_423_when_prefix_paused():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1/plan", 15, "Travão de emergência")

    app = _make_app()
    async with _client(app) as c:
        resp = await c.post(
            "/v1/plan/cpo/schedule",
            headers={"X-Tenant-Id": str(tenant)},
        )
    assert resp.status_code == 423
    body = resp.json()
    assert body["detail"] == "Travão de emergência"
    assert body["route_prefix"] == "/v1/plan"
    assert "expires_at" in body


@pytest.mark.asyncio
async def test_read_passes_even_when_prefix_paused():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1/plan", 15, "x")

    app = _make_app()
    async with _client(app) as c:
        resp = await c.get(
            "/v1/plan/cpo/schedule",
            headers={"X-Tenant-Id": str(tenant)},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_write_passes_for_other_tenant():
    paused_tenant, other_tenant = uuid4(), uuid4()
    pause_registry.register_pause(paused_tenant, "/v1/plan", 15, "x")

    app = _make_app()
    async with _client(app) as c:
        resp = await c.post(
            "/v1/plan/cpo/schedule",
            headers={"X-Tenant-Id": str(other_tenant)},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_write_without_tenant_header_passes_through():
    tenant = uuid4()
    pause_registry.register_pause(tenant, "/v1/plan", 15, "x")

    app = _make_app()
    async with _client(app) as c:
        resp = await c.post("/v1/plan/cpo/schedule")
    # No X-Tenant-Id → middleware defers; downstream answers normally.
    assert resp.status_code == 200
