"""Tests for src/shared/auth/headers.py — JWT-first tenant resolution (S2)."""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException, Depends
from fastapi.testclient import TestClient

from src.shared.auth.headers import (
    ZERO_UUID,
    require_admin,
    require_tenant_header,
    require_user_header,
    require_user_uuid,
)
from src.shared.auth.jwt_handler import create_access_token
from src.shared.config import settings

JWT_TENANT = UUID("00000000-0000-0000-0000-00000000aaaa")
JWT_USER = UUID("00000000-0000-0000-0000-00000000bbbb")
HEADER_TENANT = UUID("00000000-0000-0000-0000-00000000cccc")
HEADER_USER = UUID("00000000-0000-0000-0000-00000000dddd")


# --- helper app ---------------------------------------------------------------

def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami-tenant")
    def whoami_tenant(tenant_id: UUID = Depends(require_tenant_header)):
        return {"tenant_id": str(tenant_id)}

    @app.get("/whoami-user")
    def whoami_user(user_id: str = Depends(require_user_header)):
        return {"user_id": user_id}

    @app.get("/whoami-uuid")
    def whoami_uuid(user_id: UUID = Depends(require_user_uuid)):
        return {"user_id": str(user_id)}

    @app.get("/admin-only")
    def admin_only(ctx=Depends(require_admin)):
        return {"role": ctx.role, "source": ctx.source}

    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


# --- JWT first ----------------------------------------------------------------

def test_jwt_tenant_overrides_spoofed_header(client):
    """A client cannot impersonate another tenant via X-Tenant-Id when a JWT
    is present — the JWT's tenant_id wins."""
    token = create_access_token(JWT_USER, JWT_TENANT, "manager_operations")
    r = client.get(
        "/whoami-tenant",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": str(HEADER_TENANT),  # spoofing attempt
        },
    )
    assert r.status_code == 200
    assert r.json()["tenant_id"] == str(JWT_TENANT)


def test_jwt_user_uuid_overrides_header(client):
    token = create_access_token(JWT_USER, JWT_TENANT, "manager_operations")
    r = client.get(
        "/whoami-uuid",
        headers={
            "Authorization": f"Bearer {token}",
            "X-User-Id": str(HEADER_USER),
        },
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == str(JWT_USER)


# --- header fallback in dev ---------------------------------------------------

def test_header_fallback_in_dev(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    r = client.get("/whoami-tenant", headers={"X-Tenant-Id": str(HEADER_TENANT)})
    assert r.status_code == 200
    assert r.json()["tenant_id"] == str(HEADER_TENANT)


def test_zero_uuid_header_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    r = client.get("/whoami-tenant", headers={"X-Tenant-Id": str(ZERO_UUID)})
    assert r.status_code == 401


def test_missing_header_in_dev_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    r = client.get("/whoami-tenant")
    assert r.status_code == 401


# --- production strictness ----------------------------------------------------

def test_production_requires_jwt(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    # Header without JWT → 401, no fallback.
    r = client.get("/whoami-tenant", headers={"X-Tenant-Id": str(HEADER_TENANT)})
    assert r.status_code == 401


def test_production_bad_jwt_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    r = client.get(
        "/whoami-tenant",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401


# --- require_user_uuid: zero UUID ---------------------------------------------

def test_require_user_uuid_rejects_zero_in_dev(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    r = client.get("/whoami-uuid", headers={"X-User-Id": str(ZERO_UUID)})
    assert r.status_code == 401


# --- require_admin ------------------------------------------------------------

def test_admin_with_admin_jwt(client):
    token = create_access_token(JWT_USER, JWT_TENANT, "admin_platform")
    r = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["source"] == "jwt"


def test_admin_with_non_admin_jwt_forbidden(client):
    token = create_access_token(JWT_USER, JWT_TENANT, "operator")
    r = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_admin_legacy_header_in_dev(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development", raising=False)
    r = client.get(
        "/admin-only",
        headers={"X-User-Id": "alice", "X-User-Role": "admin_platform"},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "legacy_header"


def test_admin_legacy_header_blocked_in_prod(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production", raising=False)
    r = client.get(
        "/admin-only",
        headers={"X-User-Id": "alice", "X-User-Role": "admin_platform"},
    )
    assert r.status_code == 401
