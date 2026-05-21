"""Q.67.6.C5 — semantic queries package.

Composes the public ``SemanticQueriesInMemory`` class from three thematic
mixins so each sub-module stays small and focused:

- :mod:`.common`     — trust/confidence helpers + active-curated lookup.
- :mod:`.operations` — WIP, backlog, bottlenecks, overview.
- :mod:`.quality`    — quality, skills risk, lead time, mold conflicts.

The singleton factory ``get_semantic_service`` and its module-level cache
live in the façade ``semantic_queries_inmemory.py`` so the existing test
suite can keep resetting ``mod._service_instance``.
"""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from .common import _SemanticCommonMixin
from .operations import _SemanticOperationsMixin
from .quality import _SemanticQualityMixin

if TYPE_CHECKING:
    from ...ingest.engine import IngestEngine


class SemanticQueriesInMemory(
    _SemanticOperationsMixin,
    _SemanticQualityMixin,
    _SemanticCommonMixin,
):
    """Real semantic queries against IN-MEMORY CURATED data.

    Architecture:
    - Uses ``engine._curated_data[active_ingestion_id]`` as data source.
    - All queries respect the active_ingestion_id filter.
    - All responses include trust metadata.
    - All calculations are explainable.
    - NO DATABASE REQUIRED — works with in-memory data.

    Usage::

        from factory_data_product.ingest.engine import get_engine
        from factory_data_product.services import get_semantic_service

        engine = get_engine()
        service = get_semantic_service(engine)
        result = service.get_wip()
    """

    def __init__(self, engine: "IngestEngine") -> None:
        self.engine = engine
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 30  # seconds


__all__ = ["SemanticQueriesInMemory"]
