"""src/app/middleware_registry.py — middleware + exception handlers (Q.67.6.C2).

Order is load-bearing — FastAPI/Starlette executes middleware in reverse
registration order (LIFO). The legacy `src/main.py` ordering is preserved
verbatim:

  1. TraceIdMiddleware     (Q.61.12) — runs first on the way out so the
                            X-Request-Id echo header reaches the client
                            even on error responses (before CORS).
  2. TenantContextMiddleware (Q.62.B.2) — sets ContextVar for the engine
                            `begin` listener that emits `SET LOCAL
                            app.tenant_id` for RLS.
  3. CORSMiddleware        — explicit method + header allowlist (no wildcards
                            with credentials, per the CORS spec).
  4. RBACMiddleware        (conditional: rbac_strict or production)
  5. QualityGateMiddleware (conditional: DQA enabled + not dev)
  6. HTTP request metrics  (Sprint J follow-up)
  7. pause_writes middleware (Q.17.F.9)

Exception handlers cover RequestValidationError (flatten 422 detail to a
single string the frontend can render directly), ConnectionRefusedError
(map DB connect failures to 503 + CORS echo), and a global catch-all
that also detects asyncpg/SQLAlchemy connection errors via string match.
"""
from __future__ import annotations

import logging
from uuid import UUID as _UUID

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.auth.tenant_context import reset_tenant_id, set_tenant_id
from src.shared.config import settings
from src.shared.observability import TraceIdMiddleware

logger = logging.getLogger(__name__)


# Q.62.B.2 — Tenant context middleware.
# Extrai X-Tenant-Id (ou JWT.tenant_id) e poe em ContextVar para que o
# event listener "begin" da engine (src/shared/database.py) injecte
# `SET LOCAL app.tenant_id` em cada transacao. As policies RLS da
# migration 056_q62_b_rls_enable filtram queries automaticamente.
#
# Background tasks (scheduler, ETL) que nao passam pelo middleware
# devem chamar `tenant_scope(uuid)` explicitamente antes de queries.
class TenantContextMiddleware(BaseHTTPMiddleware):
    """Q.62.B.2 — set ContextVar `current_tenant_id_var` por request.

    Reuse a logica de extraccao do `require_tenant_header` em
    `src/shared/auth/headers.py` (Q.12 Onda 0.1 fail-closed). Se o
    header é valido (non-zero UUID), set; senao deixa None (RLS bloqueia).
    Endpoints que precisam de tenant continuam a chamar
    `require_tenant_header` como Depends e isso valida o gate (401 se
    falta). Aqui nao falhamos — middleware é best-effort.
    """

    async def dispatch(self, request, call_next):
        # JWT primeiro (Q.12 Onda 0.1 order), depois header fallback.
        tid_uuid = None
        try:
            from src.shared.auth.headers import _try_jwt  # type: ignore

            payload = _try_jwt(request)
            if payload is not None:
                try:
                    tid_uuid = _UUID(payload.tenant_id)
                except (ValueError, TypeError):
                    tid_uuid = None
        except Exception:
            tid_uuid = None  # JWT decode falhou — fica para require_tenant_header.

        if tid_uuid is None:
            header = request.headers.get("x-tenant-id") or request.headers.get("X-Tenant-Id")
            if header:
                try:
                    candidate = _UUID(header)
                    if candidate != _UUID("00000000-0000-0000-0000-000000000000"):
                        tid_uuid = candidate
                except (ValueError, TypeError):
                    tid_uuid = None

        token = set_tenant_id(tid_uuid)
        try:
            return await call_next(request)
        finally:
            reset_tenant_id(token)


