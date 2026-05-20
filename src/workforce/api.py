"""
Workforce API Endpoints
=======================

REST endpoints for Workforce Operations System:
- GET /v1/workforce/dependency-graph
- GET /v1/workforce/cascade-impact/{phase_id}
- POST /v1/workforce/simulate
- GET /v1/workforce/training-recommendations
- POST /v1/workforce/scenarios/compare

Q.61.32b — migrados de /api/allocations* (legacy):
- GET /v1/workforce/allocations          (paginated)
- GET /v1/workforce/allocations/stats    (aggregate)
"""
import logging
import math
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.hr.models.legacy_allocation import LegacyAllocation
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session, get_session_safe

from .service import WorkforceService, WorkforceDataUnavailableError
from .models import (
    WorkforceDelta,
    DependencyGraphResponse,
    CascadeImpactResponse,
    SimulationResultResponse,
    TrainingRecommendationResponse,
    ScenarioComparisonResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/workforce", tags=["workforce"])


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/dependency-graph", response_model=DependencyGraphResponse)
async def get_dependency_graph(
    demo: bool = Query(
        False,
        description="If True, fall back to a synthetic demo graph when "
        "curated data is unavailable. Default False — operators see 503 "
        "(Workforce data indisponível) instead of fake nodes.",
    ),
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """
    Get the complete workforce dependency graph.

    Returns nodes (phases, employees) and edges (aptitudes).
    This graph shows the relationships between:
    - Phases (production stages)
    - Employees (qualified workers)
    - Aptitudes (which employee can work in which phase)
    """
    logger.info("Getting dependency graph (tenant=%s, demo=%s)", tenant_id, demo)
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=demo)
    try:
        return await service.get_dependency_graph()
    except WorkforceDataUnavailableError as e:
        # Sprint Q.8 Fase 6 — surface as 503 so the UI can render a
        # banner ("Workforce data indisponível") instead of fake data.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting dependency graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cascade-impact/{phase_id}", response_model=CascadeImpactResponse)
async def get_cascade_impact(
    phase_id: str,
    demo: bool = Query(
        False,
        description="If True, fall back to a synthetic demo cascade. "
        "Default False — operators see 503 instead of fake numbers.",
    ),
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """
    Calculate cascading impact if a phase becomes unavailable.

    Shows impact across 4 levels:
    1. Workforce level - which employees are affected
    2. Production level - orders in that phase
    3. Downstream phases - phases that depend on output
    4. Economic impact (theoretical estimates)
    """
    logger.info("Calculating cascade impact for phase %s (tenant=%s, demo=%s)",
                phase_id, tenant_id, demo)
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=demo)
    try:
        return await service.calculate_cascade_impact(phase_id)
    except WorkforceDataUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error calculating cascade impact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate", response_model=SimulationResultResponse)
async def simulate_workforce(
    deltas: List[WorkforceDelta],
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """
    Simulate workforce changes and calculate impact.

    Accepts list of deltas (changes to simulate):
    - add_training: Train employee for new phase
    - remove_employee: Simulate employee unavailability
    - add_employee: Simulate hiring
    - modify_capacity: Change phase capacity

    Returns before/after comparison with impact metrics.
    """
    logger.info("Simulating workforce with %d deltas (tenant=%s)",
                len(deltas), tenant_id)
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=False)
    try:
        result = await service.simulate_workforce([d.dict() for d in deltas])
        return result
    except Exception as e:
        logger.error(f"Error simulating workforce: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-recommendations", response_model=List[TrainingRecommendationResponse])
async def get_training_recommendations(
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of recommendations to return"),
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """
    Get training recommendations ordered by impact.

    Algorithm prioritizes:
    1. SPOF elimination (phases with only 1 capable employee)
    2. Risk reduction (high-risk phases)
    3. Employee proximity to target phase (similar skills)

    Each recommendation includes:
    - Employee to train
    - Target phase
    - Reasoning
    - Expected impact
    - Estimated cost
    """
    logger.info("Getting training recommendations (tenant=%s, limit=%d)",
                tenant_id, limit)
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=False)
    try:
        result = await service.get_training_recommendations(limit)
        return result
    except Exception as e:
        logger.error(f"Error getting training recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/compare", response_model=ScenarioComparisonResponse)
async def compare_scenarios(
    scenario_ids: List[str],
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """
    Compare multiple workforce scenarios side by side.

    Returns metrics for each scenario including:
    - SPOF count
    - Average risk score
    - Backlog at risk
    - Estimated cost
    - Payback period (days)

    Also indicates which scenario is recommended (best ROI).
    """
    logger.info("Comparing %d scenarios (tenant=%s)", len(scenario_ids), tenant_id)
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=False)
    try:
        result = await service.compare_scenarios(scenario_ids)
        return result
    except Exception as e:
        logger.error(f"Error comparing scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# Q.18.ZIP.BE.2 — aliases semânticos (nomes pedidos pelo plano)
# ════════════════════════════════════════════════════════════════════════════
# Os endpoints originais (training-recommendations / simulate / dependency-graph)
# já cobrem o necessário. Estes 3 aliases dão à frontend nomes mais directos
# e payloads simplificados sem reimplementar lógica nos services.

class AbsenceSimulationRequest(BaseModel):
    """Body simples para simular ausência de um operador.

    Em vez de pedir array de WorkforceDelta com type='remove_employee',
    aceita só ``employee_id`` (+ phase_id opcional).
    """
    employee_id: str = Field(description="ID do funcionário ausente.")
    phase_id: str | None = Field(
        default=None,
        description="Fase específica a simular ausência (opcional).",
    )


@router.get("/risks/spof", response_model=List[TrainingRecommendationResponse])
async def workforce_risks_spof(
    limit: int = Query(default=10, ge=1, le=50),
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """SPOFs detectados — alias derivado de training-recommendations,
    filtrado para entries com ``expected_impact.spof_eliminated == True``.

    Plan v4 §4.5. Q.18.ZIP.BE.2.
    """
    logger.info("Getting SPOFs (tenant=%s, limit=%d)", tenant_id, limit)
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=False)
    try:
        recs = await service.get_training_recommendations(limit * 3)
        spofs = [
            r for r in recs
            if getattr(r, "expected_impact", None)
            and getattr(r.expected_impact, "spof_eliminated", False)
        ]
        return spofs[:limit]
    except Exception as e:
        logger.error(f"Error getting SPOFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate/absence", response_model=SimulationResultResponse)
async def simulate_absence(
    req: AbsenceSimulationRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """Simulate single-employee absence. Wrapper sobre /simulate com
    delta ``remove_employee`` pré-construído.

    Plan v4 §4.5. Q.18.ZIP.BE.2.
    """
    logger.info(
        "Simulating absence employee=%s phase=%s (tenant=%s)",
        req.employee_id, req.phase_id, tenant_id,
    )
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=False)
    delta = {
        "type": "remove_employee",
        "employee_id": req.employee_id,
        "description": (
            f"Simulated absence of employee {req.employee_id}"
            + (f" in phase {req.phase_id}" if req.phase_id else "")
        ),
    }
    if req.phase_id:
        delta["phase_id"] = req.phase_id
    try:
        return await service.simulate_workforce([delta])
    except Exception as e:
        logger.error(f"Error simulating absence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/training/suggestions",
    response_model=List[TrainingRecommendationResponse],
)
async def training_suggestions(
    limit: int = Query(default=10, ge=1, le=50),
    tenant_id: UUID = Depends(require_tenant_header),
    db: AsyncSession = Depends(get_session_safe),
):
    """Alias 1:1 de /training-recommendations com nome pedido pelo plano.
    Q.18.ZIP.BE.2.
    """
    logger.info(
        "Getting training suggestions (tenant=%s, limit=%d)", tenant_id, limit,
    )
    service = WorkforceService(db, tenant_id=tenant_id, allow_mock=False)
    try:
        return await service.get_training_recommendations(limit)
    except Exception as e:
        logger.error(f"Error getting training suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Q.61.32b — Migrado de src/legacy/api.py ─────────────────────────
#
# Os 2 endpoints abaixo vinham de `src/legacy/api.py` sob `/api/*`.
# Comportamento copiado tal-qual incluindo o fallback fail-soft em DB
# outage (Q.62 limpa BLE001). Behavioural preservation.


@router.get("/allocations")
async def list_allocations_paginated(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    employeeId: Optional[int] = Query(None, description="Filter by employee ID"),
    phase: Optional[str] = Query(None, description="Filter by phase name"),
    isLeader: Optional[bool] = Query(None, description="Filter by leader status"),
    search: Optional[str] = Query(None, description="Search in employee name, phase, or order ID"),
    sortBy: str = Query("startDate", description="Sort field: startDate, employeeName, phaseName, id"),
    sortOrder: str = Query("desc", description="Sort order: asc, desc"),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lista paginada de alocações (LegacyAllocation).

    Migrado em Q.61.32b de `/api/allocations`. Preserva contrato 1-para-1.
    """
    try:
        query = select(LegacyAllocation).where(LegacyAllocation.tenant_id == tenant_id)

        if employeeId:
            query = query.where(LegacyAllocation.employee_id == employeeId)
        if phase:
            query = query.where(LegacyAllocation.phase_name.ilike(f"%{phase}%"))
        if isLeader is not None:
            query = query.where(LegacyAllocation.is_leader == isLeader)
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    LegacyAllocation.employee_name.ilike(search_pattern),
                    LegacyAllocation.phase_name.ilike(search_pattern),
                    LegacyAllocation.order_id.cast(str).ilike(search_pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_query)).scalar() or 0

        sort_field_map = {
            "startDate": LegacyAllocation.start_date,
            "employeeName": LegacyAllocation.employee_name,
            "phaseName": LegacyAllocation.phase_name,
            "id": LegacyAllocation.id,
        }
        sort_field = sort_field_map.get(sortBy, LegacyAllocation.start_date)
        if sortOrder.lower() == "asc":
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())

        offset = (page - 1) * pageSize
        query = query.limit(pageSize).offset(offset)
        result = await session.execute(query)
        allocations = result.scalars().all()

        allocations_data = [
            {
                "id": str(a.id),
                "orderId": str(a.order_id) if a.order_id else None,
                "phaseId": str(a.phase_id) if a.phase_id else None,
                "phaseName": a.phase_name,
                "employeeId": str(a.employee_id),
                "employeeName": a.employee_name,
                "isLeader": a.is_leader,
                "startDate": a.start_date.isoformat() if a.start_date else None,
                "endDate": a.end_date.isoformat() if a.end_date else None,
            }
            for a in allocations
        ]

        total_pages = math.ceil(total / pageSize) if pageSize > 0 else 0
        return {
            "data": allocations_data,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": total_pages,
            "hasNextPage": page < total_pages,
            "hasPreviousPage": page > 1,
        }
    except Exception as e:  # noqa: BLE001  Q.62.E.1: comportamento copiado tal-qual em Q.61.32b (legacy fallback)
        error_str = str(e).lower()
        if (
            "connection refused" in error_str
            or "operationalerror" in error_str
            or "interfaceerror" in error_str
        ):
            logger.warning(
                "DB unavailable in list_allocations_paginated, returning fallback: %s",
                e,
            )
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


@router.get("/allocations/stats")
async def allocations_stats(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Estatísticas agregadas (total, unique employees/orders, leader, top phases/employees).

    Migrado em Q.61.32b de `/api/allocations/stats`.
    """
    try:
        total_query = select(func.count(LegacyAllocation.id)).where(
            LegacyAllocation.tenant_id == tenant_id
        )
        total = (await session.execute(total_query)).scalar() or 0

        unique_employees_query = select(
            func.count(func.distinct(LegacyAllocation.employee_id))
        ).where(LegacyAllocation.tenant_id == tenant_id)
        unique_employees = (await session.execute(unique_employees_query)).scalar() or 0

        unique_orders_query = select(
            func.count(func.distinct(LegacyAllocation.order_id))
        ).where(
            and_(
                LegacyAllocation.tenant_id == tenant_id,
                LegacyAllocation.order_id.isnot(None),
            )
        )
        unique_orders = (await session.execute(unique_orders_query)).scalar() or 0

        as_leader_query = select(func.count(LegacyAllocation.id)).where(
            and_(
                LegacyAllocation.tenant_id == tenant_id,
                LegacyAllocation.is_leader.is_(True),
            )
        )
        as_leader = (await session.execute(as_leader_query)).scalar() or 0

        avg_per_employee = (total / unique_employees) if unique_employees > 0 else 0

        top_phases_query = (
            select(
                LegacyAllocation.phase_name,
                func.count(LegacyAllocation.id).label("count"),
            )
            .where(LegacyAllocation.tenant_id == tenant_id)
            .group_by(LegacyAllocation.phase_name)
            .order_by(func.count(LegacyAllocation.id).desc())
            .limit(10)
        )
        top_phases = [
            {"phase": row[0], "count": row[1]}
            for row in (await session.execute(top_phases_query)).all()
        ]

        top_employees_query = (
            select(
                LegacyAllocation.employee_name,
                func.count(LegacyAllocation.id).label("count"),
            )
            .where(LegacyAllocation.tenant_id == tenant_id)
            .group_by(LegacyAllocation.employee_name)
            .order_by(func.count(LegacyAllocation.id).desc())
            .limit(10)
        )
        top_employees = [
            {"employee": row[0], "count": row[1]}
            for row in (await session.execute(top_employees_query)).all()
        ]

        return {
            "total": total,
            "uniqueEmployees": unique_employees,
            "uniqueOrders": unique_orders,
            "asLeader": as_leader,
            "avgPerEmployee": round(avg_per_employee, 2),
            "topPhases": top_phases,
            "topEmployees": top_employees,
        }
    except Exception as e:  # noqa: BLE001  Q.62.E.1: comportamento copiado tal-qual em Q.61.32b (legacy fallback)
        error_str = str(e).lower()
        if (
            "connection refused" in error_str
            or "operationalerror" in error_str
            or "interfaceerror" in error_str
        ):
            logger.warning("DB unavailable in allocations_stats, returning fallback: %s", e)
            return {
                "total": 0,
                "uniqueEmployees": 0,
                "uniqueOrders": 0,
                "asLeader": 0,
                "avgPerEmployee": 0.0,
                "topPhases": [],
                "topEmployees": [],
            }
        raise

