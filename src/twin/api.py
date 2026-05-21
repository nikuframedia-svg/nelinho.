"""
ProdPlan ONE - Digital Twin API
================================

Endpoints for digital twin scenarios, simulation, comparison, and solving.
Now backed by `TwinService` (DB-persisted); the previous in-memory
`scenarios_store` dict has been removed.

BLOCKED metrics (OEE/Availability/Performance/Quality/OTD) come from
`create_baseline_state()` in the service — no machine/downtime data means
these are still marked BLOCKED, not simulated.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.twin.service import TwinService, TwinValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/twin", tags=["Digital Twin"])


# ============================================================================
# SCHEMAS
# ============================================================================

class ScenarioCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_scenario_id: Optional[UUID] = None


class DeltaApplyRequest(BaseModel):
    entity_type: str
    entity_key: str
    patch: Dict[str, Any]
    description: Optional[str] = None


class ScenarioResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deltas: List[Dict[str, Any]] = Field(default_factory=list)
    simulation_result: Optional[Dict[str, Any]] = None
    scenario_hash: Optional[str] = None


class SimulationResult(BaseModel):
    scenario_id: str
    status: str
    kpis: Dict[str, Any]
    comparison: Optional[Dict[str, Any]] = None
    # `mode` is honest: "projecao_linear" = KPIs from linear delta
    # projection only; "solver_cpsat" = CP-SAT ran automatically.
    mode: str = "projecao_linear"
    mode_reason: Optional[str] = None
    solver: Optional[Dict[str, Any]] = None
    simulated_at: str


class SolveRequest(BaseModel):
    """Optional CP-SAT inputs. If omitted, endpoint returns INSUFFICIENT_DATA."""
    objective: str = Field(default="maximize_oee")
    operations: Optional[List[Dict[str, Any]]] = None
    machines: Optional[List[Dict[str, Any]]] = None
    time_limit_sec: float = Field(default=30.0, ge=1.0, le=300.0)


# ============================================================================
# DEPENDENCIES
# ============================================================================

from src.shared.auth.headers import require_tenant_header, require_user_header

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID/'api_user' defaults.
get_tenant_id = require_tenant_header
get_current_user = require_user_header


async def get_twin_service(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> TwinService:
    return TwinService(db=db, tenant_id=tenant_id)


def _scenario_response(scenario) -> ScenarioResponse:
    data = TwinService.scenario_to_dict(scenario)
    return ScenarioResponse(
        id=data["id"],
        title=data["title"],
        description=data["description"],
        status=data["status"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        deltas=data["deltas"],
        simulation_result=data["simulation_result"],
        scenario_hash=data["scenario_hash"],
    )


# ============================================================================
# BASELINE
# ============================================================================

@router.get("/baseline")
async def get_baseline_state(service: TwinService = Depends(get_twin_service)):
    """
    Get the current factory baseline state.

    Returns all available KPIs with trust metadata. BLOCKED metrics are
    marked with reason. Data comes from the Factory Data Product semantic
    layer when ingestion has run.
    """
    baseline = await service._create_baseline_state()

    available: Dict[str, Any] = {}
    blocked: Dict[str, Any] = {}
    for key, value in baseline.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and value.get("status") == "BLOCKED":
            blocked[key] = value
        else:
            available[key] = value

    return {
        "baseline_state": baseline,
        "available_metrics": available,
        "blocked_metrics": blocked,
        "summary": {
            "available_count": len(available),
            "blocked_count": len(blocked),
            "overall_trust": "WARNING",
            "data_source": baseline.get("_metadata", {}).get("data_version", "unavailable"),
        },
        "disclaimers": [
            "OEE/Availability/Performance/Quality são BLOCKED - não existem dados de máquinas/paragens",
            "OTD é BLOCKED - não existe promessa comercial (due date)",
            "Backlog e WIP são TEÓRICOS - baseados em HorasPrevistas (58% cobertura)",
            "Lead time é OBSERVADO - baseado em DataCriacao → DataAcabamento",
        ],
    }


# ============================================================================
# SCENARIO CRUD
# ============================================================================

@router.get("/scenarios", response_model=List[ScenarioResponse])
async def list_scenarios(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: TwinService = Depends(get_twin_service),
):
    scenarios = await service.list_scenarios(status=status_filter, limit=limit, offset=offset)
    return [_scenario_response(s) for s in scenarios]


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scenario(
    request: ScenarioCreateRequest,
    user: str = Depends(get_current_user),
    service: TwinService = Depends(get_twin_service),
):
    scenario = await service.create_scenario(
        title=request.title,
        description=request.description,
        base_scenario_id=request.base_scenario_id,
        created_by=user,
    )
    return _scenario_response(scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: UUID,
    service: TwinService = Depends(get_twin_service),
):
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    return _scenario_response(scenario)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: UUID,
    service: TwinService = Depends(get_twin_service),
):
    deleted = await service.delete_scenario(scenario_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )


# ============================================================================
# DELTAS
# ============================================================================

@router.post("/scenarios/{scenario_id}/apply-delta")
async def apply_delta(
    scenario_id: UUID,
    delta: DeltaApplyRequest,
    user: str = Depends(get_current_user),
    service: TwinService = Depends(get_twin_service),
):
    try:
        applied = await service.apply_delta(
            scenario_id=scenario_id,
            entity_type=delta.entity_type,
            entity_key=delta.entity_key,
            patch=delta.patch,
            description=delta.description,
            applied_by=user,
        )
    except TwinValidationError as e:
        # Q.54.I — input inválido (entity_type desconhecido, NaN/inf,
        # percentagem fora de gama) → 422, não 400/404.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    scenario = await service.get_scenario(scenario_id)
    return {
        "scenario_id": str(scenario_id),
        "delta_count": len(scenario.deltas) if scenario else 0,
        "delta_id": str(applied.id),
        "message": "Delta applied successfully.",
    }


# ============================================================================
# SIMULATION
# ============================================================================

@router.post("/scenarios/{scenario_id}/simulate", response_model=SimulationResult)
async def simulate_scenario(
    scenario_id: UUID,
    service: TwinService = Depends(get_twin_service),
):
    try:
        result = await service.simulate(scenario_id)
    except TwinValidationError as e:
        # Q.54.I — delta inválido num cenário existente → 422 (erro de
        # input). Tem de ser apanhado ANTES do `except ValueError` porque
        # TwinValidationError é subclasse de ValueError.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {e}",
        )

    return SimulationResult(
        scenario_id=str(scenario_id),
        status="simulated",
        kpis=result.get("after", {}),
        comparison=result.get("delta_summary"),
        mode=result.get("mode", "projecao_linear"),
        mode_reason=result.get("mode_reason"),
        solver=result.get("solver"),
        simulated_at=result.get("simulated_at", datetime.now(timezone.utc).isoformat()),
    )


# ============================================================================
# SOLVE
# ============================================================================

@router.post("/scenarios/{scenario_id}/solve")
async def solve_scenario(
    scenario_id: UUID,
    request: SolveRequest,
    service: TwinService = Depends(get_twin_service),
):
    """
    Run optimization on a scenario.

    Provide `operations[]` and `machines[]` in the body to run CP-SAT.
    Without them, the endpoint returns the delta-projected KPIs with
    status=INSUFFICIENT_DATA (no mock results). Send `{}` for defaults.
    """
    try:
        result = await service.solve(
            scenario_id=scenario_id,
            objective=request.objective,
            operations=request.operations,
            machines=request.machines,
            time_limit_sec=request.time_limit_sec,
        )
    except TwinValidationError as e:
        # Q.54.I — delta inválido → 422 (antes do except ValueError).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return result


# ============================================================================
# COMPARE
# ============================================================================

@router.get("/scenarios/{scenario_id}/compare")
async def compare_scenario(
    scenario_id: UUID,
    baseline_id: Optional[UUID] = Query(None),
    user: str = Depends(get_current_user),
    service: TwinService = Depends(get_twin_service),
):
    try:
        return await service.compare(
            scenario_id=scenario_id,
            baseline_scenario_id=baseline_id,
            compared_by=user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================================================
# AUDIT / REPRODUCIBILITY
# ============================================================================

@router.get("/scenarios/{scenario_id}/hashes")
async def get_scenario_hashes(
    scenario_id: UUID,
    service: TwinService = Depends(get_twin_service),
):
    """
    Return all hashes for reproducibility/audit:
    baseline, deltas, scenario, result.
    """
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    hashes = service.get_audit_hashes(scenario)
    return {
        "scenario_id": str(scenario_id),
        "hashes": hashes,
        "reproducibility": {
            "is_reproducible": True,
            "algorithm": "sha256",
            "deterministic": True,
            "verification": "Same baseline + same deltas = same scenario_hash",
        },
    }


@router.post("/scenarios/{scenario_id}/verify")
async def verify_scenario_hash(
    scenario_id: UUID,
    expected_hash: str = Query(..., description="Expected scenario hash to verify"),
    service: TwinService = Depends(get_twin_service),
):
    """Verify a scenario matches an expected hash."""
    scenario = await service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )

    hashes = service.get_audit_hashes(scenario)
    current_hash = hashes["scenario_hash_full"]

    expected_norm = expected_hash.lower()
    current_norm = current_hash.lower()
    is_match = (
        expected_norm == current_norm
        or current_norm.startswith(expected_norm)
    )

    return {
        "scenario_id": str(scenario_id),
        "verification": {
            "expected_hash": expected_hash,
            "current_hash": hashes["scenario_hash"],
            "current_hash_full": current_hash,
            "matches": is_match,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        },
        "status": "VERIFIED" if is_match else "MISMATCH",
        "message": (
            "Scenario hash matches expected value - integrity verified"
            if is_match
            else "Scenario hash does NOT match - possible modification detected"
        ),
    }
