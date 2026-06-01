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
    GET    /quality/by-supplier            — QA04 / O.8 supplier quality analytics
    GET    /quality/by-lot                 — QA04 lot-level quality

Q.61.32c — migrados de /api/errors* (legacy):
    GET    /v1/quality/errors              — paginated production errors
    GET    /v1/quality/errors/stats        — aggregate by severity/phase/desc
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models import ProductionError  # Q.61.32d
from src.quality.models.runbook import ErrorTypeRunbookLink, Runbook
from src.quality.services.dashboard_service import QualityDashboardService
from src.quality.services.impact_service import (
    ImpactService,
    most_frequent_error_code,
)
from src.quality.services.rework_service import (
    ReworkNotFoundError,
    ReworkService,
)
from src.quality.services.root_cause_analyzer import RootCauseAnalyzer
from src.quality.services.supplier_quality_service import SupplierQualityService
from src.quality.services.worker_ranking_service import WorkerRankingService
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

logger = logging.getLogger(__name__)

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


async def _resolve_phase_names(
    session: AsyncSession, tenant_id: UUID, phase_ids: set[str]
) -> dict[str, str]:
    """Mapa phase_id → phase_name (resolver canónico = routing_template_phase).

    Q.154.D — mesmo padrão de ``entity_summary`` (top_phases). Devolve só os que
    resolvem; quem chama faz fallback ao phase_id cru. Ignora None/vazios.
    """
    from src.plan.models.routing_template import RoutingTemplatePhase

    ids = {p for p in phase_ids if p}
    if not ids:
        return {}
    stmt = select(RoutingTemplatePhase.phase_id, RoutingTemplatePhase.phase_name).where(
        and_(
            RoutingTemplatePhase.tenant_id == tenant_id,
            RoutingTemplatePhase.phase_id.in_(ids),
        )
    )
    out: dict[str, str] = {}
    for pid, pname in (await session.execute(stmt)).all():
        if pid not in out and pname:
            out[pid] = pname
    return out


