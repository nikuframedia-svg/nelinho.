"""Header-based auth helpers for endpoints that have not yet migrated
to JWT (`get_current_tenant`/`get_current_user` in :mod:`jwt_handler`).

Sprint Q.12 Onda 0.1 — these replace the per-router copies of
``get_tenant_id``/``get_current_user`` that defaulted to a zero UUID
(``00000000-0000-0000-0000-000000000000``) or ``"api_user"`` when the
header was absent. That default silently hijacked the "tenant zero" in
multi-tenant SaaS: any unauthenticated request landed there, mixing
tenants in audit logs and bypassing isolation.

Sprint Q.12 Onda 0.2 — :func:`require_admin` adds a centralised admin
gate. Production requires a real JWT (no unsigned header fallback);
development still accepts ``X-User-Role`` so the existing tests + dev
tooling don't have to be retrofitted in the same sprint.

Design: fail-closed. Missing/blank/zero header → ``401`` with a clear
message instead of a silent fallback. Endpoints that genuinely have no
tenant scope (health checks, metrics) should not depend on this.

Migration strategy: the JWT-backed dependencies in :mod:`jwt_handler`
remain the long-term answer. These helpers exist so every API surface
can stop the bleeding without each team having to plumb JWT through
their tests in the same sprint.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Header, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import Request

from src.shared.auth.jwt_handler import verify_token
from src.shared.config import settings

logger = logging.getLogger(__name__)

ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")

# Admin role tokens — keep in sync with :class:`src.shared.auth.rbac.Role`.
# ``admin_tenant`` is accepted because the rbac module has historically
# carried both spellings; once the enum is the single source of truth
# this set can shrink.
_ADMIN_ROLES = {"admin", "admin_platform", "admin_tenant"}


def _try_jwt(request: Request):
    """Decode the Bearer JWT if present. Returns the verified TokenPayload or None.

    In production a malformed/expired Bearer is fatal (raises). In dev/test
    we let the caller fall through to the legacy header path so the existing
    test client doesn't have to be JWT-enabled in the same sprint.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    scheme, token = get_authorization_scheme_param(auth) if auth else ("", "")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return verify_token(token, "access")
    except HTTPException:
        if settings.environment == "production":
            raise
        return None


def require_tenant_header(
    request: Request,
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-Id"),
) -> UUID:
    """Resolve the request's tenant.

    Order:
    1. **JWT first.** If a valid Bearer token is present, its ``tenant_id``
       claim wins. Any ``X-Tenant-Id`` header that disagrees is ignored —
       a client cannot impersonate a tenant by spoofing the header.
    2. **Header fallback (dev/test only).** If no JWT and not production,
       accept ``X-Tenant-Id`` as long as it's present and non-zero.
    3. **401** otherwise.
    """
    payload = _try_jwt(request)
    if payload is not None:
        try:
            return UUID(payload.tenant_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token tenant_id claim is not a valid UUID",
            )

    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer JWT required in production",
        )

    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Tenant-Id header is required",
        )
    if x_tenant_id == ZERO_UUID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant: zero UUID is reserved",
        )
    return x_tenant_id


def require_user_header(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    """Resolve the request's user id (string form).

    JWT first; legacy ``X-User-Id`` only in dev/test. Production with no
    Bearer raises 401.
    """
    payload = _try_jwt(request)
    if payload is not None:
        return payload.sub

    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer JWT required in production",
        )

    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is required",
        )
    return x_user_id.strip()


def require_user_uuid(
    request: Request,
    x_user_id: UUID | None = Header(default=None, alias="X-User-Id"),
) -> UUID:
    """Like :func:`require_user_header` but returns a UUID.

    Use for endpoints whose service layer types user_id as UUID (e.g.
    governance decisions, sandbox publish). Rejects ``"api_user"``-style
    string defaults at the type level.
    """
    payload = _try_jwt(request)
    if payload is not None:
        try:
            return UUID(payload.sub)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token sub claim is not a valid UUID",
            )

    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer JWT required in production",
        )

    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is required",
        )
    if x_user_id == ZERO_UUID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user: zero UUID is reserved",
        )
    return x_user_id


class AdminContext:
    """Minimal admin context returned by :func:`require_admin`.

    Carries enough identity to write an audit log row without forcing
    callers to chain three separate header dependencies. Always carries
    a ``role`` string in :data:`_ADMIN_ROLES`.
    """

    __slots__ = ("user_id", "role", "source")

    def __init__(self, *, user_id: str, role: str, source: str) -> None:
        self.user_id = user_id
        self.role = role
        # ``source`` is "jwt" or "legacy_header" — useful for logging
        # and for tightening the gate later.
        self.source = source


def require_admin(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> AdminContext:
    """Admin gate that prefers JWT, falls back to legacy headers in dev.

    Production (``settings.environment == "production"``) requires a
    valid ``Authorization: Bearer <token>`` whose decoded payload has a
    ``role`` in :data:`_ADMIN_ROLES`. Anything else → ``401``/``403``.

    Development/test environments additionally accept the legacy pair
    ``X-User-Id`` + ``X-User-Role`` so existing tests and the
    ``/admin/learned-rules`` page don't have to be retrofitted in the
    same sprint that closes the security hole.
    """
    payload = _try_jwt(request)
    if payload is not None:
        if payload.role.lower() not in _ADMIN_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{payload.role}' lacks admin privileges",
            )
        return AdminContext(user_id=payload.sub, role=payload.role, source="jwt")

    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Admin endpoints require a Bearer JWT in production; "
                "legacy X-User-Role headers are rejected."
            ),
        )

    if not x_user_role or x_user_role.lower() not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is required",
        )
    logger.debug(
        "Admin endpoint accessed via unsigned header (env=%s user=%s role=%s)",
        settings.environment, x_user_id, x_user_role,
    )
    return AdminContext(
        user_id=x_user_id.strip(), role=x_user_role.lower(), source="legacy_header",
    )
