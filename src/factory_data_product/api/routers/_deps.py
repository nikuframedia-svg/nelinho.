"""
Shared dependencies for factory_data_product sub-routers (Q.66.D.4b).
====================================================================

Hosts the singleton `IngestEngine` and `SemanticQueriesInMemory` providers
used by every sub-router under `routers/`.

These are re-exported from `src.factory_data_product.api.endpoints` so that:
- existing imports (`from src.factory_data_product.api.endpoints import get_engine`)
  keep working (used by copilot.alerts.engine, copilot.service, plan.services.routing_resolver, factory_map);
- characterization tests' `app.dependency_overrides[get_engine] = ...` still
  override the dep that the sub-router endpoints actually depend on (FastAPI
  matches by identity of the callable).

Keeping the dep functions in this single module — and having endpoints.py
re-export the same objects — ensures both code paths (legacy import + new
sub-router import) resolve to identical callables.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends

from src.factory_data_product.ingest import IngestEngine
from src.factory_data_product.services.semantic_queries_inmemory import (
    SemanticQueriesInMemory,
    get_semantic_service,
)


# Process-wide engine singleton (the real DI lives in production wiring).
_engine: Optional[IngestEngine] = None


def get_engine() -> IngestEngine:
    """Get engine dependency."""
    global _engine
    if _engine is None:
        _engine = IngestEngine()
    return _engine


def get_semantic(engine: IngestEngine = Depends(get_engine)) -> SemanticQueriesInMemory:
    """Get semantic queries service dependency."""
    return get_semantic_service(engine)