def _rework_to_dict(row, phase_names: dict[str, str] | None = None) -> dict[str, Any]:
    names = phase_names or {}
    return {
        "id": str(row.id),
        "of_id": row.of_id,
        "error_code": row.error_code,
        "error_description": row.error_description,
        "phase_id_causer": row.phase_id_causer,
        "phase_id_rework": row.phase_id_rework,
        # Q.154.D — nomes humanos das fases (None = sem hit no routing → FE usa id).
        "phase_name_causer": names.get(row.phase_id_causer) if row.phase_id_causer else None,
        "phase_name_rework": names.get(row.phase_id_rework) if row.phase_id_rework else None,
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
    names = await _resolve_phase_names(
        session, tenant_id, {row.phase_id_causer, row.phase_id_rework}
    )
    return _rework_to_dict(row, names)


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
    phase_ids: set[str] = set()
    for r in rows:
        phase_ids.update({r.phase_id_causer, r.phase_id_rework})
    names = await _resolve_phase_names(session, tenant_id, phase_ids)
    return [_rework_to_dict(r, names) for r in rows]


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
    names = await _resolve_phase_names(
        session, tenant_id, {row.phase_id_causer, row.phase_id_rework}
    )
    return _rework_to_dict(row, names)


# ─── Q.54.S — qualidade dos moldes (camada curada) ────────────────────────

@router.get("/molds")
async def list_mold_quality(
    limit: int = Query(60, ge=1, le=510),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Moldes reais com o seu histórico de defeitos.

    Junta o master curado (``factory_curated.mold``, 510 moldes) com os
    eventos de qualidade (``quality_event``), agregados por molde e
    ordenados pelos que mais defeitos causam.

    Distinto de ``/v1/plan/molds/*`` — esse serve o catálogo de
    planeamento (``plan.mold``), num espaço de IDs (``MLD_ID``) que não
    casa com os dados de defeitos. Este expõe os moldes que a fábrica
    realmente usou, keyed por ``molde_id`` — o mesmo das tabelas de
    qualidade. Read-only.
    """
    from sqlalchemy import desc, func, select

    from src.factory_data_product.models.curated import (
        CuratedMold,
        CuratedQualityEvent,
    )

    stmt = (
        select(
            CuratedMold.molde_id,
            CuratedMold.molde_nome,
            CuratedMold.tipo,
            CuratedMold.em_manutencao,
            func.count(CuratedQualityEvent.id).label("defect_events"),
            func.coalesce(
                func.sum(CuratedQualityEvent.quantidade), 0
            ).label("defect_qty"),
            func.max(CuratedQualityEvent.data_evento).label("last_defect"),
        )
        .select_from(CuratedMold)
        .join(
            CuratedQualityEvent,
            CuratedQualityEvent.molde_id == CuratedMold.molde_id,
            isouter=True,
        )
        .group_by(
            CuratedMold.molde_id,
            CuratedMold.molde_nome,
            CuratedMold.tipo,
            CuratedMold.em_manutencao,
        )
        .order_by(desc("defect_qty"), desc("defect_events"))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "molde_id": r[0],
            "nome": r[1],
            "tipo": r[2],
            "em_manutencao": bool(r[3]),
            "defect_events": int(r[4] or 0),
            "defect_qty": int(r[5] or 0),
            "last_defect": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


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
    error_code: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n_per_dimension: int = 5,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """QA09 — causa-raiz por dimensão para um `error_code`.

    Quando `error_code` é omitido, usa o defeito mais frequente da janela
    (`most_frequent_error_code`) — a tab Diagnóstico nunca abre partida.
    Devolve `error_code: None` + dimensões vazias quando não há retrabalho.
    """
    if not error_code:
        error_code = await most_frequent_error_code(
            session, tenant_id, since=since, until=until
        )
    if not error_code:
        return {
            "error_code": None,
            "dimensions": {},
            "total_events": 0,
            "reason": "Sem retrabalho registado na janela.",
        }
    svc = RootCauseAnalyzer(session, tenant_id)
    return await svc.analyse(
        error_code=error_code, since=since, until=until,
        top_n_per_dimension=top_n_per_dimension,
    )


# ─── R.7 — Impact ─────────────────────────────────────────────────────────

@router.get("/impact")
async def impact_analysis(
    error_code: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """QA03 — impacto cumulativo (€, horas) de um `error_code`.

    Quando `error_code` é omitido, usa o defeito mais frequente da janela.
    Devolve `error_code: None` + zeros quando não há retrabalho.
    """
    if not error_code:
        error_code = await most_frequent_error_code(
            session, tenant_id, since=since, until=until
        )
    if not error_code:
        return {
            "error_code": None,
            "events": 0,
            "affected_orders": 0,
            "cost_estimate_eur": 0.0,
            "hours_lost": 0.0,
            "share_pct_of_total_rework": 0.0,
            "reason": "Sem retrabalho registado na janela.",
        }
    svc = ImpactService(session, tenant_id)
    return await svc.impact_by_error(
        error_code=error_code, since=since, until=until,
    )


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


# ─── Q.53.A — ML defect risk + hull zones + ROI (Qualidade page tabs) ─────

@router.get("/risk-preview")
async def risk_preview(
    operator_id: Optional[str] = Query(None, description="ID do operador"),
    phase_id: Optional[str] = Query(None, description="ID da fase"),
    boat_id: Optional[str] = Query(None, description="ID do barco (boat_id deferred Q.115.A.07)"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.115.E — P(defeito) para combinação (operator, phase, boat).

    Usado pelo card de decisão e pelas vistas Overall Q.115.J/L.
    boat_id é aceite mas ignorado até migration 018 chegar a main (Q.115.A.07).
    """
    from src.quality.services.defect_risk_service import DefectRiskService

    svc = DefectRiskService(session, tenant_id)
    preview = await svc.preview_for_combination(
        operator_id=operator_id,
        phase_id=phase_id,
        boat_id=boat_id,
    )
    # 404 se nenhuma combinação válida: todos os params None e sem histórico
    if (
        operator_id is None
        and phase_id is None
        and boat_id is None
        and preview.historical_count == 0
        and preview.p_defect == 0.0
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Nenhuma combinação válida — sem histórico de retrabalho.",
        )
    return preview


@router.get("/defect-risk")
async def defect_risk(
    top_n: int = Query(50, ge=1, le=200),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Tab "Predições" — P(defeito) per in-progress order from the active
    `QualityRiskModel`. Trains+promotes a model on first use when the
    registry is empty; degrades with `model_available=false` when the
    quality history is too thin to train.
    """
    from src.quality.services.defect_risk_service import DefectRiskService

    svc = DefectRiskService(session, tenant_id)
    return await svc.defect_risk(top_n=top_n)


@router.get("/defect-zones")
async def defect_zones(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Tab "Mapa do casco" — rework events aggregated by hull zone for the
    SVG. Always returns every canonical zone (count 0 when clean).
    """
    from src.quality.services.defect_zone_service import DefectZoneService

    svc = DefectZoneService(session, tenant_id)
    return await svc.zones(since=since, until=until)


@router.get("/roi-actions")
async def roi_actions(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    top_n: int = Query(25, ge=1, le=100),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Tab "Custos-ROI" — € saved vs invested per quality action, ranked by
    net return, from `quality.rework_entry` + the error catalog.
    """
    from src.quality.services.roi_service import ROIService

    svc = ROIService(session, tenant_id)
    return await svc.roi_by_action(since=since, until=until, top_n=top_n)


# ─── Q.61.32c — Migrado de src/legacy/api.py ─────────────────────────
#
# Endpoints abaixo vinham de `src/legacy/api.py` sob `/api/errors*`.
# Comportamento copiado tal-qual (incluindo fallback fail-soft em DB
# outage, com `undefinedtable` adicionado ao matcher para o caso em que
# a tabela `plan.production_errors` ainda não foi criada). Q.62 limpa
# o BLE001 em conjunto.
#
# Estes 2 endpoints usam `require_tenant_header` (fail-closed, Q.12 Onda
# 0.1), não o local `get_tenant_id` do resto do módulo — preserva a
# garantia de Q.18.A.4.

_EMPTY_ERRORS_STATS = {
    "total": 0,
    "bySeverity": {"minor": 0, "major": 0, "critical": 0},
    "ordersWithErrors": 0,
    "topDescriptions": [],
    "topPhases": [],
}

_SEVERITY_LABELS = {1: "Minor", 2: "Major", 3: "Critical"}


@router.get("/errors/stats")
async def errors_stats(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Estatísticas agregadas sobre `plan.production_errors`.

    Migrado em Q.61.32c de `/api/errors/stats`. Shape preserva
    `ErrorsStats` do frontend. DB indisponível ou tabela em falta
    devolve `_EMPTY_ERRORS_STATS` (não 5xx) para a Qualidade renderizar
    estado vazio.
    """
    try:
        total = (
            await session.execute(
                select(func.count())
                .select_from(ProductionError)
                .where(ProductionError.tenant_id == tenant_id)
            )
        ).scalar() or 0

        severity_rows = (
            await session.execute(
                select(ProductionError.severity, func.count())
                .where(ProductionError.tenant_id == tenant_id)
                .group_by(ProductionError.severity)
            )
        ).all()
        by_severity = {"minor": 0, "major": 0, "critical": 0}
        bucket = {1: "minor", 2: "major", 3: "critical"}
        for severity, count in severity_rows:
            key = bucket.get(severity)
            if key:
                by_severity[key] += count

        orders_with_errors = (
            await session.execute(
                select(func.count(func.distinct(ProductionError.order_id))).where(
                    and_(
                        ProductionError.tenant_id == tenant_id,
                        ProductionError.order_id.isnot(None),
                    )
                )
            )
        ).scalar() or 0

        top_desc_rows = (
            await session.execute(
                select(ProductionError.description, func.count().label("c"))
                .where(ProductionError.tenant_id == tenant_id)
                .group_by(ProductionError.description)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()
        top_phase_rows = (
            await session.execute(
                select(ProductionError.phase_name, func.count().label("c"))
                .where(ProductionError.tenant_id == tenant_id)
                .group_by(ProductionError.phase_name)
                .order_by(func.count().desc())
                .limit(10)
            )
        ).all()

        return {
            "total": total,
            "bySeverity": by_severity,
            "ordersWithErrors": orders_with_errors,
            "topDescriptions": [
                {"description": desc, "count": count}
                for desc, count in top_desc_rows
            ],
            "topPhases": [
                {"phase": phase, "count": count}
                for phase, count in top_phase_rows
            ],
        }
    except Exception as e:
        error_str = str(e).lower()
        if any(
            m in error_str
            for m in (
                "connection refused",
                "operationalerror",
                "interfaceerror",
                "undefinedtable",
            )
        ):
            logger.warning("DB unavailable in errors_stats, returning empty: %s", e)
            return dict(_EMPTY_ERRORS_STATS)
        raise


@router.get("/errors")
async def list_errors_paginated(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    severity: Optional[int] = Query(None, ge=1, le=3, description="Filter by severity 1-3"),
    phase: Optional[str] = Query(None, description="Filter by phase name"),
    search: Optional[str] = Query(None, description="Search in description or phase name"),
    sortBy: str = Query("severity", description="Sort field: id, severity, description, orderId"),
    sortOrder: str = Query("desc", description="Sort order: asc, desc"),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lista paginada de production errors.

    Migrado em Q.61.32c de `/api/errors`. Shape preserva `ErrorsResponse`
    do frontend (camelCase + `hasNextPage`/`hasPreviousPage`).
    """
    try:
        query = select(ProductionError).where(ProductionError.tenant_id == tenant_id)

        if severity is not None:
            query = query.where(ProductionError.severity == severity)
        if phase:
            query = query.where(ProductionError.phase_name == phase)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    ProductionError.description.ilike(pattern),
                    ProductionError.phase_name.ilike(pattern),
                )
            )

        total = (
            await session.execute(
                select(func.count()).select_from(query.subquery())
            )
        ).scalar() or 0

        sort_field_map = {
            "id": ProductionError.id,
            "severity": ProductionError.severity,
            "description": ProductionError.description,
            "orderId": ProductionError.order_id,
        }
        sort_field = sort_field_map.get(sortBy, ProductionError.severity)
        query = query.order_by(
            sort_field.asc() if sortOrder.lower() == "asc" else sort_field.desc()
        )

        offset = (page - 1) * pageSize
        query = query.limit(pageSize).offset(offset)

        errors = (await session.execute(query)).scalars().all()
        data = [
            {
                "id": str(err.id),
                "orderId": str(err.order_id) if err.order_id else None,
                "phaseName": err.phase_name,
                "evalPhaseName": err.eval_phase_name,
                "description": err.description,
                "severity": err.severity,
                "severityLabel": _SEVERITY_LABELS.get(err.severity, "Minor"),
            }
            for err in errors
        ]

        total_pages = math.ceil(total / pageSize) if pageSize > 0 else 0
        return {
            "data": data,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": total_pages,
            "hasNextPage": page < total_pages,
            "hasPreviousPage": page > 1,
        }
    except Exception as e:
        error_str = str(e).lower()
        if any(
            m in error_str
            for m in (
                "connection refused",
                "operationalerror",
                "interfaceerror",
                "undefinedtable",
            )
        ):
            logger.warning("DB unavailable in list_errors_paginated, returning empty: %s", e)
            return {
                "data": [],
                "total": 0,
                "page": page,
                "pageSize": pageSize,
                "totalPages": 0,
                "hasNextPage": False,
                "hasPreviousPage": False,
            }
        raise


# ─── Q.115.H — Runbooks aprendidos ────────────────────────────────────────


class RunbookApproveRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None


def _runbook_to_dict(rb: Runbook) -> dict[str, Any]:
    return {
        "id": str(rb.id),
        "error_code": rb.error_code,
        "steps_md": rb.steps_md,
        "source": rb.source,
        "confidence": rb.confidence,
        "approved_by": rb.approved_by,
        "approved_at": rb.approved_at.isoformat() if rb.approved_at else None,
        "created_at": rb.created_at.isoformat() if rb.created_at else None,
    }


@router.get("/runbook")
async def list_runbooks(
    error_code: Optional[str] = Query(None, description="Filtrar por error_code"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Lista runbooks ligados a um error_code, ordenados por prioridade + confidence DESC.

    Devolve lista vazia quando não existe runbook para o error_code.
    """
    if not error_code:
        # Sem filtro: devolve todos os runbooks do tenant
        result = await session.execute(
            select(Runbook)
            .where(Runbook.tenant_id == tenant_id)
            .order_by(desc(Runbook.confidence))
            .limit(100)
        )
        return [_runbook_to_dict(r) for r in result.scalars().all()]

    # Com error_code: join via link para respeitar prioridade
    result = await session.execute(
        select(Runbook, ErrorTypeRunbookLink.priority)
        .join(
            ErrorTypeRunbookLink,
            and_(
                ErrorTypeRunbookLink.runbook_id == Runbook.id,
                ErrorTypeRunbookLink.tenant_id == tenant_id,
                ErrorTypeRunbookLink.error_code == error_code,
            ),
        )
        .where(Runbook.tenant_id == tenant_id)
        .order_by(ErrorTypeRunbookLink.priority, desc(Runbook.confidence))
    )
    rows = result.all()
    return [_runbook_to_dict(rb) for rb, _priority in rows]


@router.post("/runbook/{runbook_id}/approve")
async def approve_runbook(
    runbook_id: UUID,
    req: RunbookApproveRequest,
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Aprova um runbook. Requer aprovação humana (Q.17 invariante).

    Escreve `approved_by` + `approved_at` + audit_trace_id na mesma tx.
    """
    from src.quality.services.runbook_service import approve_runbook as _approve

    try:
        runbook = await _approve(
            session=session,
            tenant_id=tenant_id,
            runbook_id=runbook_id,
            approved_by=req.approved_by,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))

    await session.commit()
    return _runbook_to_dict(runbook)
