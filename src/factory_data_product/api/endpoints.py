"""
Factory API — aggregator router (Q.66.D.4b).
=============================================

This module is the public surface of the factory_data_product HTTP API.
It composes per-domain sub-routers under a single `/v1/factory` prefix:

- meta       → /meta/active-run, /meta/quality-report, /meta/schema-drift,
               /meta/schema-history, /meta/ingestions
- semantic   → /semantic (list), /semantic/blocked-metrics, /semantic/{view_id},
               /semantic/queries/{wip,backlog,bottlenecks,quality,
                                   mold-conflicts,skills-risk,lead-time}
- ingest     → /ingest (multipart), /ingest-by-path (dev)
- lifecycle  → /activate/{ingestion_id}, /rollback
- watcher    → /watcher/status
- quality    → /quality/trust-heatmap, /quarantine, /quarantine/{id}/resolve

Backward-compat exports
-----------------------
`router`, `get_engine` and `get_semantic` remain importable from this module:

    from src.factory_data_product.api.endpoints import router, get_engine, get_semantic

External callers (`copilot.alerts.engine`, `copilot.service`,
`plan.services.routing_resolver`, `factory_map`, characterization tests) keep
working without modification. `dependency_overrides[get_engine] = ...` in
tests still overrides the same callable that every sub-router depends on —
the deps live in `routers/_deps.py` and are re-exported here.

History: previously a 1311-line god-module containing every endpoint inline.
Decomposed in Q.66.D.4b, pinned by 42 characterization tests in
`tests/factory_data_product/test_endpoints_characterization_q66_d.py`.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.factory_data_product.api.routers._deps import get_engine, get_semantic
from src.factory_data_product.api.routers.ingest import router as ingest_router
from src.factory_data_product.api.routers.lifecycle import router as lifecycle_router
from src.factory_data_product.api.routers.meta import router as meta_router
from src.factory_data_product.api.routers.quality import router as quality_router
from src.factory_data_product.api.routers.semantic import router as semantic_router
from src.factory_data_product.api.routers.watcher import router as watcher_router


__all__ = ["router", "get_engine", "get_semantic"]


router = APIRouter(prefix="/v1/factory", tags=["factory"])

router.include_router(meta_router)
router.include_router(semantic_router)
router.include_router(ingest_router)
router.include_router(lifecycle_router)
router.include_router(watcher_router)
router.include_router(quality_router)
