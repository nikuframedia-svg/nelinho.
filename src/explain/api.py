"""
ProdPlan ONE - Explainability API (aggregator)
==============================================

Endpoints for metric explanations, factor analysis, citations,
causal attribution / discovery, and operator-facing diagnostics.

IMPORTANT: This module integrates with Factory Data Product.
- BLOCKED metrics (OEE, Availability, OTD, etc.) return status=BLOCKED with reason
- AVAILABLE metrics return actual values from SemanticQueries
- All metrics include trust_index and semantic_label

Q.66.D.4c — the original 1216-line router was decomposed into 4
domain-scoped sub-routers under ``src.explain.routers``:

* ``routers.metrics``      — /metric/{id}, /catalog, /blocked, /compute, /commit/{sha}
* ``routers.catalog_full`` — /catalog/full, /catalog/{id}/full, /catalog/search,
                              /catalog/blocked/full, /catalog/available/full,
                              /catalog/markdown
* ``routers.causal``       — /attribution, /discover
* ``routers.diagnostics``  — /diagnostics/{investigate,common-cause,what-changed}

This file is the public seam: ``router`` (the aggregator) plus
backward-compat re-exports for everything callers used to import from
``src.explain.api`` directly (tests + ``src.main``).

The sub-router inclusion order is intentional — see the inline note
above ``include_router(catalog_full_router)``.
"""

from fastapi import APIRouter

from src.explain.routers.catalog_full import router as _catalog_full_router
from src.explain.routers.causal import router as _causal_router
from src.explain.routers.diagnostics import router as _diagnostics_router
from src.explain.routers.metrics import router as _metrics_router

# ----------------------------------------------------------------------------
# Backward-compat re-exports
# ----------------------------------------------------------------------------
# `tests/explain/test_commit_explain.py` imports `_generate_explanation`
# from this module; legacy callers may also import the schemas or the
# catalogue dict. Surface them all here so the decomposition is invisible
# to consumers.
from src.explain.routers.metrics import (  # noqa: F401  (re-export)
    METRIC_CATALOG,
    Citation,
    CommitExplanation,
    ExplainedMetric,
    Factor,
    ImprovementSuggestion,
    MetricCatalogEntry,
    _generate_explanation,
    _resolve_metric_value,
    get_tenant_id,
)

# ----------------------------------------------------------------------------
# Aggregator
# ----------------------------------------------------------------------------
# A single `APIRouter` (no prefix here — each sub-router already carries
# `/v1/explain`) that mounts the four domains in the SAME registration
# order the legacy file used. The order matters: in particular,
# `routers.catalog_full` preserves the pinned bug where
# `/catalog/blocked/full` and `/catalog/available/full` are shadowed by
# `/catalog/{metric_id}/full`. See the Q.66.D.4c TODO comments inside
# `routers/catalog_full.py`.
router = APIRouter()

router.include_router(_metrics_router)          # /metric, /catalog, /blocked, /compute
router.include_router(_catalog_full_router)     # /catalog/full + /catalog/{id}/full + …
router.include_router(_causal_router)           # /attribution, /discover
router.include_router(_diagnostics_router)      # /diagnostics/{investigate,common-cause,what-changed}

# Note: /commit/{commit_sha} lives in routers.metrics (declared after the
# `/compute` endpoint, before the catalog_full block) — matches the
# legacy file's ordering.

__all__ = [
    "router",
    "METRIC_CATALOG",
    "Citation",
    "CommitExplanation",
    "ExplainedMetric",
    "Factor",
    "ImprovementSuggestion",
    "MetricCatalogEntry",
    "_generate_explanation",
    "_resolve_metric_value",
    "get_tenant_id",
]
