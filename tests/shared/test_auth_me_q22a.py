"""Sprint Q.22.A — `GET /v1/auth/me` with real `shared.users` lookup.

The endpoint resolves the request identity against the ``shared.users``
table. Critically, it **never 404s** — the frontend Sidebar always
needs a usable ``CurrentUser``. Tests cover:

* known user_id → 200 with the real persisted email / name / role
* unknown user_id → 200 with the header-derived fallback (NOT 404)
* no X-User-Id at all → 200 with the dev placeholder payload
* a user belonging to another tenant is invisible → fallback
* the route stays ``/v1/auth/me`` and the ``umwelt`` field is present
* an explicit ``X-Umwelt`` header overrides the role-derived umwelt
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.api.auth_me import router as auth_me_router
from src.shared.database import get_session
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT = UUID("00000000-0000-0000-0000-000000000002")
USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def _user(*, tenant_id=TENANT):
    return SimpleNamespace(
        id=USER_ID,
        tenant_id=tenant_id,
        email="luis@nikufra.ai",
        name="Luis",
        role="admin_platform",
    )


class _FakeSession(FakeSession):
    """Q.68.3.4 — subclasse local sobre o canónico.

    O endpoint /v1/auth/me consulta ``shared.users`` por
    (tenant_id, user_id) e espera ``scalar_one_or_none``. O canónico
    serve ``scalar`` via ``queue_scalar``; aqui aplicamos o filtro de
    cross-tenant em Python e usamos a flag ``raise_on_execute`` já
    promovida ao canónico.
    """

    def __init__(self, row):
        super().__init__()
        self._row = row

    async def execute(self, stmt: Any):  # type: ignore[override]
        if self.raise_on_execute:
            raise RuntimeError("DB unavailable")
        # Mimic the WHERE tenant_id == ... filter.
        match = self._row if (self._row is not None and self._row.tenant_id == TENANT) else None
        self.queue_scalar(match)
        return await super().execute(stmt)


def _build_app(session):
    async def _fake_session():
        yield session

    app = FastAPI()
    app.include_router(auth_me_router)
    app.dependency_overrides[get_session] = _fake_session
    return app


def _headers(tenant=TENANT, user=USER_ID, **extra):
    h = {"X-Tenant-Id": str(tenant)}
    if user is not None:
        h["X-User-Id"] = str(user)
    h.update(extra)
    return h


def test_route_is_v1_auth_me_not_v1_me():
    """Contract: the route is /v1/auth/me (frontend authApi.me depends on it)."""
    client = TestClient(_build_app(_FakeSession(_user())))
    # The wrong route the broken Q.22 branch used must 404.
    assert client.get("/v1/me", headers=_headers()).status_code == 404
    # The correct route resolves.
    assert client.get("/v1/auth/me", headers=_headers()).status_code == 200


def test_me_returns_real_profile_for_known_user():
    client = TestClient(_build_app(_FakeSession(_user())))
    resp = client.get("/v1/auth/me", headers=_headers())

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == str(USER_ID)
    assert body["email"] == "luis@nikufra.ai"
    assert body["name"] == "Luis"
    assert body["role"] == "admin_platform"
    assert body["tenant_id"] == str(TENANT)
    # Contract: umwelt must always be present.
    assert "umwelt" in body


def test_me_unknown_user_falls_back_never_404():
    """Unknown X-User-Id → 200 header fallback, NOT 404 (frontend breaks on 404)."""
    client = TestClient(_build_app(_FakeSession(None)))
    resp = client.get(
        "/v1/auth/me",
        headers=_headers(user=UUID("99999999-9999-9999-9999-999999999999")),
    )

    assert resp.status_code == 200
    body = resp.json()
    # Header fallback identity — no real row, placeholder email.
    assert body["email"] == "—"
    assert body["name"] == "Gestor"
    assert body["role"] == "manager"
    assert body["umwelt"] == "manager"


def test_me_no_user_header_returns_dev_placeholder():
    """No X-User-Id at all (dev client) → 200 with usable placeholder."""
    client = TestClient(_build_app(_FakeSession(None)))
    resp = client.get("/v1/auth/me", headers=_headers(user=None))

    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] is None
    assert body["tenant_id"] == str(TENANT)
    assert body["umwelt"] == "manager"


def test_me_cross_tenant_user_is_invisible():
    """A user row owned by another tenant must not leak — falls back instead."""
    client = TestClient(_build_app(_FakeSession(_user(tenant_id=OTHER_TENANT))))
    resp = client.get("/v1/auth/me", headers=_headers(tenant=TENANT))

    assert resp.status_code == 200
    body = resp.json()
    # No match for TENANT → fallback, real email not exposed.
    assert body["email"] == "—"


def test_me_db_error_degrades_to_header_fallback():
    """If the User lookup raises, the endpoint still returns a usable payload."""
    session = _FakeSession(_user())
    session.raise_on_execute = True
    client = TestClient(_build_app(session))
    resp = client.get(
        "/v1/auth/me",
        headers=_headers(**{"X-User-Name": "DevUser", "X-User-Role": "operator"}),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "DevUser"
    assert body["role"] == "operator"


def test_me_explicit_umwelt_header_overrides_role():
    """The UmweltSwitcher sends X-Umwelt to view another mode — it wins."""
    client = TestClient(_build_app(_FakeSession(_user())))
    resp = client.get("/v1/auth/me", headers=_headers(**{"X-Umwelt": "ceo"}))

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin_platform"  # real role unchanged
    assert body["umwelt"] == "ceo"  # but umwelt follows the header
