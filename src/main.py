"""
ProdPlan ONE - Main Application
================================

FastAPI application entry point.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from src.shared.config import settings
from src.shared.database import init_db, close_db, check_db_health
from src.shared.redis_client import get_redis, shutdown_redis, check_redis_health
from src.shared.kafka_client import get_producer, shutdown_kafka, check_kafka_health

# Import API routers
from src.core.api import router as core_router
from src.core.api import tenant_config_router
from src.core.api import erp_integration_router
from src.plan.api import router as plan_router
from src.profit.api import router as profit_router
from src.hr.api import router as hr_router
from src.copilot.api import router as copilot_router
from src.legacy.api import router as legacy_router
from src.supply.api import router as supply_router
from src.shared.api import router as shared_router

# Import new module routers
from src.explain.api import router as explain_router
from src.twin.api import router as twin_router
from src.sandbox.api import router as sandbox_router
from src.improve.api import router as improve_router
from src.factory_data_product import factory_router
from src.copilot.api_endpoints.runbooks_api import router as runbooks_router
from src.copilot.api_endpoints.tools_api import router as tools_router
from src.copilot.api_endpoints.decision_pr_api import router as decision_pr_router
from src.governance.api import router as governance_router
from src.governance.api_preference_rules import router as preference_rules_router
from src.governance.api_learning_metrics import router as learning_metrics_router  # Sprint R.1
from src.workforce.api import router as workforce_router
from src.workforce.employee_extras_api import router as workforce_employees_router  # Sprint Q.3
from src.copilot.alerts.api import router as copilot_alerts_router
from src.shared.realtime.activity_api import router as activity_router
from src.shared.scheduler import start_scheduler, shutdown_scheduler
from src.plan.api.cpo import router as plan_cpo_router
from src.ml.api import router as ml_router
from src.copilot.poetiq import router as copilot_poetiq_router

# Configure logging first
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import DQA middleware (optional - can be disabled via settings)
try:
    from src.dqa.quality_gates import QualityGateMiddleware
    DQA_ENABLED = True
except ImportError:
    DQA_ENABLED = False
    logger.warning("DQA module not available - quality gates disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting ProdPlan ONE...")

    # Sprint Q.13.B (B1) — OpenTelemetry tracing setup. No-op when
    # OTEL_TRACES_EXPORTER is unset OR opentelemetry packages aren't
    # installed; logs the outcome either way. Must run BEFORE the rest
    # of startup so the auto-instrumentor catches subsequent
    # FastAPI route registration + DB connections.
    try:
        from src.shared.tracing import setup_tracing
        setup_tracing(app)
    except Exception as tracing_error:
        logger.warning(f"OTel setup failed: {tracing_error}")

    # Sprint Q.13.F F.4 — Sentry error reporting. Same graceful no-op
    # contract as tracing: when SENTRY_DSN is unset OR sentry-sdk
    # isn't installed, the call returns False and nothing is reported.
    # Pairs with OTel: tracing answers "where slowed", Sentry answers
    # "what raised, who, how often, with which release".
    try:
        from src.shared.error_reporting import setup_error_reporting
        setup_error_reporting()
    except Exception as sentry_error:
        logger.warning(f"Sentry setup failed: {sentry_error}")
    
    try:
        # Initialize database (opcional - permite iniciar sem DB para testes)
        try:
            await init_db()
            logger.info("Database initialized")
        except Exception as db_error:
            logger.warning(f"Database connection failed: {db_error}")
            logger.warning("Backend iniciado SEM base de dados. Algumas funcionalidades estarão limitadas.")
            logger.warning("Para usar o COPILOT completo, inicia o PostgreSQL.")
        
        # Initialize Redis (opcional)
        try:
            await get_redis()
            logger.info("Redis connected")
        except Exception as redis_error:
            logger.warning(f"Redis connection failed: {redis_error}")
            logger.warning("Backend iniciado SEM Redis. Rate limiting usará fallback em memória.")
        
        # Initialize Kafka producer (opcional)
        if not settings.is_development:
            try:
                await get_producer()
                logger.info("Kafka producer started")
            except Exception as kafka_error:
                logger.warning(f"Kafka connection failed: {kafka_error}")

        # Pre-warm the Copilot tool registry so the first /v1/tools call
        # doesn't incur an OpenAPI parse round-trip.
        # Q.33.B.1 — feed the app's own `app.openapi()` spec in-process.
        # The old no-arg call fetched `http://localhost:8000/openapi.json`
        # (wrong port) → 0 tools → the agentic loop never engaged.
        try:
            from src.copilot.tool_registry import get_tool_registry
            registry = await get_tool_registry(openapi_spec=app.openapi())
            logger.info(f"Tool registry pre-warmed: {len(registry.tools)} tools")
        except Exception as tr_error:
            logger.warning(f"Tool registry pre-warm failed: {tr_error}")

        # Q.37.D — regista os handlers reais das acções do copiloto
        # (inventário + scheduling). Sem isto, EXECUTE/SANDBOX de uma
        # acção CPO/inventário devolve 501. Idempotente (overwrite).
        try:
            from src.copilot.action_handlers import register_all_action_handlers
            _n_handlers = register_all_action_handlers()
            logger.info(f"Copilot action handlers registados: {_n_handlers}")
        except Exception as handler_error:
            logger.warning(f"Action handler registration failed: {handler_error}")

        # Q.17.D — load active YAML policy rules into the runtime engine
        # so they start firing on the first matching event without a
        # cold-start refresh. Best-effort: failure here doesn't block
        # startup (engine stays empty; rules can still be approved).
        try:
            from src.governance.yaml_policy.runtime import startup_refresh
            from src.shared.database import async_session_factory
            async with async_session_factory() as _session:
                _count = await startup_refresh(_session)
            logger.info(f"YAML policy engine warmed: {_count} active rules")
        except Exception as engine_error:
            logger.warning(f"YAML policy engine warmup failed: {engine_error}")

        # Start background scheduler (alerts scan + daily feedback).
        # In production, list active tenants here from the DB; for dev we start
        # empty and endpoints can register tenants via register_tenant().
        scheduler_instance = None
        try:
            scheduler_instance = start_scheduler(tenants=None)
        except Exception as sched_error:
            logger.warning(f"Scheduler failed to start: {sched_error}")

        # Factory data watcher — no-op unless PRODPLAN_FACTORY_FILE is set
        if scheduler_instance is not None:
            try:
                from src.factory_data_product.watcher import register_with_scheduler
                register_with_scheduler(scheduler_instance)
            except Exception as watcher_error:
                logger.warning(f"Factory watcher registration failed: {watcher_error}")

            # ML retrain jobs — load active tenant ids from DB so retrain
            # jobs actually run in production (FASE 0.1, DEVA-03).
            try:
                from src.ml.jobs.scheduling import register_ml_retrain_jobs
                from src.shared.database import get_session_context
                from src.core.services.tenant_service import TenantService
                from src.core.models.tenant import TenantStatus

                active_tenant_ids: list = []
                try:
                    async with get_session_context() as ml_session:
                        ts = TenantService(ml_session)
                        active = await ts.list_tenants(status=TenantStatus.ACTIVE, limit=1000)
                        active_tenant_ids = [t.id for t in active]
                except Exception as tenant_lookup_error:
                    logger.warning(
                        "ML retrain: could not load active tenants (%s) — jobs stay dormant",
                        tenant_lookup_error,
                    )
                register_ml_retrain_jobs(scheduler_instance, tenants=active_tenant_ids)

                # Q.32.C.4 — registar os jobs por-tenant (alerts scan +
                # Camadas 1-3 de aprendizagem). Sem este loop o scheduler
                # arrancava com "0 tenant(s)" e os jobs nocturnos
                # (preference_rule_detector, preference_weights_retrain,
                # dpo_finetune, abl_feedback) nunca corriam.
                from src.shared.scheduler import register_tenant

                registered = 0
                for tid in active_tenant_ids:
                    try:
                        register_tenant(tid)
                        registered += 1
                    except Exception as reg_error:
                        logger.warning(
                            "register_tenant(%s) failed: %s", tid, reg_error,
                        )
                logger.info(
                    "Scheduler: per-tenant jobs registered for %d/%d active tenant(s)",
                    registered, len(active_tenant_ids),
                )
            except Exception as ml_error:
                logger.warning(f"ML retrain job registration failed: {ml_error}")

        # Sprint D.1 — Realtime bridge (Kafka → SSE fan-out).
        # Graceful when Kafka is unavailable: bridge logs + stays unhealthy
        # so the /v1/realtime/events endpoint answers 503 instead of hanging.
        try:
            from src.shared.realtime import RealtimeBridge
            await RealtimeBridge.instance().start()
        except Exception as bridge_error:
            logger.warning(f"RealtimeBridge failed to start: {bridge_error}")

        # Sprint Q.14.B — Postgres LISTEN/NOTIFY listener for the
        # rule_firing channel. Pushes high-severity firings to SSE
        # within ~5ms. Same graceful contract as the bridge: if asyncpg
        # / Postgres is unreachable, push channel stays silent + Kafka
        # events still flow.
        try:
            from src.shared.realtime.notify_listener import start_notify_listener
            await start_notify_listener()
        except Exception as notify_error:
            logger.warning(f"NOTIFY listener failed to start: {notify_error}")

        logger.info("ProdPlan ONE started successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Não fazer raise - permite iniciar mesmo com erros parciais
        logger.warning("Continuando com funcionalidades limitadas...")

    yield

    # Shutdown
    # Sprint Q.13.B (B5) — graceful shutdown contract.
    #
    # Was: shutdown ran sequentially with no upper bound. A hung Kafka
    # producer or stalled DB connection could keep the process alive
    # past systemd's TimeoutStopSec, leading to SIGKILL (which loses
    # in-flight outbox events).
    #
    # Now:
    #   1. Wraps the whole shutdown in `asyncio.wait_for(..., 30.0)`
    #      so systemd's 60s grace is comfortably honoured.
    #   2. Drains the outbox dispatcher ONCE before Kafka closes so
    #      pending DECISION_EXECUTED / SCHEDULE_CREATED events that
    #      land in the last second don't get stuck in the DB.
    #   3. Each subsystem teardown is in its own try/except — one
    #      failure (e.g. Redis already gone) never blocks the rest.
    logger.info("Shutting down ProdPlan ONE...")

    async def _shutdown_sequence() -> None:
        # Stop realtime bridge first — subscribers get a clean "None"
        # sentinel before the Kafka producer/consumer teardown races in.
        try:
            from src.shared.realtime import RealtimeBridge
            await RealtimeBridge.instance().stop()
        except Exception as bridge_error:
            logger.warning(f"RealtimeBridge shutdown failed: {bridge_error}")

        # Sprint Q.14.B — close the asyncpg LISTEN connection cleanly
        # so Postgres releases the backend slot.
        try:
            from src.shared.realtime.notify_listener import stop_notify_listener
            await stop_notify_listener()
        except Exception as notify_error:
            logger.warning(f"NOTIFY listener shutdown failed: {notify_error}")

        # Sprint Q.13.B B5 — final outbox drain. Best effort: when
        # Kafka or the DB is already wedged this just logs and moves
        # on. The existing periodic dispatcher would have caught
        # these on next boot anyway via the table; this just shortens
        # the visibility window.
        try:
            from src.shared.kafka_client import get_producer
            from src.shared.outbox_dispatcher import OutboxDispatcher
            from src.shared.database import get_session_context
            producer = await get_producer()
            if producer is not None:
                dispatcher = OutboxDispatcher(
                    db_session_factory=get_session_context,
                    kafka_producer=producer,
                )
                await dispatcher.run()
                logger.info("Outbox final drain ok")
        except Exception as outbox_error:
            logger.warning(f"Outbox final drain failed: {outbox_error}")

        try:
            await shutdown_scheduler()
        except Exception as sched_error:
            logger.warning(f"Scheduler shutdown failed: {sched_error}")

        try:
            await close_db()
        except Exception as db_error:
            logger.warning(f"DB shutdown failed: {db_error}")

        try:
            await shutdown_redis()
        except Exception as redis_error:
            logger.warning(f"Redis shutdown failed: {redis_error}")

        try:
            await shutdown_kafka()
        except Exception as kafka_error:
            logger.warning(f"Kafka shutdown failed: {kafka_error}")

        # Sprint Q.13.B (B1) — flush OTel spans LAST so the trace for
        # this very shutdown sequence makes it to the collector before
        # the process exits. No-op when tracing wasn't active.
        try:
            from src.shared.tracing import shutdown_tracing
            shutdown_tracing()
        except Exception as tracing_error:
            logger.warning(f"OTel flush failed: {tracing_error}")

    try:
        await asyncio.wait_for(_shutdown_sequence(), timeout=30.0)
        logger.info("ProdPlan ONE shut down cleanly")
    except asyncio.TimeoutError:
        logger.error(
            "Shutdown exceeded 30s grace period — systemd will SIGKILL. "
            "Some pending events may not have flushed; check outbox table "
            "on next boot."
        )


# Create FastAPI app
app = FastAPI(
    title="ProdPlan ONE",
    description="Industrial ERP - Planning, Costing, HR Management",
    version="1.0.0",
    lifespan=lifespan,
)

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
if DQA_ENABLED and not settings.is_development:
    app.add_middleware(QualityGateMiddleware)
    logger.info("DQA Quality Gates middleware enabled")

# Sprint J follow-up — HTTP request metrics. Installs the Counter +
# Histogram that alerts.yml gates on (High5xxRate, High4xxRate).
from src.shared.http_metrics_middleware import register as _register_http_metrics
_register_http_metrics(app)

# Q.17.F.9 — enforce pause_writes rule actions: write requests to a
# paused route prefix get 423 Locked.
from src.governance.yaml_policy.pause_writes_middleware import register as _register_pause_writes
_register_pause_writes(app)


# Sprint Q.12 — normalize Pydantic 422 errors to a single readable string
# so the frontend's `getErrorMessage(detail)` can show it directly. Antes
# o `detail` vinha como lista `[{loc, msg, type}]` que o frontend
# renderizava como "[object Object]".
from fastapi.exceptions import RequestValidationError


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
    if "connection refused" in error_str or "operationalerror" in error_str or "interfaceerror" in error_str:
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


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": "prodplan-one"}


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check.
    
    Verifies all dependencies are available.
    """
    checks = {
        "database": await check_db_health(),
        "redis": await check_redis_health(),
    }
    
    if not settings.is_development:
        checks["kafka"] = await check_kafka_health()
    
    all_healthy = all(checks.values())
    
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if all_healthy else "not ready",
            "checks": checks,
        },
    )


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """Liveness check."""
    return {"status": "alive"}


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Exposes metrics for scraping by Prometheus.
    """
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from src.shared.metrics import registry
    
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


# Include routers
app.include_router(core_router)
app.include_router(tenant_config_router)  # Sprint L.3 — /v1/config/*
app.include_router(erp_integration_router)  # Q.44.Z — /v1/erp-integration

# Sprint AA.4 — Trust Index v2.0 endpoint
from src.dqa.api import router as dqa_router
app.include_router(dqa_router)

# Sprint Q.7 Fase 1 — Diagnostics dashboard (per-module health + infra pings)
from src.diagnostics import router as diagnostics_router
app.include_router(diagnostics_router)

# Sprint N — Factory Map
from src.factory_data_product.api.factory_map import router as factory_map_router
app.include_router(factory_map_router)

# Sprint R — Quality
from src.quality.api import router as quality_router
app.include_router(quality_router)
app.include_router(plan_router)
app.include_router(profit_router)
app.include_router(hr_router)
app.include_router(copilot_router)
app.include_router(supply_router)  # Supply Chain Planning module
app.include_router(shared_router)  # Shared/Governance APIs (Decision Ledger)
app.include_router(legacy_router)  # Legacy endpoints for compatibility

# New module routers
app.include_router(explain_router)  # Explainability API
app.include_router(twin_router)     # Digital Twin API
app.include_router(sandbox_router)  # Sandbox API
app.include_router(improve_router)  # Improvement Suggestions API
app.include_router(factory_router)  # Factory Data Product API (C10)
app.include_router(runbooks_router) # Runbooks API (P2 Enterprise)
app.include_router(tools_router)    # Tool Registry API (P2 Enterprise)
app.include_router(decision_pr_router)  # Q.37.C — ciclo de vida dos Decision PRs
app.include_router(governance_router)  # Governance API (Approvals, SoD)
app.include_router(preference_rules_router)  # Sprint E.3 — learned rules review
app.include_router(learning_metrics_router)  # Sprint R.1 — learning visibility (pairs/rules/weights)
app.include_router(workforce_router)   # Workforce Operations API (NEW)
app.include_router(workforce_employees_router)  # Sprint Q.3 — Employees extras (quality-score, skills, history)
app.include_router(copilot_alerts_router)  # Proactive alerts (Sprint C — Fase 5)
app.include_router(plan_cpo_router)  # CPO v4 scheduler (Sprint E — DRCFFS-R)

# Sprint Q.18.UI.A.1 — minimal /v1/auth/me for the Sidebar user chip.
from src.shared.api.auth_me import router as auth_me_router
app.include_router(auth_me_router)

# Q.31.G — login real por password (POST /v1/auth/login + /refresh).
from src.shared.api.auth_login import router as auth_login_router
app.include_router(auth_login_router)

# Q.31.F — pesquisa global (GET /v1/search).
from src.search.api import router as search_router
app.include_router(search_router)

# Sprint Q.18.ZIP.BE.4 — POST /v1/reports/generate dispatcher.
from src.reports.api import router as reports_router
app.include_router(reports_router)

# Sprint D.1 — Real-time SSE fan-out of Kafka events to the browser.
from src.shared.realtime import router as realtime_router
app.include_router(realtime_router)
app.include_router(activity_router)  # /v1/activity/recent — outbox poll for LiveActivityFeed
app.include_router(ml_router)  # ML learning infrastructure (Sprint G)
app.include_router(copilot_poetiq_router)  # POETIQ copilot↔CPO loop (Sprint K.4)


# API info
@app.get("/", tags=["Info"])
async def root():
    """API information."""
    return {
        "name": "ProdPlan ONE",
        "version": "1.0.0",
        "modules": ["CORE", "PLAN", "PROFIT", "HR", "COPILOT", "FACTORY", "TWIN", "SANDBOX", "IMPROVE", "EXPLAIN", "WORKFORCE"],
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )

