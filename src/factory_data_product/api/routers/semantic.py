"""
Factory semantic-view endpoints — `/v1/factory/semantic/*` (Q.66.D.4b).
========================================================================

- GET /semantic                         (list views)
- GET /semantic/blocked-metrics         (declared BEFORE catch-all)
- GET /semantic/{view_id}               (paginated view data)
- GET /semantic/queries/wip
- GET /semantic/queries/backlog
- GET /semantic/queries/bottlenecks
- GET /semantic/queries/quality
- GET /semantic/queries/mold-conflicts
- GET /semantic/queries/skills-risk
- GET /semantic/queries/lead-time
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.factory_data_product.api.routers._deps import get_engine, get_semantic
from src.factory_data_product.config import ALLOWED_METRICS, BLOCKED_METRICS
from src.factory_data_product.ingest import IngestEngine
from src.factory_data_product.models.semantic import (
    SEMANTIC_VIEW_DEFINITIONS,
    SemanticViewId,
    is_view_allowed,
)
from src.factory_data_product.services.semantic_queries_inmemory import (
    SemanticQueriesInMemory,
)


router = APIRouter(tags=["factory"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SemanticViewResponse(BaseModel):
    """Response for semantic view data."""

    view_id: str
    data: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    trust_score: Optional[float] = None
    disclaimers: List[str] = Field(default_factory=list)


class SemanticViewListResponse(BaseModel):
    """Response listing available views."""

    views: List[Dict[str, Any]]
    total: int


class SemanticQueryResponse(BaseModel):
    """Standard response for semantic queries."""

    data: Optional[Dict[str, Any]] = None
    data_confidence: float = Field(..., description="Trust score 0-100")
    trust_status: str = Field(..., description="OK | WARNING | BLOCKED")
    semantic_label: str = Field(..., description="Human-readable disclaimer")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# View discovery
# ---------------------------------------------------------------------------


@router.get(
    "/semantic",
    response_model=SemanticViewListResponse,
    summary="List semantic views",
    description="List available semantic views (allow-listed).",
)
async def list_semantic_views():
    """List available semantic views."""
    views = [
        {
            "view_id": v.view_id.value,
            "name": v.name,
            "description": v.description,
            "filterable_fields": v.filterable_fields,
            "sortable_fields": v.sortable_fields,
            "trust_score": v.trust_score,
            "is_sensitive": v.is_sensitive,
            "requires_permission": v.requires_permission,
        }
        for v in SEMANTIC_VIEW_DEFINITIONS.values()
    ]

    return SemanticViewListResponse(views=views, total=len(views))


@router.get(
    "/semantic/blocked-metrics",
    summary="Get Blocked Metrics",
    description="List metrics that cannot be calculated with current data.",
    tags=["factory", "semantic-queries"],
)
async def get_blocked_metrics():
    """
    Get list of metrics blocked from calculation.

    Declared BEFORE the catch-all `/semantic/{view_id}` so FastAPI's
    router matches this specific path first; otherwise `view_id` would
    capture `"blocked-metrics"` and reject it via the views allow-list.
    """
    return {
        "blocked_metrics": [
            {
                "metric_id": metric_id,
                "reason": info["reason"],
                "required_data": info["required_data"],
            }
            for metric_id, info in BLOCKED_METRICS.items()
        ],
        "allowed_metrics": ALLOWED_METRICS,
        "total_blocked": len(BLOCKED_METRICS),
        "total_allowed": len(ALLOWED_METRICS),
    }


@router.get(
    "/semantic/{view_id}",
    response_model=SemanticViewResponse,
    summary="Query semantic view",
    description="Query a semantic view with optional filtering and pagination.",
)
async def query_semantic_view(
    view_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: Optional[str] = Query(None, description="Sort field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    engine: IngestEngine = Depends(get_engine),
):
    """
    Query a semantic view.

    Only allow-listed views can be queried.
    Data is filtered by the active ingestion.
    """
    # Validate view is allowed
    if not is_view_allowed(view_id):
        raise HTTPException(
            status_code=400,
            detail=f"View '{view_id}' is not in the allow-list. "
                   f"Allowed views: {[v.value for v in SemanticViewId]}",
        )

    view_def = SEMANTIC_VIEW_DEFINITIONS.get(SemanticViewId(view_id))
    if not view_def:
        raise HTTPException(status_code=404, detail="View definition not found")

    # Check active run
    active = engine.get_active_run()
    if not active:
        # Return empty dataset with trust metadata
        return SemanticViewResponse(
            view_id=view_id,
            data=[],
            total=0,
            page=page,
            page_size=page_size,
            trust_score=view_def.trust_score,
            disclaimers=[*view_def.disclaimers, "No active ingestion data available"],
        )

    # Validate sort field
    if sort_by and sort_by not in view_def.sortable_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{sort_by}' is not sortable. "
                   f"Sortable fields: {view_def.sortable_fields}",
        )

    # In production, this would query the actual view
    # For demo, return mock data based on curated
    ingestion_id = str(active["active_ingestion_id"])
    curated = engine._curated_data.get(ingestion_id, {})

    data = _get_view_data(view_id, curated)

    # Sort
    if sort_by and data:
        reverse = sort_order == "desc"
        data.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

    # Paginate
    total = len(data)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = data[start:end]

    return SemanticViewResponse(
        view_id=view_id,
        data=page_data,
        total=total,
        page=page,
        page_size=page_size,
        trust_score=view_def.trust_score,
        disclaimers=view_def.disclaimers,
    )


def _get_view_data(view_id: str, curated: Dict) -> List[Dict]:
    """Get data for a semantic view from curated data."""
    if view_id == "v_lead_time_historico":
        return [
            {
                "of_id": o["of_id"],
                "produto_id": o.get("produto_id"),
                "modelo_id": o.get("modelo_id"),
                "data_entrada": str(o.get("data_entrada")) if o.get("data_entrada") else None,
                "data_conclusao": str(o.get("data_conclusao")) if o.get("data_conclusao") else None,
                "lead_time_dias": None,  # Would calculate
                "trust_score": 0.7,
            }
            for o in curated.get("orders", [])
        ]

    elif view_id == "v_backlog_fase_teorico":
        # Aggregate phases
        phases: Dict[Any, Dict[str, Any]] = {}
        for p in curated.get("order_phases", []):
            fase_id = p["fase_id"]
            if fase_id not in phases:
                phases[fase_id] = {
                    "fase_id": fase_id,
                    "fase_nome": p.get("fase_nome"),
                    "backlog_horas_teoricas": 0,
                    "backlog_ofs_count": 0,
                    "trust_score": 0.5,
                }
            if p.get("horas_finais"):
                phases[fase_id]["backlog_horas_teoricas"] += float(p["horas_finais"])
            phases[fase_id]["backlog_ofs_count"] += 1
        return list(phases.values())

    elif view_id == "v_skill_risk":
        # Aggregate skills
        fases: Dict[Any, Dict[str, Any]] = {}
        for s in curated.get("skill_matrix", []):
            fase_id = s["fase_id"]
            if fase_id not in fases:
                fases[fase_id] = {
                    "fase_id": fase_id,
                    "fase_nome": s.get("fase_nome"),
                    "aptos_count": 0,
                    "total_funcionarios": 0,
                    "trust_score": 0.7,
                }
            fases[fase_id]["total_funcionarios"] += 1
            if s.get("apto"):
                fases[fase_id]["aptos_count"] += 1
        return list(fases.values())

    # Default: empty
    return []


# ---------------------------------------------------------------------------
# Semantic query endpoints (real data wrappers)
# ---------------------------------------------------------------------------


@router.get(
    "/semantic/queries/wip",
    response_model=SemanticQueryResponse,
    summary="Get WIP (Work in Progress)",
    description="Get theoretical WIP: open orders and open phases.",
    tags=["factory", "semantic-queries"],
)
async def get_wip(
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get Work in Progress from CURATED data.

    Returns open orders and their open phases with trust metadata.
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_wip()
    return SemanticQueryResponse(**result)


@router.get(
    "/semantic/queries/backlog",
    response_model=SemanticQueryResponse,
    summary="Get Backlog by Phase",
    description="Get theoretical backlog by phase (TOC analysis).",
    tags=["factory", "semantic-queries"],
)
async def get_backlog(
    top_n: int = Query(20, ge=1, le=100, description="Number of top phases"),
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get theoretical backlog by phase from CURATED data.

    Backlog = SUM(HorasPrevistas_Final) for open phases
    BacklogDias = Backlog / CapacidadeHorasDia
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_backlog(top_n=top_n)
    return SemanticQueryResponse(**result)


@router.get(
    "/semantic/queries/bottlenecks",
    response_model=SemanticQueryResponse,
    summary="Get Bottleneck Ranking",
    description="Rank phases by theoretical backlog days.",
    tags=["factory", "semantic-queries"],
)
async def get_bottlenecks(
    top_n: int = Query(10, ge=1, le=50, description="Number of top bottlenecks"),
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get bottleneck ranking from CURATED data.

    Phases ranked by backlog_dias_teoricos descending.
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_bottlenecks(top_n=top_n)
    return SemanticQueryResponse(**result)


@router.get(
    "/semantic/queries/quality",
    response_model=SemanticQueryResponse,
    summary="Get Quality Analysis",
    description="Analyze quality issues from error records.",
    tags=["factory", "semantic-queries"],
)
async def get_quality_analysis(
    top_errors: int = Query(10, ge=1, le=50),
    group_by: str = Query("error", regex="^(error|phase|severity)$"),
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get quality analysis from CURATED data.

    Analyze errors grouped by type, phase, or severity.
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_quality(top_errors=top_errors, group_by=group_by)
    return SemanticQueryResponse(**result)


@router.get(
    "/semantic/queries/mold-conflicts",
    response_model=SemanticQueryResponse,
    summary="Get Mold Conflicts",
    description="Detect potential mold conflicts (12h occupancy heuristic).",
    tags=["factory", "semantic-queries"],
)
async def get_mold_conflicts(
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get potential mold conflicts from CURATED data.

    WARNING: Only ~4.8% of phases have DataPrevista, so confidence is very low.
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_mold_conflicts()
    return SemanticQueryResponse(**result)


@router.get(
    "/semantic/queries/skills-risk",
    response_model=SemanticQueryResponse,
    summary="Get Skills Risk",
    description="Identify phases with skill risk (few capable employees).",
    tags=["factory", "semantic-queries"],
)
async def get_skills_risk(
    min_capable: int = Query(3, ge=1, le=10, description="Minimum capable employees"),
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get skills risk analysis from CURATED data.

    Identifies phases where fewer than min_capable employees are qualified.
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_skills_risk(min_capable=min_capable)
    return SemanticQueryResponse(**result)


@router.get(
    "/semantic/queries/lead-time",
    response_model=SemanticQueryResponse,
    summary="Get Lead Time Analysis",
    description="Analyze historical lead times for completed orders.",
    tags=["factory", "semantic-queries"],
)
async def get_lead_time_analysis(
    days_back: int = Query(90, ge=7, le=365, description="Days to look back"),
    semantic: SemanticQueriesInMemory = Depends(get_semantic),
):
    """
    Get lead time analysis from CURATED data.

    Calculates lead time statistics for completed orders.
    Source: curated (real data from Excel ingestion)
    """
    result = semantic.get_lead_time(days_back=days_back)
    return SemanticQueryResponse(**result)
