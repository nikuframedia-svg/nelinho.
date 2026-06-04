"""
ProdPlan ONE - Diagnostics API (Sprint Q.7 Fase 1)
==================================================

Live audit dashboard endpoint. Powers the `/admin/health` page.

Endpoints:

  GET /v1/diagnostics/modules
        — per-module health rollup (imports, routes, tests, TODOs)
  GET /v1/diagnostics/infrastructure
        — DB, Redis, Kafka, Ollama pings
  GET /v1/diagnostics/erp-connection
        — Nelo ERP link status: masked URL, connected/offline, per-mirror
          last sync from core.etl_run, row counts, lag (Sprint Q.53.F)
  GET /v1/diagnostics/full
        — modules + infra + trust + commit cadence (the "single click"
          dashboard answer)

The endpoint is admin-only at the route layer; the data is read-only and
non-destructive.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session

from .service import (
    MODULES,
    check_database,
    check_kafka,
    check_ollama,
    check_redis,
    collect_commit_cadence,
    collect_erp_connection,
    collect_module_health,
    collect_routes_by_module,
    collect_trust_index,
)
from src.shared.auth.headers import require_tenant_header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/diagnostics", tags=["Diagnostics"])


get_tenant_id = require_tenant_header


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/modules")
async def get_modules(request: Request) -> dict[str, Any]:
    """Per-module health rollup. Cheap (~50ms) — no DB calls."""
    routes_by_module = collect_routes_by_module(request.app)
    health = collect_module_health(routes_by_module)
    rows = [m.to_dict() for m in health]
    return {
        "modules": rows,
        "summary": {
            "total": len(rows),
            "green": sum(1 for r in rows if r["health"] == "green"),
            "yellow": sum(1 for r in rows if r["health"] == "yellow"),
            "red": sum(1 for r in rows if r["health"] == "red"),
            "total_routes": sum(r["routes"] for r in rows),
            "total_import_errors": sum(r["import_error_count"] for r in rows),
            "total_todos": sum(r["todo_count"] for r in rows),
        },
        "module_catalogue": list(MODULES),
    }


@router.get("/infrastructure")
async def get_infrastructure(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Ping every infrastructure component the app depends on.

    Onda 1.6 — entire fan-out capped at 5s. Each individual check has its
    own 2s budget, but a stuck client could otherwise hold a connection
    open indefinitely; the global cap surfaces that as a clear failure.
    """
    db_check = await check_database(session)
    try:
        other = await asyncio.wait_for(
            asyncio.gather(check_redis(), check_kafka(), check_ollama()),
            timeout=5.0,
        )
        items = [db_check.to_dict()] + [c.to_dict() for c in other]
    except asyncio.TimeoutError:
        items = [
            db_check.to_dict(),
            {"component": "redis", "healthy": False, "detail": "global timeout (5s)"},
            {"component": "kafka", "healthy": False, "detail": "global timeout (5s)"},
            {"component": "ollama", "healthy": False, "detail": "global timeout (5s)"},
        ]
    return {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "summary": {
            "total": len(items),
            "healthy": sum(1 for i in items if i["healthy"]),
            "unhealthy": sum(1 for i in items if not i["healthy"]),
        },
    }


@router.get("/erp-connection")
async def get_erp_connection(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """State of the ERP NELO integration (Sprint Q.53.F).

    Answers "is the factory ERP linked, and is the data fresh?" — the
    `/infrastructure` endpoint pings DB/Redis/Kafka/Ollama but never the
    ERP itself. This one:

    * masks the connection URL (no credentials leak);
    * does a real round-trip when `sqlserver_enabled` (offline if down);
    * lists the last sync per mirror from `core.etl_run`;
    * reports row counts + lag since the last successful sync.

    Best-effort: a dead ERP or a missing `core.etl_run` table yields a
    degraded-but-shaped 200, never a 500.
    """
    return await collect_erp_connection(session, tenant_id)


@router.get("/full")
async def get_full(
    request: Request,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Single-call snapshot for the admin health page.

    Combines module health + infrastructure + trust index + commit cadence.
    All four sub-collectors are isolated try/except so a single failure
    (e.g. Kafka down) doesn't blank the whole dashboard.
    """
    # Module health is cheap; do it inline.
    routes_by_module = collect_routes_by_module(request.app)
    modules = [m.to_dict() for m in collect_module_health(routes_by_module)]

    # Infra + trust + commits in parallel.
    db_task = check_database(session)
    redis_task = check_redis()
    kafka_task = check_kafka()
    ollama_task = check_ollama()
    trust_task = collect_trust_index(session, tenant_id)
    commits_task = collect_commit_cadence(session, tenant_id)

    # Onda 1.6 — 8s global cap. `return_exceptions=True` already prevents one
    # failure from blanking the dashboard; wait_for prevents a hung client
    # from holding the response open indefinitely.
    try:
        db_res, redis_res, kafka_res, ollama_res, trust_res, commits_res = await asyncio.wait_for(
            asyncio.gather(
                db_task, redis_task, kafka_task, ollama_task, trust_task, commits_task,
                return_exceptions=True,
            ),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        timeout_exc = TimeoutError("global /full timeout (8s)")
        db_res = redis_res = kafka_res = ollama_res = trust_res = commits_res = timeout_exc

    def _safe(value, fallback_label: str) -> Any:
        if isinstance(value, Exception):
            # Onda 2.2 — strip the exception message; raw stringification
            # of SQLAlchemy/psycopg/etc. errors leaks role names, schema
            # paths, and connection strings to the dashboard. The full
            # detail is already in server logs (caller logs `value!r`
            # there); the dashboard only needs the failure category.
            logger.warning(
                "diagnostics %s subcheck failed: %r", fallback_label, value,
            )
            return {
                "component": fallback_label,
                "healthy": False,
                "detail": type(value).__name__,
            }
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return value

    infra_items = [
        _safe(db_res, "postgresql"),
        _safe(redis_res, "redis"),
        _safe(kafka_res, "kafka"),
        _safe(ollama_res, "ollama"),
    ]
    return {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "modules": modules,
        "modules_summary": {
            "total": len(modules),
            "green": sum(1 for r in modules if r["health"] == "green"),
            "yellow": sum(1 for r in modules if r["health"] == "yellow"),
            "red": sum(1 for r in modules if r["health"] == "red"),
            "unknown": sum(1 for r in modules if r["health"] == "unknown"),
        },
        "infrastructure": {
            "items": infra_items,
            "summary": {
                "total": len(infra_items),
                "healthy": sum(1 for i in infra_items if i.get("healthy")),
                "unhealthy": sum(1 for i in infra_items if not i.get("healthy")),
            },
        },
        "trust_index": _safe(trust_res, "trust_index"),
        "commits": _safe(commits_res, "commits"),
    }
