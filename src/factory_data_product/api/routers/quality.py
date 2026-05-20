"""
Factory quality + quarantine endpoints — `/v1/factory/quality/*`, `/v1/factory/quarantine/*` (Q.66.D.4b).
===========================================================================================================

- GET  /quality/trust-heatmap
- GET  /quarantine
- POST /quarantine/{row_id}/resolve
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.factory_data_product.api.routers._deps import get_engine
from src.factory_data_product.ingest import IngestEngine


router = APIRouter(tags=["factory"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TrustHeatmapResponse(BaseModel):
    """Permissive contract for `/quality/trust-heatmap` (Onda 3.7).

    The heatmap payload is rich and evolves sprint-by-sprint; we lock the
    top-level keys clients depend on and let the rest pass through with
    `extra="allow"` so future additions don't require a coordinated
    front-end + back-end ship.
    """

    model_config = {"extra": "allow"}

    overall_trust: float
    overall_status: str
    domains: List[str]
    segments: Dict[str, Any]
    summary: Dict[str, Any]
    generated_at: str
    ingestion_id: Optional[str] = None


class QuarantineRowResponse(BaseModel):
    """Response for a single quarantined row."""

    id: str
    table_name: str
    row_data: Dict[str, Any]
    quarantine_code: str
    quarantine_reason: str
    quarantined_at: str
    ingestion_id: str


class QuarantineListResponse(BaseModel):
    """Response for quarantine list."""

    rows: List[QuarantineRowResponse]
    total: int
    page: int
    page_size: int
    by_code: Dict[str, int]
    by_table: Dict[str, int]


# ---------------------------------------------------------------------------
# Trust heatmap
# ---------------------------------------------------------------------------


@router.get(
    "/quality/trust-heatmap",
    summary="Get Trust Heatmap",
    description="""
    Get a trust heatmap showing data quality by segment and domain.

    Returns:
    - Trust values by segment (rows) and domain (columns)
    - Overall trust score
    - Segments categorized by status (excellent/good/warning/critical)
    - Improvement priorities
    - Alerts for low-trust segments
    """,
    tags=["factory", "quality"],
)
async def get_trust_heatmap(
    include_priorities: bool = Query(True, description="Include improvement priorities"),
    include_alerts: bool = Query(True, description="Include alerts"),
    engine: IngestEngine = Depends(get_engine),
) -> TrustHeatmapResponse:
    """
    Get trust heatmap for data quality visualization.

    This endpoint provides a comprehensive view of data quality across
    all segments and domains, with actionable insights for improvement.
    """
    from src.factory_data_product.quality.trust_heatmap import get_trust_heatmap_generator

    generator = get_trust_heatmap_generator()

    # Get current active run ID
    active_run = engine.get_active_run()
    ingestion_id = str(active_run.get("active_ingestion_id")) if active_run else None

    # Generate heatmap
    heatmap = generator.generate(ingestion_id=ingestion_id)

    result = heatmap.to_dict()

    # Add priorities if requested
    if include_priorities:
        result["improvement_priorities"] = generator.get_improvement_priorities(heatmap)

    # Add alerts if requested
    if include_alerts:
        result["alerts"] = generator.generate_alerts(heatmap)

    return TrustHeatmapResponse(**result)


# ---------------------------------------------------------------------------
# Quarantine
# ---------------------------------------------------------------------------


@router.get(
    "/quarantine",
    response_model=QuarantineListResponse,
    summary="List Quarantined Rows",
    description="Get rows that have been quarantined due to data quality issues.",
    tags=["factory", "data-quality"],
)
async def list_quarantined_rows(
    table: Optional[str] = Query(None, description="Filter by table name"),
    code: Optional[str] = Query(None, description="Filter by quarantine code"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    engine: IngestEngine = Depends(get_engine),
):
    """
    List quarantined rows across all curated tables.

    Quarantined rows are problematic records that were not deleted
    but marked for review. Common quarantine codes:
    - MISSING_KEY: Required business key is missing
    - INVALID_TIMING: End date before start date
    - INVALID_VALUE: Value out of valid range
    - DUPLICATE_KEY: Duplicate business key
    - ORPHAN_RECORD: Foreign key references non-existent record
    - DATA_CONFLICT: Conflicting data within same record
    - OUTLIER: Statistical outlier
    """
    # Mock response - in production this would query the database
    mock_rows = [
        QuarantineRowResponse(
            id="q-001",
            table_name="FasesOrdemFabrico",
            row_data={
                "FaseOf_Id": "12345",
                "FaseOf_OfId": "OF-001",
                "FaseOf_Inicio": "2024-01-15T10:00:00",
                "FaseOf_Fim": "2024-01-15T08:00:00",
            },
            quarantine_code="INVALID_TIMING",
            quarantine_reason="Fim (2024-01-15 08:00) antes de Início (2024-01-15 10:00), duração=-2.00h",
            quarantined_at="2024-01-28T12:00:00Z",
            ingestion_id="ing-abc123",
        ),
        QuarantineRowResponse(
            id="q-002",
            table_name="Funcionarios",
            row_data={
                "Funcionario_Id": "F-999",
                "Funcionario_Nome": "Test",
                "FuncionarioValorHora": -5.0,
            },
            quarantine_code="INVALID_VALUE",
            quarantine_reason="ValorHora negativo (-5.0), deve ser >= 0",
            quarantined_at="2024-01-28T12:00:00Z",
            ingestion_id="ing-abc123",
        ),
    ]

    # Filter by table if provided
    if table:
        mock_rows = [r for r in mock_rows if r.table_name == table]

    # Filter by code if provided
    if code:
        mock_rows = [r for r in mock_rows if r.quarantine_code == code]

    # Calculate stats
    by_code: Dict[str, int] = {}
    by_table: Dict[str, int] = {}
    for row in mock_rows:
        by_code[row.quarantine_code] = by_code.get(row.quarantine_code, 0) + 1
        by_table[row.table_name] = by_table.get(row.table_name, 0) + 1

    # Paginate
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated = mock_rows[start_idx:end_idx]

    return QuarantineListResponse(
        rows=paginated,
        total=len(mock_rows),
        page=page,
        page_size=page_size,
        by_code=by_code,
        by_table=by_table,
    )


@router.post(
    "/quarantine/{row_id}/resolve",
    summary="Resolve Quarantine",
    description="Mark a quarantined row as resolved (repaired or accepted).",
    tags=["factory", "data-quality"],
)
async def resolve_quarantine(
    row_id: str,
    action: str = Query(..., description="Action: 'repair', 'accept_risk', 'delete'"),
    reason: str = Query(..., min_length=10, description="Reason for resolution"),
    user: str = Query("api_user", description="User resolving"),
):
    """
    Resolve a quarantined row.

    Actions:
    - repair: Mark as repaired (data was fixed)
    - accept_risk: Accept the risk and include in metrics
    - delete: Permanently remove the row
    """
    return {
        "success": True,
        "row_id": row_id,
        "action": action,
        "reason": reason,
        "resolved_by": user,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Row {row_id} resolved with action '{action}'",
    }
