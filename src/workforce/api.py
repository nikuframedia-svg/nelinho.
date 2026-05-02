"""
Workforce API Endpoints
=======================

REST endpoints for Workforce Operations System:
- GET /v1/workforce/dependency-graph
- GET /v1/workforce/cascade-impact/{phase_id}
- POST /v1/workforce/simulate
- GET /v1/workforce/training-recommendations
- POST /v1/workforce/scenarios/compare
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

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
# DEPENDENCY - Database Session
# ============================================================================

async def get_db() -> AsyncSession:
    """
    Get database session.
    Falls back gracefully if database not available.
    """
    try:
        from src.shared.database import get_async_session
        async for session in get_async_session():
            yield session
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        # Return a mock session that will trigger fallback behavior
        yield None


async def get_service(db: AsyncSession = Depends(get_db)) -> WorkforceService:
    """Default DI for endpoints that don't gate the mock graph.

    Sprint Q.8 Fase 6 — defaults to `allow_mock=False`. Endpoints that
    expose `?demo=true` build their own service via `WorkforceService(db,
    allow_mock=demo)` directly inside the handler so the flag flows
    through cleanly.
    """
    return WorkforceService(db, allow_mock=False)


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
    db: AsyncSession = Depends(get_db),
):
    """
    Get the complete workforce dependency graph.

    Returns nodes (phases, employees) and edges (aptitudes).
    This graph shows the relationships between:
    - Phases (production stages)
    - Employees (qualified workers)
    - Aptitudes (which employee can work in which phase)
    """
    logger.info("Getting dependency graph (demo=%s)", demo)
    service = WorkforceService(db, allow_mock=demo)
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
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate cascading impact if a phase becomes unavailable.

    Shows impact across 4 levels:
    1. Workforce level - which employees are affected
    2. Production level - orders in that phase
    3. Downstream phases - phases that depend on output
    4. Economic impact (theoretical estimates)
    """
    logger.info("Calculating cascade impact for phase %s (demo=%s)", phase_id, demo)
    service = WorkforceService(db, allow_mock=demo)
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
    service: WorkforceService = Depends(get_service),
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
    logger.info(f"Simulating workforce with {len(deltas)} deltas")
    try:
        result = await service.simulate_workforce([d.dict() for d in deltas])
        return result
    except Exception as e:
        logger.error(f"Error simulating workforce: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training-recommendations", response_model=List[TrainingRecommendationResponse])
async def get_training_recommendations(
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of recommendations to return"),
    service: WorkforceService = Depends(get_service),
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
    logger.info(f"Getting training recommendations (limit={limit})")
    try:
        result = await service.get_training_recommendations(limit)
        return result
    except Exception as e:
        logger.error(f"Error getting training recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/compare", response_model=ScenarioComparisonResponse)
async def compare_scenarios(
    scenario_ids: List[str],
    service: WorkforceService = Depends(get_service),
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
    logger.info(f"Comparing {len(scenario_ids)} scenarios")
    try:
        result = await service.compare_scenarios(scenario_ids)
        return result
    except Exception as e:
        logger.error(f"Error comparing scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))

