"""Sprint Q.18.A.4 — legacy /api/* uses fail-closed tenant dependency.

Why this test exists
--------------------
``src/legacy/api.py`` used to define a private ``get_tenant_id`` that
just returned whatever ``X-Tenant-Id`` UUID was sent — including the
zero UUID. CLAUDE.md is explicit:

    Zero UUID (00000000-0000-0000-0000-000000000000) é rejeitado por
    design (Q.12 Onda 0.1). Dev tenant é …001.

That guarantee covered the rest of the API but the legacy router
silently bypassed it on ``/api/orders``, ``/api/allocations`` and
``/api/errors``. This test locks the fail-closed behaviour so it
can't drift back.

We don't go anywhere near a real database — the dep gate is what
matters here. ``get_session`` is overridden with a stub that never
actually runs.
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.legacy.api import router as legacy_router
from src.shared.config import settings
from src.shared.database import get_session


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
DEV_TENANT = "00000000-0000-0000-0000-000000000001"


async def _stub_session() -> AsyncIterator[AsyncMock]:
    sess = AsyncMock()
    yield sess


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    app = FastAPI()
    app.include_router(legacy_router)
    app.dependency_overrides[get_session] = _stub_session
    # raise_server_exceptions=False: handler-level errors become 500
    # responses instead of bubbling up. We only care about the gate
    # (401 vs not-401), so a 500 from the stubbed session is fine.
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Endpoints to exercise — one per "shape" so we don't shadow a single buggy
# default with a single buggy dep override.
# ---------------------------------------------------------------------------

LEGACY_GET_PATHS = [
    # Q.61.32a — /api/orders e /api/orders/stats migrados para
    # /v1/plan/orders e /v1/plan/orders/stats. Cobertura fail-closed
    # vive agora em tests/plan/test_orders_api_migrated_q61_32a.py.
    "/api/allocations",
    "/api/allocations/stats",
    "/api/errors",
    "/api/errors/stats",
]


@pytest.mark.parametrize("path", LEGACY_GET_PATHS)
def test_zero_uuid_rejected(client, path):
    """Zero-UUID tenant id must NOT be accepted."""
    resp = client.get(path, headers={"X-Tenant-Id": ZERO_UUID})
    assert resp.status_code == 401, (
        f"{path} accepted zero UUID — fail-closed broken; got {resp.status_code}"
    )


@pytest.mark.parametrize("path", LEGACY_GET_PATHS)
def test_missing_header_rejected(client, path):
    """No tenant header at all → 401 (was previously 422 from Header(...) but
    that's a leak: clients distinguishing 422 from 401 can probe).

    require_tenant_header makes this 401 across the board.
    """
    resp = client.get(path)
    assert resp.status_code == 401, resp.text


def test_valid_dev_tenant_passes_dep_gate(client):
    """A valid non-zero UUID makes it past the gate.

    The handler may still 5xx because we stubbed the session, but the
    gate itself must accept the request — that's what we're asserting.
    Q.61.32a — exemplo passa a usar `/api/allocations` (orders migrou).
    """
    resp = client.get("/api/allocations", headers={"X-Tenant-Id": DEV_TENANT})
    # 200 if the handler tolerates the AsyncMock session, otherwise 5xx.
    # The point is "not 401" — the dep let it through.
    assert resp.status_code != 401, resp.text


def test_production_requires_jwt(monkeypatch):
    """Legacy endpoints in production must require a JWT — header alone is rejected.

    Q.61.32a — exemplo passa a usar `/api/allocations` (orders migrou).
    """
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    app = FastAPI()
    app.include_router(legacy_router)
    app.dependency_overrides[get_session] = _stub_session
    c = TestClient(app, raise_server_exceptions=False)

    resp = c.get("/api/allocations", headers={"X-Tenant-Id": DEV_TENANT})
    assert resp.status_code == 401, resp.text
    assert "JWT" in resp.json().get("detail", "")
