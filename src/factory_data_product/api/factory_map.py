"""
ProdPlan ONE - Factory Map API (Sprint N)
==========================================

Blueprint v2.0 §3.2 — 6 endpoints under `/v1/factory-map/*`:

    GET /snapshot               — FM01/FM02: full factory snapshot
    GET /boats/{of_id}          — FM02: per-boat trajectory + risk flags
    GET /projection             — FM03: forward heatmap (historical avg)
    GET /shortage-risks         — FM04: ROP-based shortage detector
    GET /line-load              — FM06: schedule load per (op, date)
    GET /kpis                   — FM05: strategic KPIs

Every endpoint is thin — the heavy lifting is in
`FactoryMapService`. Redis caching for `/snapshot` honours the
`factory_map.snapshot.cache_ttl_seconds` TenantConfig key (default 30s
from Sprint L.4).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.services.factory_map_service import FactoryMapService
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/factory-map", tags=["Factory Map"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


async def _build_service(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    parallel: bool = False,
) -> FactoryMapService:
    """Construct the aggregator with a lazy semantic-service lookup.

    Falls back to `None` for the semantic service if the in-memory engine
    hasn't been warmed up yet — the service methods already handle that.

    Q.54.C — `parallel=True` (used by `/snapshot`) injects the global
    `async_session_factory` so the snapshot fans its independent DB reads
    out concurrently, each on its own session.
    """
    semantic = None
    try:
        from src.factory_data_product.ingest.engine import get_engine
        from src.factory_data_product.services import get_semantic_service

        semantic = get_semantic_service(get_engine())
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("semantic service unavailable: %s", exc)

    session_factory = None
    if parallel:
        from src.shared.database import async_session_factory

        session_factory = async_session_factory

    return FactoryMapService(
        session, tenant_id,
        semantic_service=semantic,
        session_factory=session_factory,
    )


async def _cache_ttl(session: AsyncSession, tenant_id: UUID) -> int:
    """Read `factory_map.snapshot.cache_ttl_seconds` from TenantConfig."""
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        cfg = TenantConfigService(session, tenant_id)
        return int(await cfg.get("factory_map", "snapshot.cache_ttl_seconds", default=30))
    except Exception:
        return 30


# ---------------------------------------------------------------------------
# Response models — small, permissive; Factory Map payloads are best-effort
# and may include extra keys as sub-services grow.
# ---------------------------------------------------------------------------

class FactoryMapPayload(BaseModel):
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/snapshot")
async def get_snapshot(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Global factory snapshot. Redis-cached with the
    `factory_map.snapshot.cache_ttl_seconds` TTL."""
    # Cache read
    try:
        from src.shared.redis_client import RedisClient, get_redis

        redis = await get_redis()
        key = RedisClient.tenant_key(tenant_id, "factory_map", "snapshot")
        cached = await redis.get(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception as exc:
                # Sprint Q.7 Fase 4 — was bare `pass`. Corrupt cache
                # entry → fallthrough to recompute. Log under DEBUG.
                logger.debug("factory_map: corrupt cache for %s: %s", key, exc)
    except Exception as exc:
        logger.debug("factory_map: redis unavailable, computing fresh: %s", exc)
        redis = None
        key = None

    svc = await _build_service(session, tenant_id, parallel=True)
    payload = await svc.snapshot()

    if redis is not None and key is not None:
        try:
            ttl = await _cache_ttl(session, tenant_id)
            await redis.setex(key, ttl, json.dumps(payload, default=str))
        except Exception as exc:
            # Sprint Q.7 Fase 4 — best-effort cache write; never block
            # the response on a Redis hiccup, but log so cache thrash
            # is visible.
            logger.debug("factory_map: cache write failed: %s", exc)

    return payload


@router.get("/boats/{of_id}")
async def get_boat(
    of_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Per-boat trajectory + risk flags."""
    svc = await _build_service(session, tenant_id)
    result = await svc.boat_view(of_id=of_id)
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Order {of_id} not found",
        )
    return result


@router.get("/projection")
async def get_projection(
    days_ahead: int = Query(7, ge=1, le=30),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Forward heatmap based on historical phase durations.

    Does NOT run the CPO engine — Sprint P is the one that wires in the
    full greedy cascade. The historical-average method is honest about
    its source via the `method` field in the response.
    """
    svc = await _build_service(session, tenant_id)
    return await svc.projection(days_ahead=days_ahead)


@router.get("/shortage-risks")
async def get_shortage_risks(
    horizon_days: int = Query(14, ge=1, le=180),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """ROP-based shortage detector. BOM explosion lands in Sprint O.2."""
    svc = await _build_service(session, tenant_id)
    return await svc.shortage_risks(horizon_days=horizon_days)


@router.get("/line-load")
async def get_line_load(
    horizon_days: int = Query(14, ge=1, le=180),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Production schedule load per (operation, date) for `horizon_days`."""
    svc = await _build_service(session, tenant_id)
    return await svc.line_load(horizon_days=horizon_days)


@router.get("/kpis")
async def get_kpis(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Strategic KPIs. Throughput €/dia stays `unavailable` until Sprint Q.0."""
    svc = await _build_service(session, tenant_id)
    return await svc.kpis()
