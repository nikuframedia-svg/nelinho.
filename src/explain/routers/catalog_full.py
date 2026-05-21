"""Q.66.D.4c — Full catalog sub-router (extracted from `src.explain.api`).

Hosts the comprehensive catalog endpoints driven by
``src.explain.catalog``:

* ``GET /v1/explain/catalog/full``
* ``GET /v1/explain/catalog/blocked/full``
* ``GET /v1/explain/catalog/available/full``
* ``GET /v1/explain/catalog/search``
* ``GET /v1/explain/catalog/{metric_id}/full``
* ``GET /v1/explain/catalog/markdown``

ROUTE ORDER MATTERS. Specific literal paths (``/catalog/blocked/full``
and ``/catalog/available/full``) MUST be declared BEFORE the generic
``/catalog/{metric_id}/full`` — Q.67.1.E fix to the route-collision
bug pinned in Q.66.D.4c.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.explain.catalog import (
    METRIC_CATALOG as FULL_CATALOG,
    MetricDomain,
    generate_catalog_markdown,
    get_available_metrics,
    get_blocked_metrics as get_blocked_from_catalog,
    get_metric,
    get_metrics_by_domain,
    search_metrics,
)

router = APIRouter(prefix="/v1/explain", tags=["Explainability"])


# ============================================================================
# NEW CATALOG ENDPOINTS (from P0-3)
# ============================================================================

@router.get("/catalog/full")
async def get_full_metric_catalog(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    include_blocked: bool = Query(True, description="Include blocked metrics"),
):
    """
    Get the complete metric catalog with all definitions.

    This is the authoritative source for all metrics in the system.
    Each metric includes:
    - Full definition (formula, description, unit)
    - Trust information (base index, coverage requirements)
    - Forbidden claims (what NOT to say)
    - How to improve (actionable steps)
    """
    if domain:
        try:
            domain_enum = MetricDomain(domain)
            metrics = get_metrics_by_domain(domain_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain: {domain}. Valid: {[d.value for d in MetricDomain]}"
            )
    else:
        metrics = list(FULL_CATALOG.values())

    if not include_blocked:
        metrics = [m for m in metrics if not m.is_blocked]

    return {
        "metrics": [m.to_dict() for m in metrics],
        "total": len(metrics),
        "domains": [d.value for d in MetricDomain],
        "blocked_count": len([m for m in metrics if m.is_blocked]),
        "available_count": len([m for m in metrics if not m.is_blocked]),
    }


# Q.67.1.E: declarado ANTES de /catalog/{metric_id}/full — ordem matters em FastAPI
@router.get("/catalog/blocked/full")
async def get_full_blocked_metrics():
    """
    Get detailed information about all blocked metrics.

    Blocked metrics are those that cannot be computed due to missing data.
    This endpoint provides:
    - Why each metric is blocked
    - What data is needed to unblock
    - Actionable steps to enable the metric
    """
    blocked = get_blocked_from_catalog()

    return {
        "blocked": [
            {
                "id": m.id,
                "name": m.name,
                "name_pt": m.name_pt,
                "blocked_reason": m.blocked_reason,
                "how_to_improve": m.how_to_improve,
                "domain": m.domain.value,
            }
            for m in blocked
        ],
        "total": len(blocked),
        "message": f"{len(blocked)} metrics are blocked due to missing data",
    }


@router.get("/catalog/available/full")
async def get_full_available_metrics():
    """
    Get all metrics that can be computed with current data.

    These are the metrics that are safe to use in the UI and API.
    Each includes trust level and coverage information.
    """
    available = get_available_metrics()

    return {
        "available": [
            {
                "id": m.id,
                "name": m.name,
                "name_pt": m.name_pt,
                "unit": m.unit,
                "base_trust_index": m.base_trust_index,
                "semantic_kind": m.semantic_kind.value,
                "domain": m.domain.value,
                "assumptions": m.assumptions,
                "forbidden_claims": m.forbidden_claims,
            }
            for m in available
        ],
        "total": len(available),
    }


@router.get("/catalog/search")
async def search_metric_catalog(
    q: str = Query(..., min_length=2, description="Search query"),
):
    """
    Search the metric catalog by name or description.

    Searches in:
    - Name (EN and PT)
    - Description (EN and PT)
    - Formula
    """
    results = search_metrics(q)

    return {
        "query": q,
        "results": [m.to_dict() for m in results],
        "total": len(results),
    }


@router.get("/catalog/{metric_id}/full")
async def get_full_metric_definition(metric_id: str):
    """
    Get the complete definition for a specific metric.

    Returns ALL metadata including:
    - Formula and description (PT and EN)
    - Data sources with trust and coverage
    - Assumptions and forbidden claims
    - How to improve actions
    - Dependency chain
    """
    metric = get_metric(metric_id)

    if not metric:
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{metric_id}' not found in catalog."
        )

    return metric.to_dict()


@router.get("/catalog/markdown")
async def get_catalog_as_markdown():
    """
    Generate markdown documentation from the metric catalog.

    Useful for:
    - Auto-generating documentation
    - Exporting for external systems
    - Auditing metric definitions
    """
    markdown = generate_catalog_markdown()

    return {
        "format": "markdown",
        "content": markdown,
        "generated_at": datetime.utcnow().isoformat(),
    }
