"""Tests for src/shared/auth/jwt_handler.py — strict JWT verification (S1)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException
from jose import jwt

from src.shared.auth.jwt_handler import (
    REQUIRED_CLAIMS,
    UserContext,
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_token,
)
from src.shared.config import settings

USER_ID = UUID("00000000-0000-0000-0000-00000000aaaa")
TENANT_ID = UUID("00000000-0000-0000-0000-00000000bbbb")
ROLE = "manager_operations"


def _encode(payload: dict, *, secret: str | None = None, algorithm: str | None = None) -> str:
    return jwt.encode(
        payload,
        secret if secret is not None else settings.secret_key,
        algorithm=algorithm or settings.algorithm,
    )


# --- happy path ---------------------------------------------------------------

def test_round_trip_access_token():
    token = create_access_token(USER_ID, TENANT_ID, ROLE)
    payload = verify_token(token, "access")
    assert payload.sub == str(USER_ID)
    assert payload.tenant_id == str(TENANT_ID)
    assert payload.role == ROLE
    assert payload.type == "access"
    assert payload.exp.tzinfo is not None  # timezone-aware


def test_refresh_token_round_trip():
    token = create_refresh_token(USER_ID, TENANT_ID, ROLE)
    payload = verify_token(token, "refresh")
    assert payload.type == "refresh"


# --- expiry -------------------------------------------------------------------

def test_expired_token_rejected():
    expired_payload = {
        "sub": str(USER_ID),
        "tenant_id": str(TENANT_ID),
        "role": ROLE,
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=10),
        "type": "access",
    }
    token = _encode(expired_payload)
    with pytest.raises(HTTPException) as exc:
        verify_token(token, "access")
    assert exc.value.status_code == 401


def test_token_without_exp_rejected():
    payload_no_exp = {
        "sub": str(USER_ID),
        "tenant_id": str(TENANT_ID),
        "role": ROLE,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = _encode(payload_no_exp)
    with pytest.raises(HTTPException) as exc:
        verify_token(token, "access")
    assert exc.value.status_code == 401


# --- signature ----------------------------------------------------------------

def test_bad_signature_rejected():
    token = create_access_token(USER_ID, TENANT_ID, ROLE)
    # Flip last byte of the signature segment.
    head, payload_b64, sig = token.rsplit(".", 2)
    tampered = f"{head}.{payload_b64}.{sig[:-2]}aa"
    with pytest.raises(HTTPException) as exc:
        verify_token(tampered, "access")
    assert exc.value.status_code == 401


def test_token_signed_with_wrong_secret_rejected():
    foreign = _encode(
        {
            "sub": str(USER_ID),
            "tenant_id": str(TENANT_ID),
            "role": ROLE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "type": "access",
        },
        secret="another-secret-of-at-least-32-characters!!",
    )
    with pytest.raises(HTTPException) as exc:
        verify_token(foreign, "access")
    assert exc.value.status_code == 401


# --- alg=none -----------------------------------------------------------------

def test_alg_none_token_rejected():
    """A hand-forged `alg=none` JWT must be rejected at verify time."""
    import base64
    import json

    def b64(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    header = b64({"alg": "none", "typ": "JWT"})
    body = b64({
        "sub": str(USER_ID),
        "tenant_id": str(TENANT_ID),
        "role": ROLE,
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "type": "access",
    })
    forged = f"{header}.{body}."  # empty signature
    with pytest.raises(HTTPException) as exc:
        verify_token(forged, "access")
    assert exc.value.status_code == 401


# --- required claims ----------------------------------------------------------

@pytest.mark.parametrize("missing_claim", ["sub", "tenant_id", "role", "exp", "iat", "type"])
def test_missing_required_claim_rejected(missing_claim: str):
    full = {
        "sub": str(USER_ID),
        "tenant_id": str(TENANT_ID),
        "role": ROLE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    full.pop(missing_claim)
    token = _encode(full)
    with pytest.raises(HTTPException) as exc:
        verify_token(token, "access")
    assert exc.value.status_code == 401


def test_required_claims_constant_matches_token_payload_fields():
    """Guard: keep REQUIRED_CLAIMS in sync with TokenPayload model."""
    assert set(REQUIRED_CLAIMS) == {"sub", "tenant_id", "role", "exp", "iat", "type"}


# --- token type mismatch ------------------------------------------------------

def test_access_token_used_as_refresh_rejected():
    token = create_access_token(USER_ID, TENANT_ID, ROLE)
    with pytest.raises(HTTPException) as exc:
        verify_token(token, "refresh")
    assert exc.value.status_code == 401


# --- malformed UUID claims ----------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_user_rejects_non_uuid_claims():
    from fastapi.security import HTTPAuthorizationCredentials

    bad_payload = {
        "sub": "not-a-uuid",
        "tenant_id": str(TENANT_ID),
        "role": ROLE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    token = _encode(bad_payload)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_returns_context_for_valid_token():
    from fastapi.security import HTTPAuthorizationCredentials

    token = create_access_token(USER_ID, TENANT_ID, ROLE)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(creds)
    assert isinstance(user, UserContext)
    assert user.user_id == USER_ID
    assert user.tenant_id == TENANT_ID
    assert user.role == ROLE


# --- iss / aud (when configured) ---------------------------------------------

def test_aud_iss_verification(monkeypatch):
    monkeypatch.setattr(settings, "jwt_audience", "prodplan-api", raising=False)
    monkeypatch.setattr(settings, "jwt_issuer", "prodplan-issuer", raising=False)

    # Token with matching aud/iss must pass.
    good = create_access_token(USER_ID, TENANT_ID, ROLE)
    payload = verify_token(good, "access")
    assert payload.sub == str(USER_ID)

    # Token with wrong aud must fail.
    wrong_aud = _encode(
        {
            "sub": str(USER_ID),
            "tenant_id": str(TENANT_ID),
            "role": ROLE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "type": "access",
            "aud": "someone-else",
            "iss": "prodplan-issuer",
        },
    )
    with pytest.raises(HTTPException):
        verify_token(wrong_aud, "access")

    # Token with wrong iss must fail.
    wrong_iss = _encode(
        {
            "sub": str(USER_ID),
            "tenant_id": str(TENANT_ID),
            "role": ROLE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "type": "access",
            "aud": "prodplan-api",
            "iss": "evil",
        },
    )
    with pytest.raises(HTTPException):
        verify_token(wrong_iss, "access")
