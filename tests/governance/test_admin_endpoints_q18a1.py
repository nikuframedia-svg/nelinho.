"""Sprint Q.18.A.1 — admin gate on irreversible governance endpoints.

(Q.168 F4.E: ``decisions/bulk`` saiu da matriz — o endpoint órfão foi
removido; ver ``test_governance_bulk_route_removed_q168_f4e``.)

The endpoints below used to accept any authenticated user (only
``require_user_header`` was applied). That meant any logged-in operator
could ``POST /v1/governance/kill-switch`` and stop production in their
own tenant — directly contradicting the YAML policy schema's
``Literal["admin_only"]`` invariant.

This test asserts the admin gate for each route, in dev mode (where
``X-User-Role`` legacy header is accepted) and via JWT.

Strategy
--------
Real ``governance.router`` mounted on a small FastAPI app. The
``GovernanceService`` is overridden with an ``AsyncMock`` so we never
touch a database — we only care about whether the dep gate fires.
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.governance.api import (
    get_governance_service,
    get_tenant_id,
    router as governance_router,
)
from src.shared.auth.jwt_handler import create_access_token
from src.shared.config import settings


TENANT_ID = UUID("00000000-0000-0000-0000-00000000aaaa")
USER_ID = UUID("00000000-0000-0000-0000-00000000bbbb")


def _fake_service() -> AsyncMock:
    svc = AsyncMock()
    svc.activate_kill_switch.return_value = {
        "id": "ks-1",
        "executed_at": "2026-05-08T12:00:00Z",
    }
    svc.execute_decision.return_value = {
        "status": "executed",
        "executed_at": "2026-05-08T12:00:00Z",
        "outcome_hash": "deadbeef",
    }
    svc.rollback_decision.return_value = {
        "status": "rolled_back",
        "rolled_back_at": "2026-05-08T12:00:00Z",
    }
    svc.modify_payload.return_value = {"id": "d-1", "patched": True}
    return svc


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    application = FastAPI()
    application.include_router(governance_router)
    application.dependency_overrides[get_governance_service] = lambda: _fake_service()
    application.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

def _admin_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": str(TENANT_ID),
        "X-User-Id": str(USER_ID),
        "X-User-Role": "admin_platform",
    }


def _operator_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": str(TENANT_ID),
        "X-User-Id": str(USER_ID),
        "X-User-Role": "operator",
    }


def _no_role_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": str(TENANT_ID),
        "X-User-Id": str(USER_ID),
    }


# ---------------------------------------------------------------------------
# Endpoint × auth matrix
# ---------------------------------------------------------------------------

ROUTES = [
    {
        "name": "kill-switch",
        "method": "POST",
        "path": "/v1/governance/kill-switch",
        "params": {"scope": "all", "reason": "production smoke fire test"},
        "json": None,
    },
    {
        "name": "decisions.execute",
        "method": "POST",
        "path": "/v1/governance/decisions/d-1/execute",
        "params": None,
        "json": None,
    },
    {
        "name": "decisions.rollback",
        "method": "POST",
        "path": "/v1/governance/decisions/d-1/rollback",
        "params": {"reason": "rollback because tested"},
        "json": None,
    },
    {
        "name": "decisions.payload",
        "method": "PATCH",
        "path": "/v1/governance/decisions/d-1/payload",
        "params": None,
        "json": {"patch": {"foo": "bar"}, "reason": "patched for test"},
    },
]


def _call(client: TestClient, route: dict, headers: dict) -> int:
    method = client.patch if route["method"] == "PATCH" else client.post
    resp = method(
        route["path"],
        params=route["params"],
        json=route["json"],
        headers=headers,
    )
    return resp.status_code


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r["name"])
def test_admin_role_allowed(client, route):
    """admin_platform legacy header → 2xx."""
    status_code = _call(client, route, _admin_headers())
    assert status_code < 400, f"admin should pass {route['name']} but got {status_code}"


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r["name"])
def test_operator_role_forbidden(client, route):
    """operator role → 403 Forbidden (admin gate enforced)."""
    status_code = _call(client, route, _operator_headers())
    assert status_code == 403, f"operator must be 403 for {route['name']}, got {status_code}"


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r["name"])
def test_no_role_header_forbidden(client, route):
    """No X-User-Role header → 403 (require_admin needs explicit role)."""
    status_code = _call(client, route, _no_role_headers())
    assert status_code == 403, f"no-role must be 403 for {route['name']}, got {status_code}"


def test_governance_bulk_route_removed_q168_f4e(client):
    """Q.168 F4.E — ``POST /v1/governance/decisions/bulk`` foi removido.

    O endpoint era órfão: o frontend migrou no Q.130.I para
    ``/v1/decisions/bulk`` (tabela ``shared.decision_runs``); este operava
    na tabela DIFERENTE ``governance.decision_run`` — um caller enganado
    aprovaria decisões na casa errada. Mesmo com headers de admin tem de
    ser 404.
    """
    resp = client.post(
        "/v1/governance/decisions/bulk",
        json={"items": []},
        headers=_admin_headers(),
    )
    # 405 (não 404): o path "bulk" ainda casa com GET /decisions/{decision_id},
    # mas o handler POST desapareceu — qualquer um dos dois prova a remoção.
    assert resp.status_code in (404, 405)


# ---------------------------------------------------------------------------
# Production guard — legacy header is rejected; only JWT works.
# ---------------------------------------------------------------------------

def test_kill_switch_admin_via_jwt_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    application = FastAPI()
    application.include_router(governance_router)
    application.dependency_overrides[get_governance_service] = lambda: _fake_service()
    application.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    c = TestClient(application)

    token = create_access_token(USER_ID, TENANT_ID, "admin_platform")
    resp = c.post(
        "/v1/governance/kill-switch",
        params={"scope": "all", "reason": "prod smoke fire test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code < 400, resp.text


def test_kill_switch_legacy_header_blocked_in_production(monkeypatch):
    """In prod, legacy ``X-User-Role`` is rejected even when role=admin."""
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    application = FastAPI()
    application.include_router(governance_router)
    application.dependency_overrides[get_governance_service] = lambda: _fake_service()
    application.dependency_overrides[get_tenant_id] = lambda: TENANT_ID
    c = TestClient(application)

    resp = c.post(
        "/v1/governance/kill-switch",
        params={"scope": "all", "reason": "should not pass in prod"},
        headers=_admin_headers(),
    )
    assert resp.status_code == 401, resp.text
