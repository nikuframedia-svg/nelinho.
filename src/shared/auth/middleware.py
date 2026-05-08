"""RBAC enforcement middleware (Sprint Q.18.A.2).

Why this exists
---------------
``rbac.ROUTE_PREFIX_REQUIREMENTS`` defines the canonical mapping
``path prefix → required permissions``, and ``requirements_for_route``
already knows how to resolve "longest prefix wins". But before this
sprint nobody actually called those helpers from the request path —
the matrix was a documentation artifact + a unit-test fixture.
Endpoints had to declare ``Depends(require_permission(...))`` per
route, and ~88% of mutations didn't.

This middleware closes that gap: every request that hits a path with
a matrix entry must carry a role with at least one of the required
permissions, or the request is rejected at the edge.

Rollout posture
---------------
Strict enforcement is gated by ``settings.rbac_strict`` (off by
default) so it can be flipped per-environment. ``main.py`` activates
it unconditionally when ``settings.environment == "production"`` —
production is fail-closed, dev is fail-open with the matrix still
honoured for tests that opt in via monkeypatch.

Non-enforcement paths
---------------------
Health, metrics, OpenAPI docs, and ``OPTIONS`` preflights bypass the
gate. Routes without a matrix entry fall through (gradual rollout
posture — adding a new router doesn't accidentally lock everyone out).
"""
from __future__ import annotations

import logging
from typing import Iterable

from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.shared.auth.jwt_handler import verify_token
from src.shared.auth.rbac import (
    has_any_permission,
    requirements_for_route,
)
from src.shared.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bypass rules
# ---------------------------------------------------------------------------

#: Exact path matches that never require auth (health, metrics, docs, …).
_BYPASS_EXACT: frozenset[str] = frozenset({
    "/",
    "/health",
    "/healthz",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
})

#: Path prefixes that bypass the gate (auth flow itself, SSE bridge).
#: Keep this list short — anything not strictly self-serve must enforce.
_BYPASS_PREFIXES: tuple[str, ...] = (
    "/v1/auth/",            # login / refresh — chicken-and-egg
    "/v1/realtime/events",  # SSE: handles auth via query token
    "/static/",
    "/assets/",
    "/docs/",               # swagger sub-resources
)


def _is_bypassed(path: str) -> bool:
    if path in _BYPASS_EXACT:
        return True
    return any(path.startswith(p) for p in _BYPASS_PREFIXES)


# ---------------------------------------------------------------------------
# Role resolution (mirror :mod:`headers` so behaviour stays consistent)
# ---------------------------------------------------------------------------

def _resolve_role(request: Request) -> tuple[str | None, str]:
    """Resolve the requester's role.

    Returns ``(role, source)`` where ``source`` is one of ``"jwt"``,
    ``"legacy_header"`` or ``"none"``. Any failure (malformed token,
    expired, missing) returns ``(None, "none")`` — the caller decides
    how to respond.

    JWT wins over legacy headers; legacy headers are only honoured
    outside production. This mirrors :func:`require_admin` so an admin
    JWT and an ``X-User-Role: admin_platform`` header behave the same
    way against the gate.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    scheme, token = get_authorization_scheme_param(auth) if auth else ("", "")
    if scheme.lower() == "bearer" and token:
        try:
            payload = verify_token(token, "access")
        except Exception:  # noqa: BLE001 — invalid/expired token
            return None, "none"
        return payload.role, "jwt"

    if settings.environment == "production":
        return None, "none"

    legacy = request.headers.get("x-user-role") or request.headers.get("X-User-Role")
    if legacy:
        return legacy.strip(), "legacy_header"
    return None, "none"


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RBACMiddleware(BaseHTTPMiddleware):
    """Apply :data:`ROUTE_PREFIX_REQUIREMENTS` to every request.

    ``main.py`` is the single registration site. Tests build their own
    app with ``app.add_middleware(RBACMiddleware)`` so each test asserts
    what it intends to.
    """

    def __init__(self, app: ASGIApp, *, bypass_paths: Iterable[str] | None = None) -> None:
        super().__init__(app)
        # Optional extra bypass set, useful for tests that want to skip a
        # specific health-check path that isn't already in the defaults.
        self._extra_bypass: frozenset[str] = frozenset(bypass_paths or ())

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method.upper()

        # Preflight — never enforce.
        if method == "OPTIONS":
            return await call_next(request)

        if _is_bypassed(path) or path in self._extra_bypass:
            return await call_next(request)

        required = requirements_for_route(path, method)
        if required is None:
            # No matrix entry → gradual rollout: caller still has the
            # legacy per-route dependency to enforce. This middleware
            # adds a backstop, it doesn't replace per-route gates.
            return await call_next(request)

        role, source = _resolve_role(request)
        if role is None:
            logger.info("RBAC: 401 on %s %s (no auth)", method, path)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authentication required",
                    "path": path,
                },
            )

        if not has_any_permission(role, required):
            logger.info(
                "RBAC: 403 on %s %s — role=%s missing one of %s",
                method, path, role, [p.value for p in required],
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Insufficient permissions for this route",
                    "role": role,
                    "required": [p.value for p in required],
                    "auth_source": source,
                },
            )

        return await call_next(request)


__all__ = ["RBACMiddleware"]
