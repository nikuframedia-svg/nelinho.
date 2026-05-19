"""
ProdPlan ONE - Quality API (Sprint R.1/R.3/R.4/R.5/R.7/R.8)
=============================================================

Endpoints under `/v1/quality/*`:

    POST   /rework                         — record a ReworkEntry
    GET    /rework                         — list rework events
    PATCH  /rework/{id}/resolve            — mark resolved
    GET    /workers/ranking                — QA08 objective error-rate ranking
    GET    /dashboard                      — QA05 rework dashboards by dimension
    GET    /root-cause                     — QA09 statistical correlations
    GET    /impact                         — QA03 cumulative impact per error
    GET    /rework/cost-summary            — Q.37.A factory-wide rework € rollup
    GET    /quality/by-supplier            — QA04 / O.8 supplier quality analytics
    GET    /quality/by-lot                 — QA04 lot-level quality
    GET    /defect-zones                   — F11 / Q.46.B defect-by-zone hull map
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.services.dashboard_service import QualityDashboardService
from src.quality.services.defect_zone_service import DefectZoneService
from src.quality.services.impact_service import ImpactService
from src.quality.services.rework_service import (
    ReworkNotFoundError,
    ReworkService,
)
from src.quality.services.root_cause_analyzer import RootCauseAnalyzer
from src.quality.services.supplier_quality_service import SupplierQualityService
from src.quality.services.worker_ranking_service import WorkerRankingService
from src.shared.database import get_session

router = APIRouter(prefix="/v1/quality", tags=["Quality"])


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


# ─── Schemas ──────────────────────────────────────────────────────────────

class ReworkCreateRequest(BaseModel):
    of_id: str
    error_code: str
    detected_at: datetime
    original_op_id: Optional[str] = None
    rework_op_id: Optional[str] = None
    model_id: Optional[str] = None
    causer_employee_id: Optional[UUID] = None
    chefe_employee_id: Optional[UUID] = None
    phase_id_causer: Optional[str] = None
    phase_id_rework: Optional[str] = None
    error_description: Optional[str] = None
    root_cause_category: Optional[str] = None
    mold_id: Optional[str] = None
    material_lot_id: Optional[str] = None
    supplier_id: Optional[UUID] = None
    detected_by: Optional[str] = None
    cost_estimate_eur: Optional[float] = None
    hours_lost: Optional[float] = None
    context: Optional[dict] = None
    notes: Optional[str] = None


def _rework_to_dict(row) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "of_id": row.of_id,
        "error_code": row.error_code,
        "error_description": row.error_description,
        "phase_id_causer": row.phase_id_causer,
        "phase_id_rework": row.phase_id_rework,
        "causer_employee_id": str(row.causer_employee_id) if row.causer_employee_id else None,
        "chefe_employee_id": str(row.chefe_employee_id) if row.chefe_employee_id else None,
        "mold_id": row.mold_id,
        "material_lot_id": row.material_lot_id,
        "supplier_id": str(row.supplier_id) if row.supplier_id else None,
        "detected_at": row.detected_at.isoformat() if row.detected_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "cost_estimate_eur": float(row.cost_estimate_eur) if row.cost_estimate_eur else None,
        "hours_lost": float(row.hours_lost) if row.hours_lost else None,
        "route_to_causer": ReworkService.should_route_to_causer(row.phase_id_rework),
    }


# ─── R.1 — Rework CRUD ────────────────────────────────────────────────────

@router.post("/rework", status_code=status.HTTP_201_CREATED)
async def create_rework(
    req: ReworkCreateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = ReworkService(session, tenant_id)
    kwargs = req.model_dump()
    if kwargs.get("cost_estimate_eur") is not None:
        kwargs["cost_estimate_eur"] = Decimal(str(kwargs["cost_estimate_eur"]))
    if kwargs.get("hours_lost") is not None:
        kwargs["hours_lost"] = Decimal(str(kwargs["hours_lost"]))
    row = await svc.record(**kwargs)
    return _rework_to_dict(row)


@router.get("/rework")
async def list_rework(
    of_id: Optional[str] = None,
    phase_id: Optional[str] = None,
    mold_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = ReworkService(session, tenant_id)
    rows = await svc.list_rework(
        of_id=of_id, phase_id=phase_id, mold_id=mold_id,
        since=since, until=until, limit=limit,
    )
    return [_rework_to_dict(r) for r in rows]


@router.patch("/rework/{rework_id}/resolve")
async def resolve_rework(
    rework_id: UUID,
    resolved_by: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = ReworkService(session, tenant_id)
    try:
        row = await svc.resolve(rework_id=rework_id, resolved_by=resolved_by)
    except ReworkNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Rework {rework_id} not found",
        )
    return _rework_to_dict(row)


# ─── R.3 — Worker ranking ─────────────────────────────────────────────────

@router.get("/workers/ranking")
async def worker_ranking(
    phase_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = WorkerRankingService(session, tenant_id)
    items = await svc.ranking(
        since=since, until=until, phase_id=phase_id, limit=limit,
    )
    return {"items": items, "count": len(items)}


# ─── R.4 — Dashboard ──────────────────────────────────────────────────────

@router.get("/dashboard")
async def quality_dashboard(
    group_by: str = Query("phase", description="operator|phase|sku|shift"),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = 25,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = QualityDashboardService(session, tenant_id)
    try:
        return await svc.group_by(
            group_by=group_by, since=since, until=until, top_n=top_n,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─── Sprint Q.5 — First-pass yield (CEO dashboard tile) ──────────────────

@router.get("/first-pass-yield")
async def first_pass_yield(
    window_days: int = Query(30, ge=1, le=365),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """% of completed orders with zero rework events in the window.

    Plan v4 §9. Reuses `DashboardMetricsService` from the profit module
    so the same definition is used by both /v1/profit/dashboard and
    here — single source of truth.
    """
    from src.profit.services.dashboard_metrics_service import (
        DashboardMetricsService,
    )

    svc = DashboardMetricsService(session, tenant_id)
    result = await svc.first_pass_yield(window_days=window_days)
    return result.to_dict()


# ─── R.5 — Root-cause ─────────────────────────────────────────────────────

@router.get("/root-cause")
async def root_cause(
    error_code: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n_per_dimension: int = 5,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = RootCauseAnalyzer(session, tenant_id)
    return await svc.analyse(
        error_code=error_code, since=since, until=until,
        top_n_per_dimension=top_n_per_dimension,
    )


# ─── R.7 — Impact ─────────────────────────────────────────────────────────

@router.get("/impact")
async def impact_analysis(
    error_code: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = ImpactService(session, tenant_id)
    return await svc.impact_by_error(
        error_code=error_code, since=since, until=until,
    )


# ─── Q.37.A — Rework cost summary (CEO €) ─────────────────────────────────

@router.get("/rework/cost-summary")
async def rework_cost_summary(
    group_by: Optional[str] = Query(
        None, description="error_code|phase|model|of_id",
    ),
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = Query(20, ge=1, le=200),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Custo total de retrabalho em € no período (factory-wide).

    Responde "quanto custou o retrabalho" — total €, horas perdidas,
    ordens afectadas, e `cost_coverage_pct` (a fracção dos eventos com €
    real estimado; baixa cobertura = o total é uma subcontagem). Com
    `group_by` dá o breakdown por erro, fase, modelo ou ordem.
    """
    svc = ImpactService(session, tenant_id)
    try:
        return await svc.cost_summary(
            group_by=group_by, since=since, until=until, top_n=top_n,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─── R.8 — Supplier / Lot quality ─────────────────────────────────────────

@router.get("/by-supplier")
async def quality_by_supplier(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = 20,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = SupplierQualityService(session, tenant_id)
    items = await svc.by_supplier(since=since, until=until, top_n=top_n)
    return {"items": items, "count": len(items)}


@router.get("/by-lot")
async def quality_by_lot(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = 20,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    svc = SupplierQualityService(session, tenant_id)
    items = await svc.by_lot(since=since, until=until, top_n=top_n)
    return {"items": items, "count": len(items)}


# ─── F11 / Q.46.B — Defect-by-zone hull map ───────────────────────────────

@router.get("/defect-zones")
async def defect_zones(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = Query(25, ge=1, le=200),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Mapa de defeitos do barco por zona do casco (F11).

    Heatmap / Pareto de retrabalho por zona — responde "onde no barco a
    fábrica falha". `zone_coverage_pct` é o sinal de honestidade: a
    fracção dos eventos com zona marcada (`OFCH_LOCAL`); cobertura baixa
    = o Pareto é parcial, não um facto.
    """
    svc = DefectZoneService(session, tenant_id)
    return await svc.zone_map(since=since, until=until, top_n=top_n)
