"""
ProdPlan ONE - Quality Gates Middleware (Sprint Q.1 — Trust Index v2)
=====================================================================

FastAPI middleware that enforces the factory-scope Trust Index gate on
commit-class endpoints. Below the configured `AUTO_COMMIT` threshold
(default 0.75 from `tenant_configuration.trust.gates.auto_commit`), the
middleware returns 422 with the failing components so the caller can see
what's wrong.

Migrated from v1 (request-shape based, 4 components, hardcoded 0.70) to v2
(factory-state based, 7 components, gate-configurable). Aligned with
Blueprint v2.0 §4.5.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional
from uuid import UUID

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.dqa.trust_gates import (
    TrustGate,
    gate_allows,
    load_gate_config,
)
from src.dqa.trust_signals import curated_signals_provider
from src.dqa.trust_v2 import (
    SCOPE_FACTORY,
    TrustIndexV2Calculator,
)
from src.shared.database import async_session_factory

logger = logging.getLogger(__name__)


# Exact-match paths gated by factory-scope Trust Index. POST/PUT/PATCH/
# DELETE on these paths must clear the AUTO_COMMIT gate.
DEFAULT_GATED_ENDPOINTS: frozenset[str] = frozenset({
    "/v1/plan/replan",
    "/v1/plan/commit",
    "/v1/supply/forecast",
})

# Sprint Q.9 Onda 2.4 — prefix-match paths gated by Trust Index. Plan v4
# §15 requires any commit-class route to clear the gate (TI ≥ 0.75 by
# default). Listing whole API surfaces by prefix keeps the rule
# resilient to new endpoint additions inside these surfaces. Only
# POST/PUT/PATCH/DELETE on these prefixes trigger the check; GET stays
# free.
DEFAULT_GATED_PREFIXES: tuple[str, ...] = (
    "/v1/plan/cpo/",          # CPO schedule/decide — high-impact writes
    "/v1/decisions/",         # decision ledger — every approval/rejection
    "/v1/transport/",         # transport batch mutations
    "/v1/plan/schedule/",     # apply-move, preview-delta-apply
    "/v1/governance/learning/adapter/",  # DPO adapter promotion
)

# Header that carries the active tenant. Matches the convention used by
# `src.shared.database.get_session` and the rest of the API.
TENANT_HEADER = "X-Tenant-Id"


class QualityGateMiddleware(BaseHTTPMiddleware):
    """Enforce the AUTO_COMMIT trust gate on commit-class endpoints.

    The v2 Trust Index is computed for `scope=factory` (global state); below
    the configured threshold the middleware returns 422 with the failing
    components so the caller can fix the underlying data.
    """

    def __init__(
        self,
        app,
        gated_endpoints: Optional[frozenset[str]] = None,
        gated_prefixes: Optional[tuple[str, ...]] = None,
        gate: TrustGate = TrustGate.AUTO_COMMIT,
    ) -> None:
        super().__init__(app)
        self._gated_endpoints = gated_endpoints or DEFAULT_GATED_ENDPOINTS
        self._gated_prefixes = (
            gated_prefixes if gated_prefixes is not None
            else DEFAULT_GATED_PREFIXES
        )
        self._gate = gate

    def _is_gated(self, path: str) -> bool:
        if path in self._gated_endpoints:
            return True
        return any(path.startswith(p) for p in self._gated_prefixes)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Sprint Q.9 Onda 2.4 — gate by exact match OR prefix match on
        # known commit-class API surfaces. Reads (GET/HEAD/OPTIONS) and
        # the tenant-config endpoints (which set the gates themselves)
        # are always allowed.
        if not self._is_gated(request.url.path):
            return await call_next(request)
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        tenant_raw = request.headers.get(TENANT_HEADER)
        if not tenant_raw:
            # No tenant context → log and let the route handler reject.
            # The handler's own `Depends(get_tenant_id)` will return 422,
            # so this isn't a bypass — but it must be visible in logs.
            logger.warning(
                "Quality gate: %s %s without %s header — gate skipped, "
                "route handler will reject",
                request.method, request.url.path, TENANT_HEADER,
            )
            return await call_next(request)

        try:
            tenant_id = UUID(tenant_raw)
        except ValueError:
            logger.warning(
                "Quality gate: invalid X-Tenant-Id %r on %s %s — gate "
                "skipped, route handler will reject",
                tenant_raw, request.method, request.url.path,
            )
            return await call_next(request)

        try:
            async with async_session_factory() as session:
                calc = TrustIndexV2Calculator(
                    session,
                    tenant_id,
                    signals_provider=curated_signals_provider,
                )
                result = await calc.compute_for_scope(SCOPE_FACTORY)
                gate_cfg = await load_gate_config(session, tenant_id)
        except Exception as exc:
            # Fail-closed (Sprint Onda 1.2). When the DQA stack is unable to
            # evaluate the Trust Index we MUST NOT silently approve the
            # commit-class request — that's the exact scenario the gate
            # exists to prevent. 503 surfaces the dependency outage; the
            # caller can retry once the stack recovers.
            logger.error("Quality gate evaluation failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "dqa_unavailable",
                    "message": (
                        "Trust Index could not be evaluated; quality gate "
                        "blocked the request to avoid an unverified commit. "
                        "Check the DQA stack (DB, tenant config) and retry."
                    ),
                },
            )

        if not gate_allows(result.composite, self._gate, gate_cfg):
            threshold = gate_cfg.get(self._gate)
            logger.warning(
                "Quality gate blocked %s %s: TI=%.3f < %.2f (gate=%s)",
                request.method, request.url.path,
                result.composite, threshold, self._gate.value,
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "data_quality_insufficient",
                    "trust_index": round(result.composite, 4),
                    "gate": self._gate.value,
                    "threshold": threshold,
                    "components": {
                        k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in result.components.as_dict().items()
                    },
                    "suggestion": (
                        "Factory data quality is below the configured gate. "
                        "Call GET /v1/dqa/trust-index?scope=factory to see "
                        "which components are failing and resolve before "
                        "retrying."
                    ),
                },
            )

        # Pass the TI through for downstream handlers that want to consume it
        # (e.g. ScheduleCommit.trust_index pre-fill).
        request.state.trust_index = result.composite
        request.state.trust_components = result.components.as_dict()
        return await call_next(request)
