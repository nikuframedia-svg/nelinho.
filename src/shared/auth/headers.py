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

from src.shared.auth.jwt_handler import UserContext, verify_token
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


def get_current_user_or_dev_header(
    request: Request,
    x_user_id: UUID | None = Header(default=None, alias="X-User-Id"),
    x_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> UserContext:
    """JWT-first com dev-fallback por headers, devolvendo um ``UserContext``.

    Q.121.D3 — o ``PermissionDependency`` (rbac) dependia de
    ``jwt_handler.get_current_user``, que usa ``HTTPBearer(auto_error=True)`` e
    levanta 401 "Not authenticated" SEM Bearer, antes de qualquer fallback. Por
    isso /v1/work-orders, /v1/master-data/*, /v1/user-input davam 401 no painel
    dev — enquanto /v1/decisions (que usa os helpers de header) funcionava.

    Esta dependência espelha :func:`require_user_uuid`/:func:`require_tenant_header`:

    1. **JWT primeiro** — Bearer válido → ``UserContext`` do payload.
    2. **Produção sem JWT → 401** (nunca aceita headers não-assinados).
    3. **Dev/test sem JWT** → ``UserContext`` a partir de X-User-Id/X-Tenant-Id/
       X-User-Role (mesmo modelo que /v1/decisions já usa). Zero-UUID rejeitado.
    """
    payload = _try_jwt(request)
    if payload is not None:
        try:
            return UserContext(
                user_id=UUID(payload.sub),
                tenant_id=UUID(payload.tenant_id),
                role=payload.role,
            )
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token claims are not valid UUIDs: {exc!s}",
            )

    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer JWT required in production",
        )

    if x_user_id is None or x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id e X-Tenant-Id headers required (dev)",
        )
    if x_user_id == ZERO_UUID or x_tenant_id == ZERO_UUID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity: zero UUID is reserved",
        )
    # Q.121.D3 — o frontend envia X-User-Role "admin" (genérico); o enum rbac.Role
    # canónico do admin é "admin_platform" (tem todas as permissões). Sem isto o
    # has_permission(Role("admin")) lançava ValueError → 403. Normaliza os aliases
    # de admin para o valor canónico (string, p/ não importar rbac aqui → circular).
    role = x_user_role or "viewer"
    if role in _ADMIN_ROLES:
        role = "admin_platform"
    return UserContext(
        user_id=x_user_id,
        tenant_id=x_tenant_id,
        role=role,
    )


class AdminContext:
    """Minimal admin context returned by :func:`require_admin`.

    Carries enough identity to write an audit log row without forcing
    callers to chain three separate header dependencies. Always carries
    a ``role`` string in :data:`_ADMIN_ROLES`.
    """

    __slots__ = ("role", "source", "user_id")

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


def dev_only() -> None:
    """Dependency que dá 404 quando ``settings.environment == "production"``.

    Sprint Q.12 Onda 0.5 — os endpoints ``/*-dev`` (sem auth, tenant fixo)
    eram alcançáveis em qualquer ambiente. Q.168.D — promovido de
    ``src/copilot/routers/_common.py`` para shared: o gate é transversal
    (profit/copilot/...) e o teste de cobertura de rotas
    (test_tenant_route_coverage_q168d) reconhece-o pelo nome.
    """
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )
