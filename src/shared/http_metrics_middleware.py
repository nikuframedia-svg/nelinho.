"""
HTTP metrics middleware (Sprint J follow-up)
==============================================

Records ``prodplan_http_requests_total``,
``prodplan_http_request_duration_seconds`` and
``prodplan_http_requests_in_flight`` for every HTTP request handled
by the FastAPI app. Required by the alert rules in
``monitoring/prometheus/alerts.yml`` (``High5xxRate``, ``High4xxRate``).

Label budget
------------
Prometheus histograms with high label cardinality are a classic memory
leak. We deliberately label by ``path_template`` (e.g.
``/v1/plan/cpo/commits/{sha}``) NOT the concrete URL with the UUID in
it — FastAPI exposes the matched route via ``request.scope["route"]``.
When no route matched (404), we collapse to ``__unmatched__`` so we
don't multiply labels by attacker-scanned URLs.

Endpoints excluded
------------------
* ``/metrics`` itself — Prometheus scrapes this 4×/minute; recording
  it would create a feedback loop that inflates its own latency
  histogram.
* ``/v1/realtime/events`` — a long-lived SSE stream; its duration is
  the connection lifetime, not a request, and it would single-bucket
  the whole histogram.

Both exclusions are an explicit list (``_EXCLUDED_PATHS``) so edits
show up in review.
"""

from __future__ import annotations

import time
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.shared.metrics import (
    http_request_duration_seconds,
    http_requests_in_flight,
    http_requests_total,
)


_EXCLUDED_PATHS: frozenset[str] = frozenset({
    "/metrics",
    "/v1/realtime/events",
})


def _route_template(request: Request) -> str:
    """Return the FastAPI route template, collapsing unmatched paths
    into a single label value to bound cardinality.

    FastAPI attaches the resolved ``APIRoute`` (with ``path_format``)
    to ``request.scope['route']`` once routing finishes. During
    middleware dispatch that field is already populated — but we check
    defensively because exception paths may skip it.
    """
    try:
        route = request.scope.get("route")
    except Exception:
        return "__unmatched__"
    if route is None:
        return "__unmatched__"
    # FastAPI `APIRoute` exposes `.path_format` (e.g. "/v1/plan/cpo/
    # commits/{sha}"). Starlette `Route` exposes `.path`. Both are
    # stable template-level strings.
    for attr in ("path_format", "path"):
        value = getattr(route, attr, None)
        if isinstance(value, str) and value:
            return value
    return "__unmatched__"


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that emits the four HTTP metrics.

    Sits as close to the wire as possible (install it BEFORE
    application-specific middlewares) so it times the real,
    user-observed latency — including auth, DB connect, SSE setup.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _EXCLUDED_PATHS or path.startswith("/metrics/"):
            return await call_next(request)

        started = time.perf_counter()
        http_requests_in_flight.inc()
        status_code = 500  # default if the handler crashes
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # Record the request as a 500 and re-raise so the
            # framework's exception handlers can still reply.
            raise
        finally:
            elapsed = max(0.0, time.perf_counter() - started)
            template = _route_template(request)
            labels = {
                "method": request.method,
                "path_template": template,
                "status": str(status_code),
            }
            try:
                http_requests_total.labels(**labels).inc()
                http_request_duration_seconds.labels(**labels).observe(elapsed)
            except Exception:
                # Never let metrics emission fail a real request.
                pass
            http_requests_in_flight.dec()


def register(app) -> None:
    """Attach the middleware to a FastAPI app. Callers in
    :mod:`src.main` import this helper rather than the class directly
    so adding future hooks (sampling, PII stripping on paths) has one
    home."""
    app.add_middleware(HTTPMetricsMiddleware)


__all__ = ["HTTPMetricsMiddleware", "register"]