def register_middleware(app: FastAPI) -> None:
    """Register every middleware on the app in the legacy order."""
    # Q.61.12 — trace_id end-to-end. Extrai X-Request-Id (ou gera UUID),
    # mete em ContextVar; call-sites lem via `get_trace_id()`. Ecoa no
    # response header para o cliente correlacionar com network logs.
    # Registado ANTES de CORS para que a echo ainda chegue em respostas
    # de erro.
    app.add_middleware(TraceIdMiddleware)

    app.add_middleware(TenantContextMiddleware)

    # CORS middleware. Sprint S6 / Φ5: was `allow_methods=["*"]` and
    # `allow_headers=["*"]` together with `allow_credentials=True`. That combo is
    # specifically forbidden by the CORS spec (browsers reject credentialed wildcard
    # preflights, and any server that allows it opens the door to credentialed
    # preflight abuse from any listed origin). Lock both lists down explicitly.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Tenant-Id",
            "X-User-Id",
            "X-User-Role",
            "X-Request-Id",
            "X-Correlation-Id",
        ],
        expose_headers=["X-Request-Id", "X-Correlation-Id"],
    )

    # Sprint Q.18.A.2 — global RBAC enforcement.
    # Off in dev so existing tests/frontend mocks keep working; production is
    # fail-closed. Flip locally with PRODPLAN_RBAC_STRICT=true to smoke-test.
    if settings.rbac_strict or settings.is_production:
        from src.shared.auth.middleware import RBACMiddleware

        app.add_middleware(RBACMiddleware)
        logger.info(
            "RBACMiddleware enabled (rbac_strict=%s, env=%s)",
            settings.rbac_strict,
            settings.environment,
        )

    # DQA Quality Gates middleware (optional)
    try:
        from src.dqa.quality_gates import QualityGateMiddleware

        dqa_available = True
    except ImportError:
        dqa_available = False
        logger.warning("DQA module not available - quality gates disabled")

    if dqa_available and not settings.is_development:
        app.add_middleware(QualityGateMiddleware)
        logger.info("DQA Quality Gates middleware enabled")

    # Sprint J follow-up — HTTP request metrics. Installs the Counter +
    # Histogram that alerts.yml gates on (High5xxRate, High4xxRate).
    from src.shared.http_metrics_middleware import register as _register_http_metrics

    _register_http_metrics(app)

    # Q.17.F.9 — enforce pause_writes rule actions: write requests to a
    # paused route prefix get 423 Locked.
    from src.governance.yaml_policy.pause_writes_middleware import (
        register as _register_pause_writes,
    )

    _register_pause_writes(app)

    _register_exception_handlers(app)


def _register_exception_handlers(app: FastAPI) -> None:
    """Validation 422 + DB 503 + global catch-all (with CORS echo on errors)."""

    # Sprint Q.12 — normalize Pydantic 422 errors to a single readable string
    # so the frontend's `getErrorMessage(detail)` can show it directly. Antes
    # o `detail` vinha como lista `[{loc, msg, type}]` que o frontend
    # renderizava como "[object Object]".
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Flatten Pydantic validation errors into `{detail: <string>, errors: [...]}`."""
        errs = exc.errors()
        parts = []
        for e in errs:
            loc = ".".join(str(x) for x in e.get("loc", []) if x not in ("body", "query"))
            msg = e.get("msg", "invalid")
            parts.append(f"{loc}: {msg}" if loc else msg)
        summary = "; ".join(parts) if parts else "validation error"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": summary, "errors": errs},
        )

    # Exception handlers
    # DB connection errors - return 503 instead of 500
    @app.exception_handler(ConnectionRefusedError)
    async def db_connection_refused_handler(request: Request, exc: ConnectionRefusedError):
        """Handle database connection refused errors."""
        logger.warning(f"DB connection refused on {request.url.path}: {exc}")
        response = JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Database service unavailable",
                "detail": "PostgreSQL connection refused. Please ensure PostgreSQL is running.",
                "path": str(request.url.path),
            },
        )
        origin = request.headers.get("origin")
        if origin and origin in settings.cors_origins_list:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        # Skip DB connection errors (handled above) — re-raise so the
        # `db_connection_refused_handler` registered earlier picks them up.
        # Was a bare `raise` which in this scope (no active except block) would
        # have raised `RuntimeError: No active exception to re-raise`.
        if isinstance(exc, (ConnectionRefusedError,)):
            raise exc

        # Check for SQLAlchemy/asyncpg DB errors
        error_str = str(exc).lower()
        if (
            "connection refused" in error_str
            or "operationalerror" in error_str
            or "interfaceerror" in error_str
        ):
            logger.warning(f"DB connection error on {request.url.path}: {exc}")
            response = JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "Database service unavailable",
                    "detail": "PostgreSQL connection error. Please ensure PostgreSQL is running.",
                    "path": str(request.url.path),
                },
            )
            origin = request.headers.get("origin")
            if origin and origin in settings.cors_origins_list:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
            return response

        logger.exception(f"Unhandled exception: {exc}")
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.debug else None,
            },
        )
        # Garantir que CORS headers são enviados mesmo em caso de erro
        origin = request.headers.get("origin")
        if origin and origin in settings.cors_origins_list:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
