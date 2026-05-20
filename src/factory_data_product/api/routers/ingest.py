"""
Factory ingest endpoints — `/v1/factory/ingest*` (Q.66.D.4b).
=============================================================

- POST /ingest          (multipart upload, 100 MB cap)
- POST /ingest-by-path  (dev: by absolute path, allowlist-guarded)
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from src.factory_data_product.api.routers._deps import get_engine
from src.factory_data_product.ingest import IngestEngine
from src.factory_data_product.models.meta import SourceType


router = APIRouter(tags=["factory"])


# ---------------------------------------------------------------------------
# Response/request models
# ---------------------------------------------------------------------------


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


class IngestByPathRequest(BaseModel):
    """Dev-friendly: ingest a local file by absolute path (skips multipart)."""

    path: str = Field(..., description="Absolute path to the XLSX file")
    auto_activate: bool = Field(default=False)
    user: str = Field(default="api_user")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
    workspace = Path(__file__).resolve().parents[4]
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
