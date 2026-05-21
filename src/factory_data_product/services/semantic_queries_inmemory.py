"""
SemanticQueriesInMemory — Real Data from CURATED Layer (In-Memory)
==================================================================

Replaces mock data endpoints with real queries against IN-MEMORY curated
data. No PostgreSQL required — uses ``IngestEngine._curated_data``
directly.

Every query:

- Filters by ``active_ingestion_id``.
- Returns trust metadata.
- Is fully explainable.
- Source = "curated" (not "mock").

Q.67.6.C5 decomposed this file (969L) into the ``semantic/`` sub-package:

- ``semantic.common``     — trust/confidence helpers + active-curated lookup.
- ``semantic.operations`` — WIP, backlog, bottlenecks, overview.
- ``semantic.quality``    — quality, skills risk, lead time, mold conflicts.

This module stays as the public façade: it re-exports
``SemanticQueriesInMemory`` and owns the ``get_semantic_service``
singleton (the tests reset ``_service_instance`` on this module).
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .semantic import SemanticQueriesInMemory

if TYPE_CHECKING:
    from ..ingest.engine import IngestEngine


__all__ = ["SemanticQueriesInMemory", "get_semantic_service"]


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

_service_instance: Optional[SemanticQueriesInMemory] = None


def get_semantic_service(engine: "IngestEngine") -> SemanticQueriesInMemory:
    """Get or create the ``SemanticQueriesInMemory`` service instance.

    Cached per-engine: calling again with the same engine returns the
    same instance; a different engine yields a fresh one.
    """
    global _service_instance

    if _service_instance is None or _service_instance.engine is not engine:
        _service_instance = SemanticQueriesInMemory(engine)

    return _service_instance
