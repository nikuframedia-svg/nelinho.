"""Q.31.G — `POST /v1/auth/login` + `/refresh`.

Login real por password (decisão D3 do Luis). Cobre:
  * credenciais válidas → 200 + access/refresh tokens + role;
  * password errada / email inexistente / utilizador sem hash → 401;
  * tenant zero → 401;
  * refresh com token válido → novo access token;
  * o access token emitido é verificável por `verify_token`.
"""

from __future__ import annotations

from typing import Any, List
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.shared.api.auth_login import LoginRequest, RefreshRequest, login, refresh
from src.shared.auth.jwt_handler import create_refresh_token, verify_token
from src.shared.auth.passwords import hash_password, verify_password
from src.shared.models.user import User

TENANT = UUID("00000000-0000-0000-0000-000000000001")
ZERO = UUID("00000000-0000-0000-0000-000000000000")


def _user(*, email: str, password: str | None, role: str = "manager_operations") -> User:
    return User(
        id=uuid4(),
        tenant_id=TENANT,
        email=email,
        name="Teste",
        role=role,
        password_hash=hash_password(password) if password is not None else None,
    )


class _FakeSession:
    """AsyncSession mínima: resolve o select(User) por tenant + email."""

    def __init__(self, users: List[User]) -> None:
        self.users = list(users)

    async def execute(self, stmt):
        params = stmt.compile().params
        uuids = [v for v in params.values() if isinstance(v, UUID)]
        strs = [v for v in params.values() if isinstance(v, str)]
        tenant = uuids[0] if uuids else None
        email = strs[0].lower() if strs else None
        hits = [
            u for u in self.users
            if u.tenant_id == tenant and u.email.lower() == email
        ]

        class _Result:
            def scalar_one_or_none(self_: Any):
                return hits[0] if hits else None

        return _Result()


# ── passwords ──────────────────────────────────────────────────────────────


def test_hash_and_verify_roundtrip():
    h = hash_password("segredo-123")
    assert h != "segredo-123"
    assert verify_password("segredo-123", h) is True
    assert verify_password("errada", h) is False


def test_verify_password_rejects_empty_or_malformed():
    assert verify_password("", "x") is False
    assert verify_password("x", "") is False
    assert verify_password("x", "not-a-bcrypt-hash") is False


# ── /login ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_tokens():
    session = _FakeSession([_user(email="luis@nelo.eu", password="kayak2026")])
    result = await login(
        body=LoginRequest(email="luis@nelo.eu", password="kayak2026"),
        x_tenant_id=TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert result.access_token
    assert result.refresh_token
    assert result.role == "manager_operations"
    # O access token tem de ser verificável.
    payload = verify_token(result.access_token, "access")
    assert payload.tenant_id == str(TENANT)


@pytest.mark.asyncio
async def test_login_is_case_insensitive_on_email():
    session = _FakeSession([_user(email="Luis@Nelo.eu", password="kayak2026")])
    result = await login(
        body=LoginRequest(email="LUIS@nelo.EU", password="kayak2026"),
        x_tenant_id=TENANT,
        session=session,  # type: ignore[arg-type]
    )
    assert result.access_token


@pytest.mark.asyncio
async def test_login_wrong_password_is_401():
    session = _FakeSession([_user(email="luis@nelo.eu", password="kayak2026")])
    with pytest.raises(HTTPException) as exc:
        await login(
            body=LoginRequest(email="luis@nelo.eu", password="errada"),
            x_tenant_id=TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_is_401():
    session = _FakeSession([_user(email="luis@nelo.eu", password="kayak2026")])
    with pytest.raises(HTTPException) as exc:
        await login(
            body=LoginRequest(email="ninguem@nelo.eu", password="kayak2026"),
            x_tenant_id=TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_user_without_password_hash_is_401():
    session = _FakeSession([_user(email="sem@nelo.eu", password=None)])
    with pytest.raises(HTTPException) as exc:
        await login(
            body=LoginRequest(email="sem@nelo.eu", password="qualquer"),
            x_tenant_id=TENANT,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_zero_tenant_is_401():
    session = _FakeSession([])
    with pytest.raises(HTTPException) as exc:
        await login(
            body=LoginRequest(email="luis@nelo.eu", password="x"),
            x_tenant_id=ZERO,
            session=session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


# ── /refresh ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_valid_token_returns_new_access():
    rt = create_refresh_token(uuid4(), TENANT, "ceo")
    result = await refresh(body=RefreshRequest(refresh_token=rt))
    assert result.access_token
    payload = verify_token(result.access_token, "access")
    assert payload.role == "ceo"


@pytest.mark.asyncio
async def test_refresh_garbage_token_is_401():
    with pytest.raises(HTTPException) as exc:
        await refresh(body=RefreshRequest(refresh_token="not-a-jwt"))
    assert exc.value.status_code == 401
