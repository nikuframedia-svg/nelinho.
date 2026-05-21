"""
Factory data watcher status — `/v1/factory/watcher/*` (Q.66.D.4b).
==================================================================

- GET /watcher/status
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(tags=["factory"])


@router.get(
    "/watcher/status",
    summary="Factory data watcher status",
    description="Inspect the periodic file watcher (hash-change → ingest).",
)
async def get_watcher_status():
    """Report the watcher's last seen hash + any error."""
    from src.factory_data_product.watcher import _resolve_watch_path, get_state

    state = get_state()
    path = _resolve_watch_path()
    return {
        "enabled": path is not None,
        "watch_path": str(path) if path else None,
        "last_hash": state.last_hash,
        "last_ingestion_id": state.last_ingestion_id,
        "last_error": state.last_error,
    }
