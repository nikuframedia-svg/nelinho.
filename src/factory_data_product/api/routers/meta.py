"""
Factory meta endpoints — `/v1/factory/meta/*` (Q.66.D.4b).
==========================================================

- GET /meta/active-run
- GET /meta/quality-report/{ingestion_id}
- GET /meta/schema-drift
- GET /meta/schema-history
- GET /meta/ingestions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.factory_data_product.api.routers._deps import get_engine
from src.factory_data_product.ingest import IngestEngine


router = APIRouter(tags=["factory"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
