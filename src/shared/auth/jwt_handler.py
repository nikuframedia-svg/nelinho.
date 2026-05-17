"""
ProdPlan ONE - JWT Handler
===========================

JWT token creation and verification.

Tokens always carry: sub, tenant_id, role, exp, iat, type. Optionally aud/iss
when configured in `settings`. Verification rejects unsigned tokens, expired
tokens, and any token missing a required claim.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.shared.config import settings

security = HTTPBearer()

REQUIRED_CLAIMS = ["sub", "tenant_id", "role", "exp", "iat", "type"]


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    tenant_id: str
    role: str
    exp: datetime
    iat: datetime
    type: str  # access or refresh


class UserContext(BaseModel):
    """Current user context."""
    user_id: UUID
    tenant_id: UUID
    role: str
    email: Optional[str] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _build_payload(
    *,
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    token_type: str,
    expires_delta: timedelta,
) -> Dict[str, object]:
    now = _now_utc()
    expire = now + expires_delta
    payload: Dict[str, object] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "iat": now,
        "type": token_type,
    }
    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        payload["aud"] = settings.jwt_audience
    return payload


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT access token."""
    expires_delta = expires_delta or timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = _build_payload(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        token_type="access",
        expires_delta=expires_delta,
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
) -> str:
    """Create JWT refresh token."""
    payload = _build_payload(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str, token_type: str = "access") -> TokenPayload:
    """Verify JWT token and return payload.

    Rejects:
    - tokens with `alg=none` (forced via `algorithms=[settings.algorithm]`)
    - tokens with bad signature
    - expired tokens
    - tokens missing any required claim
    - tokens with mismatched `aud`/`iss` (when configured)
    - tokens whose `type` does not match `token_type`
    """
    decode_kwargs = {
        "key": settings.secret_key,
        "algorithms": [settings.algorithm],
        "options": {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_aud": settings.jwt_audience is not None,
            "verify_iss": settings.jwt_issuer is not None,
            "require": REQUIRED_CLAIMS,
        },
    }
    if settings.jwt_audience:
        decode_kwargs["audience"] = settings.jwt_audience
    if settings.jwt_issuer:
        decode_kwargs["issuer"] = settings.jwt_issuer

    try:
        payload = jwt.decode(token, **decode_kwargs)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e!s}",
        )

    # python-jose returns `exp`/`iat` as int (epoch seconds) — coerce to UTC datetime.
    try:
        token_payload = TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            role=payload["role"],
            exp=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
            iat=datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc),
            type=payload["type"],
        )
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed token payload: {e!s}",
        )

    if token_payload.type != token_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type. Expected {token_type}",
        )

    return token_payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserContext:
    """Get current user from JWT token."""
    token = credentials.credentials
    payload = verify_token(token, "access")

    try:
        user_id = UUID(payload.sub)
        tenant_id = UUID(payload.tenant_id)
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token claims are not valid UUIDs: {e!s}",
        )

    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=payload.role,
    )


async def get_current_tenant(
    user: UserContext = Depends(get_current_user),
) -> UUID:
    """Get current tenant ID."""
    return user.tenant_id


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """Generate new access token from refresh token."""
    payload = verify_token(refresh_token, "refresh")

    new_access = create_access_token(
        user_id=UUID(payload.sub),
        tenant_id=UUID(payload.tenant_id),
        role=payload.role,
    )

    return {
        "access_token": new_access,
        "token_type": "bearer",
    }










