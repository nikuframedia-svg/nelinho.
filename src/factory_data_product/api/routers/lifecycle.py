"""
Factory lifecycle endpoints — `/v1/factory/activate/*`, `/v1/factory/rollback` (Q.66.D.4b).
============================================================================================

- POST /activate/{ingestion_id}
- POST /rollback
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.factory_data_product.api.routers._deps import get_engine
from src.factory_data_product.ingest import IngestEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["factory"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ActivateRequest(BaseModel):
    """Request to activate an ingestion."""

    user: str = Field(default="api_user", description="User performing activation")


class RollbackRequest(BaseModel):
    """Request to rollback."""

    to_ingestion_id: str
    reason: str = Field(..., min_length=10)
    user: str = Field(default="api_user")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
