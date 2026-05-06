"""
ProdPlan ONE - Copilot Alerts API (`/v1/copilot/alerts`).

Exposes the proactive alerts raised by `AlertsEngine` and lets users
acknowledge/resolve them. Follows the newer `/v1` convention rather than
reusing the legacy `/api/copilot` prefix.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.alerts.engine import AlertsEngine
from src.copilot.alerts.models import (
    STATUS_ACKNOWLEDGED,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
    CopilotAlert,
)
from src.shared.database import get_session

router = APIRouter(prefix="/v1/copilot", tags=["Copilot Alerts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    id: str
    severity: str
    code: str
    title: str
    message_pt: str
    context: Dict[str, Any]
    entity_refs: List[str]
    status: str
    created_at: Optional[str]
    acknowledged_at: Optional[str]
    acknowledged_by: Optional[str]
    resolved_at: Optional[str]


class ScanResponse(BaseModel):
    created: int
    skipped_duplicate: int
    detectors_run: int


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

from src.shared.auth.headers import require_tenant_header, require_user_header

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID/'api_user' defaults.
_tenant_id = require_tenant_header
_user_id = require_user_header


def _serialize(alert: CopilotAlert) -> AlertResponse:
    return AlertResponse(
        id=str(alert.id),
        severity=alert.severity,
        code=alert.code,
        title=alert.title,
        message_pt=alert.message_pt,
        context=alert.context or {},
        entity_refs=list(alert.entity_refs or []),
        status=alert.status,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
        acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(
    status_filter: Optional[str] = Query(
        default=STATUS_ACTIVE,
        alias="status",
        description="active | acknowledged | resolved | all",
    ),
    severity: Optional[str] = Query(default=None, description="INFO | WARN | CRITICAL"),
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(CopilotAlert).where(CopilotAlert.tenant_id == tenant_id)
    if status_filter and status_filter != "all":
        stmt = stmt.where(CopilotAlert.status == status_filter)
    if severity:
        stmt = stmt.where(CopilotAlert.severity == severity)
    stmt = stmt.order_by(CopilotAlert.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return [_serialize(a) for a in result.scalars().all()]


@router.post("/alerts/scan", response_model=ScanResponse)
async def trigger_scan(
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Run every detector immediately. Normally the background scheduler does this."""
    engine = AlertsEngine(session=db, tenant_id=tenant_id)
    summary = await engine.scan()
    return ScanResponse(**summary)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: UUID,
    tenant_id: UUID = Depends(_tenant_id),
    user: str = Depends(_user_id),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(CopilotAlert).where(
        and_(CopilotAlert.id == alert_id, CopilotAlert.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = STATUS_ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = user
    await db.flush()
    return _serialize(alert)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    tenant_id: UUID = Depends(_tenant_id),
    user: str = Depends(_user_id),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(CopilotAlert).where(
        and_(CopilotAlert.id == alert_id, CopilotAlert.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.status = STATUS_RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    if not alert.acknowledged_by:
        alert.acknowledged_by = user
        alert.acknowledged_at = datetime.now(timezone.utc)
    await db.flush()
    return _serialize(alert)


# ---------------------------------------------------------------------------
# Shift report (Sprint C.2)
# ---------------------------------------------------------------------------

class ShiftReportResponse(BaseModel):
    tenant_id: str
    window_hours: int
    generated_at: str
    summary: Dict[str, Any]
    highlights: List[Dict[str, Any]]
    new_alerts: List[AlertResponse]
    semantic_snapshot: Dict[str, Any]


@router.post("/shift-report", response_model=ShiftReportResponse)
async def shift_report(
    window_hours: int = Query(default=8, ge=1, le=48),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """
    Deterministic shift handover report.

    Assembles, for the previous `window_hours`:
    - Summary counters (active/new alerts by severity).
    - Highlights (top WIP / bottleneck / skills risk from semantic layer).
    - New alerts raised in the window.
    - Current semantic snapshot (WIP, backlog, bottlenecks, skills, quality).

    No LLM synthesis — kept deterministic for auditability and so it works
    offline. Can be wrapped in LLM-sumarisation later.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    # New alerts in the window
    alerts_stmt = (
        select(CopilotAlert)
        .where(
            and_(
                CopilotAlert.tenant_id == tenant_id,
                CopilotAlert.created_at >= since,
            )
        )
        .order_by(CopilotAlert.created_at.desc())
        .limit(50)
    )
    alerts_result = await db.execute(alerts_stmt)
    new_alerts: List[CopilotAlert] = list(alerts_result.scalars().all())

    severity_counts = {"INFO": 0, "WARN": 0, "CRITICAL": 0}
    status_counts = {STATUS_ACTIVE: 0, STATUS_ACKNOWLEDGED: 0, STATUS_RESOLVED: 0}
    for a in new_alerts:
        if a.severity in severity_counts:
            severity_counts[a.severity] += 1
        if a.status in status_counts:
            status_counts[a.status] += 1

    # Semantic snapshot (best-effort)
    snapshot: Dict[str, Any] = {}
    highlights: List[Dict[str, Any]] = []
    try:
        from src.factory_data_product.services.semantic_queries_inmemory import (
            SemanticQueriesInMemory,
        )
        sq = SemanticQueriesInMemory()

        def _q(name: str, **kw) -> Optional[Dict[str, Any]]:
            try:
                r = getattr(sq, name)(**kw)
                if r and r.get("status") != "BLOCKED":
                    return r
            except Exception as exc:
                # Sprint Q.7 Fase 4 — was bare `pass`. Best-effort query;
                # log under DEBUG so the failure is visible without spam.
                logger.debug("alert _q(%s) failed: %s", name, exc)
            return None

        wip = _q("get_wip")
        bottlenecks = _q("get_bottlenecks")
        skills = _q("get_skills_risk", min_capable=2)
        quality = _q("get_quality")

        snapshot = {
            "wip_rows": len((wip or {}).get("rows", [])) if wip else None,
            "bottleneck_rows": len((bottlenecks or {}).get("rows", [])) if bottlenecks else None,
            "skills_risk_rows": len((skills or {}).get("rows", [])) if skills else None,
            "quality_events_total": sum(
                int(r.get("total_erros", 0) or 0)
                for r in (quality or {}).get("rows", [])
            ) if quality else None,
        }

        if bottlenecks and bottlenecks.get("rows"):
            top = bottlenecks["rows"][:3]
            highlights.extend(
                {
                    "kind": "bottleneck",
                    "fase": r.get("fase_nome"),
                    "backlog_dias": r.get("backlog_dias"),
                }
                for r in top
            )
        if skills and skills.get("rows"):
            top = skills["rows"][:3]
            highlights.extend(
                {
                    "kind": "spof",
                    "fase": r.get("fase_nome"),
                    "capable": r.get("num_funcionarios_aptos", r.get("capable_count")),
                }
                for r in top
            )
    except Exception:
        snapshot = {"error": "semantic layer unavailable"}

    return ShiftReportResponse(
        tenant_id=str(tenant_id),
        window_hours=window_hours,
        generated_at=datetime.now(timezone.utc).isoformat(),
        summary={
            "alerts_by_severity": severity_counts,
            "alerts_by_status": status_counts,
            "alerts_total": len(new_alerts),
        },
        highlights=highlights,
        new_alerts=[_serialize(a) for a in new_alerts[:10]],
        semantic_snapshot=snapshot,
    )
