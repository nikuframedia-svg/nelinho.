"""Q.17.F.9 — HTTP middleware enforcing ``pause_writes`` rule actions.

When a YAML rule fires the ``pause_writes`` action, the dispatcher
registers a pause in :mod:`pause_registry`. This middleware reads that
registry on every write request and answers **423 Locked** for any
write (POST/PUT/PATCH/DELETE) whose path falls under a paused prefix.

Reads are never blocked — a pause is an emergency brake on mutations,
not a full outage. Requests without a resolvable tenant pass through
untouched; auth downstream rejects them on its own terms.
"""

from __future__ import annotations

import logging
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.governance.yaml_policy.pause_registry import is_paused

_log = logging.getLogger(__name__)

_WRITE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class PauseWritesMiddleware(BaseHTTPMiddleware):
    """Reject writes to a route prefix that a ``pause_writes`` rule paused."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in _WRITE_METHODS:
            return await call_next(request)

        raw_tenant = request.headers.get("X-Tenant-Id")
        if not raw_tenant:
            return await call_next(request)
        try:
            tenant_id = UUID(raw_tenant)
        except ValueError:
            return await call_next(request)

        pause = is_paused(tenant_id, request.url.path)
        if pause is None:
            return await call_next(request)

        _log.warning(
            "pause_writes blocked %s %s tenant=%s prefix=%s",
            request.method, request.url.path, tenant_id, pause.route_prefix,
        )
        return JSONResponse(
            status_code=423,
            content={
                "detail": pause.reason_pt or "Escritas pausadas por uma regra de governança.",
                "route_prefix": pause.route_prefix,
                "expires_at": pause.expires_at.isoformat(),
            },
        )


def register(app) -> None:
    """Attach the middleware to a FastAPI app. Imported by :mod:`src.main`."""
    app.add_middleware(PauseWritesMiddleware)


__all__ = ["PauseWritesMiddleware", "register"]
