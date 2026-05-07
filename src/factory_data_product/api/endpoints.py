"""
Factory API Endpoints — Contrato 010
====================================

Read-only endpoints:
- GET /v1/factory/meta/active-run
- GET /v1/factory/meta/quality-report/{ingestion_id}
- GET /v1/factory/meta/ingestions
- GET /v1/factory/semantic/{view_id}
- GET /v1/factory/semantic/queries/wip
- GET /v1/factory/semantic/queries/backlog
- GET /v1/factory/semantic/queries/bottlenecks
- GET /v1/factory/semantic/queries/quality
- GET /v1/factory/semantic/queries/mold-conflicts
- GET /v1/factory/semantic/queries/skills-risk
- GET /v1/factory/semantic/queries/lead-time
- POST /v1/factory/ingest (upload)
- POST /v1/factory/activate/{ingestion_id}
- POST /v1/factory/rollback
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel, Field

from src.factory_data_product.models.meta import (
    IngestionRunResponse,
    ActiveRunResponse,
    QualityCheckResponse,
    IngestionStatus,
    QualityGateStatus,
)
from src.factory_data_product.models.semantic import (
    SemanticViewId,
    SEMANTIC_VIEW_DEFINITIONS,
    is_view_allowed,
)
from src.factory_data_product.ingest import IngestEngine
from src.factory_data_product.models.meta import SourceType
from src.factory_data_product.config import BLOCKED_METRICS, ALLOWED_METRICS
from src.factory_data_product.services.semantic_queries_inmemory import (
    SemanticQueriesInMemory,
    get_semantic_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/factory", tags=["factory"])


# Global engine (would be injected via DI in production)
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


# ============================================================================
# SCHEMAS
# ============================================================================

class ActiveRunResponseModel(BaseModel):
    """Response for active run."""
    
    active_ingestion_id: Optional[str] = None
    activated_at_utc: Optional[datetime] = None
    activated_by: Optional[str] = None
    has_active: bool = False


class QualityReportResponse(BaseModel):
    """Response for quality report."""
    
    ingestion_id: str
    quality_gate_status: str
    checks: List[Dict[str, Any]]
    total_checks: int
    passed_checks: int
    failed_blocking: int
    failed_warning: int


class IngestionListResponse(BaseModel):
    """Response for ingestion list."""
    
    ingestions: List[Dict[str, Any]]
    total: int


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


class IngestResponse(BaseModel):
    """Response for ingestion."""
    
    success: bool
    ingestion_id: Optional[str] = None
    status: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    total_rows_raw: int = 0
    total_rows_curated: int = 0
    quality_gate_status: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ActivateRequest(BaseModel):
    """Request to activate an ingestion."""
    
    user: str = Field(default="api_user", description="User performing activation")


class RollbackRequest(BaseModel):
    """Request to rollback."""
    
    to_ingestion_id: str
    reason: str = Field(..., min_length=10)
    user: str = Field(default="api_user")


# ============================================================================
# META ENDPOINTS
# ============================================================================

@router.get(
    "/meta/active-run",
    response_model=ActiveRunResponseModel,
    summary="Get active ingestion run",
    description="Get the currently active ingestion run.",
)
async def get_active_run(
    engine: IngestEngine = Depends(get_engine),
):
    """Get the active ingestion run."""
    active = engine.get_active_run()
    
    if not active:
        return ActiveRunResponseModel(has_active=False)
    
    return ActiveRunResponseModel(
        active_ingestion_id=str(active["active_ingestion_id"]),
        activated_at_utc=active["activated_at_utc"],
        activated_by=active["activated_by"],
        has_active=True,
    )


@router.get(
    "/meta/quality-report/{ingestion_id}",
    response_model=QualityReportResponse,
    summary="Get quality report",
    description="Get quality check results for an ingestion.",
)
async def get_quality_report(
    ingestion_id: str,
    engine: IngestEngine = Depends(get_engine),
):
    """Get quality report for an ingestion."""
    try:
        uid = UUID(ingestion_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    
    run = engine._ingestion_runs.get(uid)
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion not found")
    
    checks = [c for c in engine._quality_checks if c.get("ingestion_id") == uid]
    
    passed = sum(1 for c in checks if c.get("passed"))
    failed_blocking = sum(
        1 for c in checks 
        if not c.get("passed") and c.get("severity") == "blocking"
    )
    failed_warning = sum(
        1 for c in checks 
        if not c.get("passed") and c.get("severity") == "warning"
    )
    
    return QualityReportResponse(
        ingestion_id=ingestion_id,
        quality_gate_status=run.quality_gate_status.value,
        checks=checks,
        total_checks=len(checks),
        passed_checks=passed,
        failed_blocking=failed_blocking,
        failed_warning=failed_warning,
    )


class SchemaDriftResponse(BaseModel):
    """Response for schema drift report."""
    
    has_drift: bool
    has_blocking: bool
    summary: str
    stats: Dict[str, int]
    items: List[Dict[str, Any]]
    baseline_ingestion_id: Optional[str] = None
    baseline_timestamp: Optional[datetime] = None
    current_timestamp: datetime


class SchemaHistoryResponse(BaseModel):
    """Response for schema history."""
    
    snapshots: List[Dict[str, Any]]
    total: int


@router.get(
    "/meta/schema-drift",
    response_model=SchemaDriftResponse,
    summary="Get latest schema drift report",
    description="Get the schema drift report from the most recent ingestion.",
)
async def get_schema_drift(
    engine: IngestEngine = Depends(get_engine),
):
    """
    Get the latest schema drift report.
    
    Returns information about:
    - Columns added/removed/renamed
    - Sheets added/removed
    - Whether drift is blocking or just a warning
    """
    # Get the most recent drift report from ingestion results
    history = engine.get_schema_history()

    if len(history) < 2:
        return SchemaDriftResponse(
            has_drift=False,
            has_blocking=False,
            summary="No drift - only one schema snapshot exists",
            stats={
                "columns_added": 0,
                "columns_removed": 0,
                "columns_renamed": 0,
                "sheets_added": 0,
                "sheets_removed": 0,
            },
            items=[],
            baseline_ingestion_id=history[0].get("ingestion_id") if history else None,
            baseline_timestamp=(
                datetime.fromisoformat(history[0]["timestamp"]) if history else None
            ),
            current_timestamp=datetime.now(timezone.utc),
        )

    # Onda 1.8 — actually run drift detection between the last two
    # snapshots. The previous version built a SchemaDriftDetector and a
    # SchemaSnapshot but never called detect_drift(), returning hardcoded
    # `has_drift=False`. We now diff the snapshots directly and surface
    # the real result.
    from src.factory_data_product.ingest.drift_detector import (
        DriftReport,
        DriftItem,
        DriftSeverity,
        DriftType,
        CRITICAL_COLUMNS,
        CRITICAL_SHEETS,
    )

    baseline = history[-2]
    current = history[-1]
    base_sheets: Dict[str, set] = {
        n: set(cols) for n, cols in baseline.get("sheets", {}).items()
    }
    curr_sheets: Dict[str, set] = {
        n: set(cols) for n, cols in current.get("sheets", {}).items()
    }

    report = DriftReport()
    # Sheets added / removed
    for sheet in set(curr_sheets) - set(base_sheets):
        report.add_item(DriftItem(
            drift_type=DriftType.SHEET_ADDED,
            severity=DriftSeverity.WARNING,
            sheet_name=sheet,
            message=f"New sheet '{sheet}' detected",
        ))
    for sheet in set(base_sheets) - set(curr_sheets):
        report.add_item(DriftItem(
            drift_type=DriftType.SHEET_REMOVED,
            severity=(
                DriftSeverity.BLOCKING if sheet in CRITICAL_SHEETS
                else DriftSeverity.WARNING
            ),
            sheet_name=sheet,
            message=f"Sheet '{sheet}' is missing",
        ))
    # Columns within common sheets
    for sheet in set(base_sheets) & set(curr_sheets):
        added = curr_sheets[sheet] - base_sheets[sheet]
        removed = base_sheets[sheet] - curr_sheets[sheet]
        critical_cols = CRITICAL_COLUMNS.get(sheet, set())
        for col in added:
            report.add_item(DriftItem(
                drift_type=DriftType.COLUMN_ADDED,
                severity=DriftSeverity.INFO,
                sheet_name=sheet, column_name=col,
                message=f"New column '{col}' in sheet '{sheet}'",
            ))
        for col in removed:
            report.add_item(DriftItem(
                drift_type=DriftType.COLUMN_REMOVED,
                severity=(
                    DriftSeverity.BLOCKING if col in critical_cols
                    else DriftSeverity.WARNING
                ),
                sheet_name=sheet, column_name=col,
                message=f"Column '{col}' missing from '{sheet}'",
            ))

    return SchemaDriftResponse(
        has_drift=report.has_drift,
        has_blocking=report.has_blocking,
        summary=report.generate_summary(),
        stats={
            "columns_added": report.columns_added,
            "columns_removed": report.columns_removed,
            "columns_renamed": report.columns_renamed,
            "sheets_added": report.sheets_added,
            "sheets_removed": report.sheets_removed,
        },
        items=[
            {
                "drift_type": i.drift_type.value,
                "severity": i.severity.value,
                "sheet_name": i.sheet_name,
                "column_name": i.column_name,
                "message": i.message,
            }
            for i in report.items
        ],
        baseline_ingestion_id=baseline.get("ingestion_id"),
        baseline_timestamp=(
            datetime.fromisoformat(baseline["timestamp"])
            if baseline.get("timestamp") else None
        ),
        current_timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/meta/schema-history",
    response_model=SchemaHistoryResponse,
    summary="Get schema history",
    description="Get the history of schema snapshots from all ingestions.",
)
async def get_schema_history(
    engine: IngestEngine = Depends(get_engine),
):
    """
    Get schema history across all ingestions.
    
    Shows how the schema evolved over time.
    """
    history = engine.get_schema_history()
    
    return SchemaHistoryResponse(
        snapshots=history,
        total=len(history),
    )


@router.get(
    "/meta/ingestions",
    response_model=IngestionListResponse,
    summary="List ingestions",
    description="List all ingestion runs.",
)
async def list_ingestions(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    engine: IngestEngine = Depends(get_engine),
):
    """List all ingestion runs."""
    ingestions = engine.list_ingestions()
    
    if status:
        ingestions = [i for i in ingestions if i.get("status") == status]
    
    return IngestionListResponse(
        ingestions=ingestions[:limit],
        total=len(ingestions),
    )


# ============================================================================
# SEMANTIC ENDPOINTS
# ============================================================================

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
            disclaimers=view_def.disclaimers + ["No active ingestion data available"],
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
        phases = {}
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
        fases = {}
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


# ============================================================================
# INGEST ENDPOINTS
# ============================================================================


def _is_under(child, parent) -> bool:
    """Onda 5.4 — return True iff `child` is `parent` or a descendant of it.

    Both arguments must be already-resolved absolute Paths. Uses
    `Path.is_relative_to` (Python 3.9+) and falls back to a string-prefix
    check (with separator) when not available. The separator check is
    needed so `/data` is NOT considered a parent of `/data_other`.
    """
    try:
        return child.is_relative_to(parent)
    except (AttributeError, ValueError):
        # `is_relative_to` raises ValueError on Python <3.12 when the
        # paths are siblings; fall through to string check.
        import os
        c = str(child)
        p = str(parent).rstrip(os.sep)
        return c == p or c.startswith(p + os.sep)


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest Excel file",
    description="Upload and ingest an Excel file.",
)
async def ingest_file(
    file: UploadFile = File(...),
    auto_activate: bool = Query(False, description="Auto-activate on success"),
    user: str = Query("api_user", description="User performing ingest"),
    engine: IngestEngine = Depends(get_engine),
):
    """
    Ingest an Excel file.

    Steps:
    1. Receive file (cap at 100 MB to avoid DoS via giant uploads)
    2. Calculate hash (idempotency check)
    3. Extract to RAW
    4. Run quality gates
    5. Transform to CURATED
    6. Optionally activate
    """
    import tempfile
    from pathlib import Path

    # Onda 1.8 — DoS guard. The Folha_IA_extra.xlsx ships ~57 MB, so 100 MB
    # is generous headroom; anything larger is almost certainly an attack
    # or a misconfigured client. Cap is enforced after read because
    # UploadFile.size is not always populated by clients.
    MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        result = engine.ingest(
            file_path=tmp_path,
            source_type=SourceType.UPLOAD,
            created_by=user,
            auto_activate=auto_activate,
        )
        
        return IngestResponse(
            success=result.success,
            ingestion_id=str(result.ingestion_id) if result.ingestion_id else None,
            status=result.status.value,
            is_duplicate=result.is_duplicate,
            duplicate_of=str(result.duplicate_of) if result.duplicate_of else None,
            total_rows_raw=result.total_rows_raw,
            total_rows_curated=result.total_rows_curated,
            quality_gate_status=result.quality_gate_status.value,
            errors=result.errors,
            warnings=result.warnings,
        )
    finally:
        # Cleanup temp file
        tmp_path.unlink(missing_ok=True)


class IngestByPathRequest(BaseModel):
    """Dev-friendly: ingest a local file by absolute path (skips multipart)."""
    path: str = Field(..., description="Absolute path to the XLSX file")
    auto_activate: bool = Field(default=False)
    user: str = Field(default="api_user")


@router.post(
    "/ingest-by-path",
    response_model=IngestResponse,
    summary="Ingest Excel file by absolute path (dev)",
    description=(
        "Trigger ingestion against a file already on disk. Avoids the multipart "
        "upload round-trip for large files (e.g. Folha_IA_extra.xlsx ~57 MB)."
    ),
)
async def ingest_by_path(
    request: IngestByPathRequest,
    engine: IngestEngine = Depends(get_engine),
):
    """
    Dev-only convenience: ingest by absolute path.

    Validates the path exists and is an XLSX. Calls the same IngestEngine
    pipeline as the upload endpoint — result shape is identical.

    Onda 5.4 — path-traversal guard. The user-supplied path is restricted
    to an allowlist of roots (env-configurable via PRODPLAN_INGEST_ROOTS,
    comma-separated; defaults to the workspace root). Without this, an
    attacker could read arbitrary disk paths by submitting e.g.
    `/etc/passwd` (parser.py would still reject non-XLSX, but the file
    would be opened to read the magic bytes — info leak via timing).
    """
    import os
    from pathlib import Path

    raw_path = Path(request.path)
    if not raw_path.is_absolute():
        raise HTTPException(
            status_code=400, detail="path must be absolute",
        )
    # Resolve to canonical form before any check (defeats `..` traversal).
    try:
        path = raw_path.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=400, detail=f"File not found: {raw_path}")

    if path.suffix.lower() not in (".xlsx", ".xls"):
        raise HTTPException(
            status_code=400, detail="Only .xlsx/.xls files are accepted",
        )

    # Allowlist: PRODPLAN_INGEST_ROOTS env var (comma-separated absolute
    # paths). Default to the workspace's `data/` dir + the workspace root
    # itself for dev convenience.
    workspace = Path(__file__).resolve().parents[3]
    default_roots = [str(workspace), str(workspace / "data")]
    roots_env = os.environ.get("PRODPLAN_INGEST_ROOTS", "")
    raw_roots = [r.strip() for r in roots_env.split(",") if r.strip()]
    allowed_roots = [Path(r).resolve() for r in (raw_roots or default_roots)]
    if not any(_is_under(path, root) for root in allowed_roots):
        raise HTTPException(
            status_code=403,
            detail=(
                "path is outside the configured ingest roots; set "
                "PRODPLAN_INGEST_ROOTS to permit additional locations"
            ),
        )

    result = engine.ingest(
        file_path=path,
        source_type=SourceType.UPLOAD,
        created_by=request.user,
        auto_activate=request.auto_activate,
    )

    return IngestResponse(
        success=result.success,
        ingestion_id=str(result.ingestion_id) if result.ingestion_id else None,
        status=result.status.value,
        is_duplicate=result.is_duplicate,
        duplicate_of=str(result.duplicate_of) if result.duplicate_of else None,
        total_rows_raw=result.total_rows_raw,
        total_rows_curated=result.total_rows_curated,
        quality_gate_status=result.quality_gate_status.value,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post(
    "/activate/{ingestion_id}",
    summary="Activate ingestion",
    description="Activate an ingestion run as the current data.",
)
async def activate_ingestion(
    ingestion_id: str,
    request: ActivateRequest,
    x_tenant_id: Optional[UUID] = Header(None, alias="X-Tenant-Id"),
    engine: IngestEngine = Depends(get_engine),
):
    """Activate an ingestion (+ emit drift alert if schema changed)."""
    try:
        uid = UUID(ingestion_id)
        success = engine.activate(uid, request.user)

        alert_id: Optional[str] = None
        if success:
            alert_id = await _emit_drift_alert_safe(engine, uid, x_tenant_id)

        return {
            "success": success,
            "activated_ingestion_id": ingestion_id,
            "activated_by": request.user,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "drift_alert_id": alert_id,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _emit_drift_alert_safe(
    engine: IngestEngine,
    ingestion_id: UUID,
    tenant_id: Optional[UUID] = None,
) -> Optional[str]:
    """
    Best-effort drift alert emission. Failure to create an alert must not
    break activation itself — we log and return None.

    Onda 1.8 — `tenant_id` is now read from the X-Tenant-Id header instead
    of the hardcoded zero UUID. Without a header we skip emission entirely
    rather than route the alert to a phantom tenant.
    """
    if tenant_id is None:
        logger.warning(
            "Drift alert skipped for ingestion %s: no X-Tenant-Id provided",
            ingestion_id,
        )
        return None
    try:
        from src.factory_data_product.drift_bridge import emit_drift_alert_if_any
        from src.shared.database import get_session_context

        history = engine.get_schema_history()
        async with get_session_context() as session:
            alert_id = await emit_drift_alert_if_any(
                session, tenant_id, ingestion_id, history,
            )
            await session.commit()
            return alert_id
    except Exception as e:
        logger.warning(
            f"Drift alert emission failed for ingestion {ingestion_id}: {e}"
        )
        return None


# ============================================================================
# Watcher status (Sprint J.2)
# ============================================================================

@router.get(
    "/watcher/status",
    summary="Factory data watcher status",
    description="Inspect the periodic file watcher (hash-change → ingest).",
)
async def get_watcher_status():
    """Report the watcher's last seen hash + any error."""
    from src.factory_data_product.watcher import get_state, _resolve_watch_path

    state = get_state()
    path = _resolve_watch_path()
    return {
        "enabled": path is not None,
        "watch_path": str(path) if path else None,
        "last_hash": state.last_hash,
        "last_ingestion_id": state.last_ingestion_id,
        "last_error": state.last_error,
    }


