"""
ProdPlan ONE - Diagnostics API (Sprint Q.7 Fase 1)
==================================================

Live audit dashboard endpoint. Powers the `/admin/health` page.

Endpoints:

  GET /v1/diagnostics/modules
        — per-module health rollup (imports, routes, tests, TODOs)
  GET /v1/diagnostics/infrastructure
        — DB, Redis, Kafka, Ollama pings
  GET /v1/diagnostics/full
        — modules + infra + trust + commit cadence (the "single click"
          dashboard answer)

The endpoint is admin-only at the route layer; the data is read-only and
non-destructive.
"""

from __future__ import annotations

import asyncio
import logging
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
    collect_module_health,
    collect_routes_by_module,
    collect_trust_index,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/diagnostics", tags=["Diagnostics"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


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
    """Ping every infrastructure component the app depends on. ~3-4s if
    Kafka/Redis are slow; <500ms when everything is local + warm."""
    db_check = await check_database(session)
    other = await asyncio.gather(
        check_redis(),
        check_kafka(),
        check_ollama(),
    )
    items = [db_check.to_dict()] + [c.to_dict() for c in other]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "healthy": sum(1 for i in items if i["healthy"]),
            "unhealthy": sum(1 for i in items if not i["healthy"]),
        },
    }


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

    db_res, redis_res, kafka_res, ollama_res, trust_res, commits_res = await asyncio.gather(
        db_task, redis_task, kafka_task, ollama_task, trust_task, commits_task,
        return_exceptions=True,
    )

    def _safe(value, fallback_label: str) -> Any:
        if isinstance(value, Exception):
            return {
                "component": fallback_label,
                "healthy": False,
                "detail": f"{type(value).__name__}: {value!s}"[:200],
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
        "modules": modules,
        "modules_summary": {
            "total": len(modules),
            "green": sum(1 for r in modules if r["health"] == "green"),
            "yellow": sum(1 for r in modules if r["health"] == "yellow"),
            "red": sum(1 for r in modules if r["health"] == "red"),
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
