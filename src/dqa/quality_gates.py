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


# Endpoints gated by factory-scope Trust Index. Only POST/PUT/PATCH on these
# paths trigger the check — reads are always allowed regardless of TI.
DEFAULT_GATED_ENDPOINTS: frozenset[str] = frozenset({
    "/v1/plan/replan",
    "/v1/plan/commit",
    "/v1/supply/forecast",
})

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
        gate: TrustGate = TrustGate.AUTO_COMMIT,
    ) -> None:
        super().__init__(app)
        self._gated_endpoints = gated_endpoints or DEFAULT_GATED_ENDPOINTS
        self._gate = gate

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path not in self._gated_endpoints:
            return await call_next(request)
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        tenant_raw = request.headers.get(TENANT_HEADER)
        if not tenant_raw:
            # No tenant context → let the route handler reject; we don't gate.
            return await call_next(request)

        try:
            tenant_id = UUID(tenant_raw)
        except ValueError:
            logger.warning("Quality gate: invalid X-Tenant-Id %r", tenant_raw)
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
            # Never block on TI evaluation failure — better to allow than to
            # break prod when the DQA stack is itself unhealthy.
            logger.error("Quality gate evaluation failed: %s", exc, exc_info=True)
            return await call_next(request)

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
