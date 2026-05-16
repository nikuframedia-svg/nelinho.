"""Sprint Q.18.A.2 — RBACMiddleware enforces ROUTE_PREFIX_REQUIREMENTS.

Coverage targets
----------------
1. **Bypass posture** — health/docs/OPTIONS preflight pass without auth
   even when the middleware is mounted.
2. **Fall-through posture** — paths without a matrix entry fall through
   silently (gradual rollout: a new router doesn't lock everyone out).
3. **Auth gate** — paths with a matrix entry require auth (401 if
   missing) and the correct permission (403 otherwise).
4. **Role resolution** — JWT wins; legacy ``X-User-Role`` works in dev,
   not in production.

The matrix entries we lean on:
    /v1/profit/dashboard  GET  → [COGS_READ]
    /v1/core/customers    *    → [MASTER_DATA_WRITE]

These are stable and chosen because the read role (CEO) and the
write role (PLANNER_SUPPLY) differ — that lets us catch silent allow
bugs that a single-role test wouldn't.
"""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.auth.jwt_handler import create_access_token
from src.shared.auth.middleware import RBACMiddleware
from src.shared.config import settings


TENANT_ID = UUID("00000000-0000-0000-0000-00000000aaaa")
USER_ID = UUID("00000000-0000-0000-0000-00000000bbbb")


@pytest.fixture(autouse=True)
def _force_dev(monkeypatch):
    """Most tests assume dev mode. Production-mode tests override locally."""
    monkeypatch.setattr(settings, "environment", "development", raising=False)


def _build_app() -> FastAPI:
    """Tiny app whose paths land on three different matrix entries.

    /v1/profit/dashboard  → GET requires COGS_READ (matrix entry)
    /v1/core/customers    → * requires MASTER_DATA_WRITE (matrix entry)
    /v1/no-rbac/anything  → no matrix entry (fall-through)
    /health               → bypassed
    """
    app = FastAPI()
    app.add_middleware(RBACMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/v1/profit/dashboard")
    async def dashboard():
        return {"data": "ceo-only"}

    @app.post("/v1/core/customers")
    async def customers():
        return {"created": True}

    @app.get("/v1/no-rbac/anything")
    async def no_matrix():
        return {"open": True}

    return app


@pytest.fixture
def client():
    return TestClient(_build_app())


# ---------------------------------------------------------------------------
# 1) Bypass paths
# ---------------------------------------------------------------------------

def test_health_bypassed_without_auth(client):
    assert client.get("/health").status_code == 200


def test_options_preflight_bypassed(client):
    """OPTIONS never enforced — let CORS handle it."""
    resp = client.options("/v1/profit/dashboard")
    # FastAPI returns 405 for unhandled OPTIONS, NOT 401. The point is
    # the gate did not respond first with 401.
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# 2) Fall-through (path without matrix entry)
# ---------------------------------------------------------------------------

def test_path_without_matrix_entry_falls_through(client):
    """No matrix entry → middleware does not enforce; route is reachable."""
    assert client.get("/v1/no-rbac/anything").status_code == 200


# ---------------------------------------------------------------------------
# 3) Auth gate (matrix entry exists)
# ---------------------------------------------------------------------------

def test_no_auth_returns_401(client):
    resp = client.get("/v1/profit/dashboard")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


def test_wrong_role_returns_403(client):
    """OPERATOR has no COGS_READ — must be 403, not 401, not 200."""
    resp = client.get(
        "/v1/profit/dashboard",
        headers={"X-User-Role": "operator"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["role"] == "operator"
    assert "cogs:read" in body["required"]


def test_correct_role_passes_dashboard(client):
    """CEO is read-only across the dashboard surface and HAS COGS_READ."""
    resp = client.get(
        "/v1/profit/dashboard",
        headers={"X-User-Role": "ceo"},
    )
    assert resp.status_code == 200, resp.text


def test_correct_role_passes_write(client):
    """PLANNER_SUPPLY does NOT have MASTER_DATA_WRITE → 403.
    MANAGER_OPERATIONS does → 200. Asserts both, since silent-allow is
    the worst-case bug.
    """
    blocked = client.post(
        "/v1/core/customers",
        headers={"X-User-Role": "planner_supply"},
    )
    assert blocked.status_code == 403, blocked.text

    allowed = client.post(
        "/v1/core/customers",
        headers={"X-User-Role": "manager_operations"},
    )
    assert allowed.status_code == 200, allowed.text


# ---------------------------------------------------------------------------
# 4) Role resolution: JWT wins; legacy header dev-only
# ---------------------------------------------------------------------------

def test_jwt_role_resolved(client):
    token = create_access_token(USER_ID, TENANT_ID, "ceo")
    resp = client.get(
        "/v1/profit/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


def test_invalid_jwt_returns_401(client):
    resp = client.get(
        "/v1/profit/dashboard",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert resp.status_code == 401


def test_legacy_header_blocked_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    c = TestClient(_build_app())
    resp = c.get(
        "/v1/profit/dashboard",
        headers={"X-User-Role": "ceo"},
    )
    assert resp.status_code == 401


def test_jwt_works_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    c = TestClient(_build_app())
    token = create_access_token(USER_ID, TENANT_ID, "ceo")
    resp = c.get(
        "/v1/profit/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# 5) Wiring smoke — main.py only mounts when strict OR production.
# ---------------------------------------------------------------------------

def test_main_does_not_mount_middleware_in_dev_default(monkeypatch):
    """Importing src.main in dev with rbac_strict=False must NOT register RBACMiddleware.

    Guards against accidentally locking out the dev frontend.
    Importing src.main pulls heavy ML deps (pandas, numpy, sklearn,
    deap/ortools); those are present in the project venv but may be
    absent in trimmed test runners. Skip in that case — the wiring
    logic itself is one ``if`` we can read by eye.
    """
    pytest.importorskip("pandas")
    pytest.importorskip("sklearn")

    monkeypatch.setattr(settings, "rbac_strict", False, raising=False)
    monkeypatch.setattr(settings, "environment", "development", raising=False)

    import importlib

    import src.main as main_module
    main_module = importlib.reload(main_module)

    middleware_classes = [m.cls.__name__ for m in main_module.app.user_middleware]
    assert "RBACMiddleware" not in middleware_classes, middleware_classes
