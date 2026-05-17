"""
ProdPlan ONE - Mold Maintenance API (Sprint R.6)
=================================================

Endpoints under `/v1/molds/*`:

    GET    /v1/molds/                        — list
    POST   /v1/molds/                        — create
    GET    /v1/molds/{id}                    — detail + latest health
    POST   /v1/molds/{id}/maintenance        — plan / start / complete
    GET    /v1/molds/calendar                — planned events
    GET    /v1/molds/health-report           — red-flagged molds
    POST   /v1/molds/scan-alerts             — emit MOLD_MAINT_DUE alerts
    POST   /v1/molds/propose-preventive      — create PLANNED events for reds
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.mold import Mold, MoldHealth, MoldMaintenanceEvent
from src.plan.services.mold_service import MoldNotFoundError, MoldService
from src.shared.database import get_session

router = APIRouter(tags=["Molds"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


class MoldCreateRequest(BaseModel):
    mold_code: str
    model_id: str
    pocket_count: int = 1
    expected_life_cycles: Optional[int] = None
    name: Optional[str] = None


class PlanMaintenanceRequest(BaseModel):
    planned_date: date
    maintenance_type: str = "preventive"
    technician_id: Optional[UUID] = None
    comments: Optional[str] = None


class CompleteMaintenanceRequest(BaseModel):
    actual_duration_h: Optional[float] = None
    parts_cost_eur: Optional[float] = None
    labor_cost_eur: Optional[float] = None
    defects_fixed: list[str] = []


def _mold_to_dict(mold: Mold, health: Optional[MoldHealth] = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(mold.id),
        "mold_code": mold.mold_code,
        "model_id": mold.model_id,
        "name": mold.name,
        "pocket_count": mold.pocket_count,
        "expected_life_cycles": mold.expected_life_cycles,
        "active": mold.active,
        "depreciated": mold.depreciated,
    }
    if health is not None:
        data["health"] = {
            "score_0_100": health.score_0_100,
            "risk_category": health.risk_category,
            "assessed_at": health.assessed_at.isoformat() if health.assessed_at else None,
            "components": health.components,
        }
    return data


def _event_to_dict(event: MoldMaintenanceEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "mold_id": str(event.mold_id),
        "maintenance_type": event.maintenance_type,
        "planned_date": event.planned_date.isoformat() if event.planned_date else None,
        "started_at": event.started_at.isoformat() if event.started_at else None,
        "completed_at": event.completed_at.isoformat() if event.completed_at else None,
        "status": event.status,
        "actual_duration_h": float(event.actual_duration_h) if event.actual_duration_h else None,
        "parts_cost_eur": float(event.parts_cost_eur) if event.parts_cost_eur else None,
        "labor_cost_eur": float(event.labor_cost_eur) if event.labor_cost_eur else None,
        "comments": event.comments,
    }


@router.get("/molds/")
async def list_molds(
    active_only: bool = True,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    molds = await svc.list_molds(active_only=active_only)
    return [_mold_to_dict(m) for m in molds]


@router.post("/molds/", status_code=status.HTTP_201_CREATED)
async def create_mold(
    req: MoldCreateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    try:
        mold = await svc.create_mold(**req.model_dump())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _mold_to_dict(mold)


@router.get("/molds/calendar")
async def mold_calendar(
    since: Optional[date] = Query(None),
    until: Optional[date] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    from datetime import timedelta
    since = since or date.today()
    until = until or (since + timedelta(days=30))
    svc = MoldService(session, tenant_id)
    events = await svc.calendar(since=since, until=until)
    return [_event_to_dict(e) for e in events]


@router.get("/molds/health-report")
async def mold_health_report(
    limit: int = Query(25, ge=1, le=500),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    molds = await svc.list_molds()
    results: list[dict[str, Any]] = []
    for mold in molds:
        health = await svc.latest_health(mold.id)
        results.append(_mold_to_dict(mold, health))
    # Reds first, then yellows, then greens.
    rank = {"red": 0, "yellow": 1, "green": 2, None: 3}
    results.sort(key=lambda d: (
        rank.get((d.get("health") or {}).get("risk_category"), 3),
        (d.get("health") or {}).get("score_0_100") or 100,
    ))
    return results[:limit]


@router.post("/molds/scan-alerts")
async def mold_scan_alerts(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    created = await svc.emit_maintenance_alerts()
    return {"alerts_created": created}


@router.post("/molds/propose-preventive")
async def mold_propose_preventive(
    horizon_days: int = Query(14, ge=1, le=180),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    events = await svc.propose_preventive_schedule(horizon_days=horizon_days)
    return {"events_proposed": len(events), "events": [_event_to_dict(e) for e in events]}


@router.get("/molds/{mold_id}")
async def get_mold(
    mold_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    try:
        mold = await svc.get_mold(mold_id)
    except MoldNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Mold {mold_id} not found")
    health = await svc.latest_health(mold.id)
    return _mold_to_dict(mold, health)


@router.post("/molds/{mold_id}/recompute-health")
async def recompute_health(
    mold_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    try:
        mold = await svc.get_mold(mold_id)
    except MoldNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Mold {mold_id} not found")
    health = await svc.recompute_health(mold)
    return {
        "score_0_100": health.score_0_100,
        "risk_category": health.risk_category,
        "components": health.components,
    }


@router.get("/molds/{mold_id}/maintenance")
async def list_mold_maintenance(
    mold_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.31.B — eventos de manutenção de um molde (planeado/em curso/feito)."""
    svc = MoldService(session, tenant_id)
    events = await svc.list_maintenance(mold_id)
    return [_event_to_dict(e) for e in events]


@router.post("/molds/{mold_id}/maintenance", status_code=status.HTTP_201_CREATED)
async def plan_mold_maintenance(
    mold_id: UUID,
    req: PlanMaintenanceRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    try:
        await svc.get_mold(mold_id)
    except MoldNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Mold {mold_id} not found")
    event = await svc.plan_maintenance(mold_id=mold_id, **req.model_dump())
    return _event_to_dict(event)


@router.post("/molds/maintenance/{event_id}/start")
async def start_mold_maintenance(
    event_id: UUID,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    try:
        event = await svc.start_maintenance(event_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _event_to_dict(event)


@router.post("/molds/maintenance/{event_id}/complete")
async def complete_mold_maintenance(
    event_id: UUID,
    req: CompleteMaintenanceRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = MoldService(session, tenant_id)
    try:
        event = await svc.complete_maintenance(
            event_id=event_id,
            actual_duration_h=Decimal(str(req.actual_duration_h)) if req.actual_duration_h else None,
            parts_cost_eur=Decimal(str(req.parts_cost_eur)) if req.parts_cost_eur else None,
            labor_cost_eur=Decimal(str(req.labor_cost_eur)) if req.labor_cost_eur else None,
            defects_fixed=req.defects_fixed,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _event_to_dict(event)