@router.post(
    "/rollback",
    summary="Rollback to previous ingestion",
    description="Rollback to a previous ingestion (logical, not physical).",
)
async def rollback_ingestion(
    request: RollbackRequest,
    engine: IngestEngine = Depends(get_engine),
):
    """
    Rollback to a previous ingestion.
    
    This is a LOGICAL rollback — just swapping active_ingestion_id.
    No data is deleted.
    """
    try:
        uid = UUID(request.to_ingestion_id)
        success = engine.rollback(uid, request.user, request.reason)
        
        return {
            "success": success,
            "rolled_back_to": request.to_ingestion_id,
            "reason": request.reason,
            "rolled_back_by": request.user,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# SEMANTIC QUERY ENDPOINTS (Real Data)
# ============================================================================

class SemanticQueryResponse(BaseModel):
    """Standard response for semantic queries."""
    
    data: Optional[Dict[str, Any]] = None
    data_confidence: float = Field(..., description="Trust score 0-100")
    trust_status: str = Field(..., description="OK | WARNING | BLOCKED")
    semantic_label: str = Field(..., description="Human-readable disclaimer")
    metadata: Dict[str, Any] = Field(default_factory=dict)


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


# ============================================================================
# BLOCKED METRICS ENDPOINT
# ============================================================================

@router.get(
    "/semantic/blocked-metrics",
    summary="Get Blocked Metrics",
    description="List metrics that cannot be calculated with current data.",
    tags=["factory", "semantic-queries"],
)
async def get_blocked_metrics():
    """
    Get list of blocked metrics.
    
    These metrics cannot be calculated because required data is missing.
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


# ============================================================================
# TRUST HEATMAP ENDPOINT (P2 Enterprise)
# ============================================================================

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


# ============================================================================
# QUARANTINE ENDPOINTS
# ============================================================================

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
