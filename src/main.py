"""
ProdPlan ONE - Main Application
================================

FastAPI application entry point.

Q.67.6.C2 (Fase 8 — god-file decomposition): main.py é uma façade fina.
A lógica de startup/shutdown vive em `src/app/startup.py`, a registação
de routers em `src/app/routers_registry.py` e a stack de middleware +
exception handlers em `src/app/middleware_registry.py`. Aqui só ficam:

  - logging baseline
  - instanciação do `FastAPI(...)` com lifespan
  - chamadas a `register_middleware(app)` + `register_routers(app)`
  - endpoints triviais (/, /health/*, /metrics) — tied to the app object
  - `if __name__ == "__main__"` uvicorn fallback
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, Response

from src.app.lifespan import lifespan
from src.app.middleware_registry import (
    TenantContextMiddleware,  # re-exported (Q.62.B.2; tests import from src.main)
    register_middleware,
)
from src.app.routers_registry import register_routers
from src.shared.config import settings
from src.shared.database import check_db_health
from src.shared.kafka_client import check_kafka_health
from src.shared.redis_client import check_redis_health

# Configure logging first
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="ProdPlan ONE",
    description="Industrial ERP - Planning, Costing, HR Management",
    version="1.0.0",
    lifespan=lifespan,
)

# Order matters: middleware first (LIFO at request time → trace_id runs
# first on the way OUT so headers echo even on error responses), then
# routers. Health/metrics/root endpoints below sit directly on `app`.
register_middleware(app)
register_routers(app)


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
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    from src.shared.metrics import registry

    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


# API info
@app.get("/", tags=["Info"])
async def root():
    """API information."""
    return {
        "name": "ProdPlan ONE",
        "version": "1.0.0",
        "modules": [
            "CORE",
            "PLAN",
            "PROFIT",
            "HR",
            "COPILOT",
            "FACTORY",
            "TWIN",
            "SANDBOX",
            "IMPROVE",
            "EXPLAIN",
            "WORKFORCE",
        ],
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
