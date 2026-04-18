"""
ProdPlan ONE - Main Application
================================

FastAPI application entry point.
"""

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
from src.governance.api import router as governance_router
from src.workforce.api import router as workforce_router
from src.copilot.alerts.api import router as copilot_alerts_router
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
            redis = await get_redis()
            logger.info("Redis connected")
        except Exception as redis_error:
            logger.warning(f"Redis connection failed: {redis_error}")
            logger.warning("Backend iniciado SEM Redis. Rate limiting usará fallback em memória.")
        
        # Initialize Kafka producer (opcional)
        if not settings.is_development:
            try:
                producer = await get_producer()
                logger.info("Kafka producer started")
            except Exception as kafka_error:
                logger.warning(f"Kafka connection failed: {kafka_error}")

        # Pre-warm the Copilot tool registry so the first /v1/tools call
        # doesn't incur an OpenAPI parse round-trip.
        try:
            from src.copilot.tool_registry import get_tool_registry
            await get_tool_registry()
            logger.info("Tool registry pre-warmed")
        except Exception as tr_error:
            logger.warning(f"Tool registry pre-warm failed: {tr_error}")

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

            # ML retrain jobs — no-op until active tenants are registered.
            # In production, call register_ml_retrain_jobs(scheduler, tenant_ids)
            # after the tenant list is resolved from the DB.
            try:
                from src.ml.jobs.scheduling import register_ml_retrain_jobs
                register_ml_retrain_jobs(scheduler_instance, tenants=None)
            except Exception as ml_error:
                logger.warning(f"ML retrain job registration failed: {ml_error}")

        logger.info("ProdPlan ONE started successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Não fazer raise - permite iniciar mesmo com erros parciais
        logger.warning("Continuando com funcionalidades limitadas...")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ProdPlan ONE...")
    
    await shutdown_scheduler()
    await close_db()
    await shutdown_redis()
    await shutdown_kafka()

    logger.info("ProdPlan ONE shut down")


# Create FastAPI app
app = FastAPI(
    title="ProdPlan ONE",
    description="Industrial ERP - Planning, Costing, HR Management",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DQA Quality Gates middleware (optional)
if DQA_ENABLED and not settings.is_development:
    app.add_middleware(QualityGateMiddleware)
    logger.info("DQA Quality Gates middleware enabled")


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
    # Skip DB connection errors (handled above)
    if isinstance(exc, (ConnectionRefusedError,)):
        raise
    
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

# Sprint AA.4 — Trust Index v2.0 endpoint
from src.dqa.api import router as dqa_router  # noqa: E402
app.include_router(dqa_router)

# Sprint N — Factory Map
from src.factory_data_product.api.factory_map import router as factory_map_router  # noqa: E402
app.include_router(factory_map_router)
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
app.include_router(governance_router)  # Governance API (Approvals, SoD)
app.include_router(workforce_router)   # Workforce Operations API (NEW)
app.include_router(copilot_alerts_router)  # Proactive alerts (Sprint C — Fase 5)
app.include_router(plan_cpo_router)  # CPO v4 scheduler (Sprint E — DRCFFS-R)
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

