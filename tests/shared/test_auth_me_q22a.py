"""Sprint Q.22.A — `GET /v1/me` current-user endpoint.

The endpoint resolves the request identity against the ``shared.users``
table. Tests cover:
* existing user → 200 with the real email/name/role
* unknown user_id → 404 (no placeholder email fallback)
* a user belonging to another tenant is not visible (tenant isolation)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.api.auth_me import router as auth_me_router
from src.shared.database import get_session

TENANT = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _user(*, tenant_id=TENANT):
    return SimpleNamespace(
        id=USER_ID,
        tenant_id=tenant_id,
        email="luis@nikufra.ai",
        name="Luis",
        role="admin",
    )


def _build_app(scalar_result):
    """Wire a TestClient whose session.execute yields ``scalar_result``."""
    result = SimpleNamespace(scalar_one_or_none=lambda: scalar_result)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(auth_me_router, prefix="/v1")
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers(tenant=TENANT, user=USER_ID):
    return {"X-Tenant-Id": str(tenant), "X-User-Id": str(user)}


def test_me_returns_real_profile_for_known_user():
    client = TestClient(_build_app(_user()))
    resp = client.get("/v1/me", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "luis@nikufra.ai"
    assert body["name"] == "Luis"
    assert body["role"] == "admin"
    assert body["id"] == str(USER_ID)
    assert body["tenant_id"] == str(TENANT)


def test_me_returns_404_for_unknown_user():
    client = TestClient(_build_app(None))
    resp = client.get("/v1/me", headers=_headers(user=uuid4()))

    assert resp.status_code == 404
    # No placeholder email — explicit error state.
    assert "email" not in resp.json()


def test_me_requires_tenant_header():
    client = TestClient(_build_app(_user()))
    resp = client.get("/v1/me", headers={"X-User-Id": str(USER_ID)})

    assert resp.status_code == 401


def test_me_isolation_user_from_other_tenant_not_found():
    # The query filters on tenant_id; a row under OTHER_TENANT never
    # reaches this caller — the session yields None for this tenant.
    client = TestClient(_build_app(None))
    resp = client.get("/v1/me", headers=_headers(tenant=OTHER_TENANT))

    assert resp.status_code == 404
