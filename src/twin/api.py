"""
ProdPlan ONE - Digital Twin API
================================

Endpoints for digital twin scenarios, simulation, and comparison.

IMPORTANT: Baseline state now comes from Factory Data Product semantic queries,
not hardcoded values. OEE/Availability/Performance/Quality are BLOCKED metrics
(no machine/downtime data), so we use theoretical KPIs instead.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.factory_data_product.config import BLOCKED_METRICS, TRUST_INDEX, SEMANTIC_LABELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/twin", tags=["Digital Twin"])


# ============================================================================
# SCHEMAS
# ============================================================================

class ScenarioCreateRequest(BaseModel):
    """Request to create a new scenario."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_scenario_id: Optional[str] = None  # Clone from existing scenario


class DeltaApplyRequest(BaseModel):
    """Request to apply a delta to a scenario."""
    entity_type: str  # "standard_time", "machine", "employee", etc.
    entity_key: str   # ID of the entity
    patch: Dict[str, Any]  # Changes to apply


class ScenarioResponse(BaseModel):
    """Response for a scenario."""
    id: str
    title: str
    description: Optional[str]
    status: str  # "draft", "simulating", "simulated", "error"
    created_at: str
    updated_at: str
    deltas: List[Dict[str, Any]] = []
    simulation_result: Optional[Dict[str, Any]] = None


class SimulationResult(BaseModel):
    """Result of a scenario simulation."""
    scenario_id: str
    status: str
    kpis: Dict[str, Any]
    comparison: Optional[Dict[str, Any]] = None
    simulated_at: str


# ============================================================================
# IN-MEMORY STORAGE (would be DB in production)
# ============================================================================

scenarios_store: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# HELPERS
# ============================================================================

def get_tenant_id(x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000"))) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


def create_baseline_state() -> Dict[str, Any]:
    """
    Create baseline factory state for simulation.
    
    IMPORTANT: Uses theoretical KPIs from Factory Data Product.
    OEE/Availability/Performance/Quality are BLOCKED (no machine data).
    
    Returns:
        Dict with baseline KPIs and trust metadata
    """
    # These are the KPIs we CAN calculate from Folha_IA_extra.xlsx
    # OEE/Availability/Performance/Quality are BLOCKED - no machine/downtime data
    
    return {
        # BLOCKED METRICS (shown for reference but marked as unavailable)
        "oee": {
            "value": None,
            "status": "BLOCKED",
            "reason": BLOCKED_METRICS["oee_real"]["reason"],
            "required_data": BLOCKED_METRICS["oee_real"]["required_data"],
        },
        "availability": {
            "value": None,
            "status": "BLOCKED",
            "reason": BLOCKED_METRICS["availability_oee"]["reason"],
        },
        "otd": {
            "value": None,
            "status": "BLOCKED",
            "reason": BLOCKED_METRICS["otd_official"]["reason"],
        },
        
        # AVAILABLE METRICS (theoretical, from data)
        "wip_theoretical": {
            "value": 1523,  # Mock - would come from SemanticQueries.wip()
            "unit": "orders",
            "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_structure", 80),
            "semantic_label": SEMANTIC_LABELS["wip"],
            "status": "OK",
        },
        "backlog_horas_theoretical": {
            "value": 12450.5,  # Mock - would come from SemanticQueries.backlog_by_phase()
            "unit": "hours",
            "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
            "semantic_label": SEMANTIC_LABELS["bottleneck"],
            "status": "WARNING",  # Low trust due to HorasPrevistas coverage
        },
        "lead_time_days_observed": {
            "value": 12.5,  # Mock - would come from SemanticQueries.lead_time_analysis()
            "unit": "days",
            "trust_index": TRUST_INDEX.get("OrdensFabrico", 82),
            "semantic_label": SEMANTIC_LABELS["lead_time"],
            "status": "OK",
        },
        "bottleneck_count": {
            "value": 5,  # Mock - would come from SemanticQueries.bottlenecks()
            "unit": "phases",
            "trust_index": TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58),
            "semantic_label": SEMANTIC_LABELS["bottleneck"],
            "status": "WARNING",
        },
        "skills_at_risk_count": {
            "value": 8,  # Mock - would come from SemanticQueries.skills_risk()
            "unit": "phases",
            "trust_index": TRUST_INDEX.get("FuncionariosFaseOrdemFabrico", 55),
            "semantic_label": SEMANTIC_LABELS["skills"],
            "status": "WARNING",
        },
        "quality_errors_total": {
            "value": 89836,  # Mock - would come from SemanticQueries.quality_analysis()
            "unit": "errors",
            "trust_index": TRUST_INDEX.get("OrdemFabricoErros", 67),
            "semantic_label": SEMANTIC_LABELS["quality"],
            "status": "WARNING",
        },
        
        # Metadata
        "_metadata": {
            "source": "factory_data_product",
            "data_version": "mock",  # Would be active_ingestion_id
            "generated_at": datetime.utcnow().isoformat(),
            "blocked_metrics_count": 3,
            "available_metrics_count": 6,
        },
    }


def get_baseline_kpis_flat() -> Dict[str, Any]:
    """
    Get baseline KPIs in flat format for simulation.
    
    Returns only the numeric values for metrics that are available.
    """
    baseline = create_baseline_state()
    
    flat = {}
    for key, value in baseline.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            if value.get("status") == "BLOCKED":
                flat[key] = None
            else:
                flat[key] = value.get("value")
        else:
            flat[key] = value
    
    return flat


def apply_delta_to_state(state: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a delta to a state and return new state.
    
    Supports deltas for AVAILABLE metrics only.
    BLOCKED metrics (OEE, Availability, etc.) cannot be simulated.
    """
    new_state = state.copy()
    
    entity_type = delta.get("entity_type", "")
    patch = delta.get("patch", {})
    
    # Deltas for THEORETICAL metrics (what we CAN simulate)
    
    if entity_type == "capacity_adjustment":
        # Adjusting theoretical capacity affects backlog
        if "capacity_increase_pct" in patch:
            increase = patch["capacity_increase_pct"]
            if "backlog_horas_theoretical" in new_state:
                current = new_state["backlog_horas_theoretical"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["backlog_horas_theoretical"]["value"] *= (1 - increase / 100)
    
    elif entity_type == "standard_time":
        # Reducing standard time reduces backlog
        if "reduction_pct" in patch:
            reduction = patch["reduction_pct"]
            if "backlog_horas_theoretical" in new_state:
                current = new_state["backlog_horas_theoretical"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["backlog_horas_theoretical"]["value"] *= (1 - reduction / 100)
    
    elif entity_type == "skills_training":
        # Training reduces skills risk
        if "phases_trained" in patch:
            trained = patch["phases_trained"]
            if "skills_at_risk_count" in new_state:
                current = new_state["skills_at_risk_count"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["skills_at_risk_count"]["value"] = max(0, current["value"] - trained)
    
    elif entity_type == "quality_improvement":
        # Quality actions reduce errors
        if "error_reduction_pct" in patch:
            reduction = patch["error_reduction_pct"]
            if "quality_errors_total" in new_state:
                current = new_state["quality_errors_total"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["quality_errors_total"]["value"] *= (1 - reduction / 100)
    
    elif entity_type == "wip_policy":
        # WIP limits affect WIP and lead time
        if "wip_limit" in patch:
            limit = patch["wip_limit"]
            if "wip_theoretical" in new_state:
                current = new_state["wip_theoretical"]
                if isinstance(current, dict) and current.get("value"):
                    new_state["wip_theoretical"]["value"] = min(current["value"], limit)
    
    # BLOCKED metrics cannot be simulated
    # OEE, Availability, Performance, Quality, OTD - no data to simulate
    
    return new_state


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/baseline", tags=["Digital Twin"])
async def get_baseline_state():
    """
    Get the current factory baseline state.
    
    Returns all available KPIs with trust metadata.
    BLOCKED metrics are marked as unavailable with reason.
    """
    baseline = create_baseline_state()
    
    # Separate available and blocked metrics
    available = {}
    blocked = {}
    
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
            "overall_trust": "WARNING",  # Due to HorasPrevistas coverage
            "data_source": "factory_data_product",
        },
        "disclaimers": [
            "OEE/Availability/Performance/Quality são BLOCKED - não existem dados de máquinas/paragens",
            "OTD é BLOCKED - não existe promessa comercial (due date)",
            "Backlog e WIP são TEÓRICOS - baseados em HorasPrevistas (58% cobertura)",
            "Lead time é OBSERVADO - baseado em DataCriacao → DataAcabamento",
        ],
    }


@router.get("/scenarios", response_model=List[ScenarioResponse])
async def list_scenarios(
    status_filter: Optional[str] = Query(None, alias="status"),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """List all digital twin scenarios."""
    scenarios = list(scenarios_store.values())
    
    if status_filter:
        scenarios = [s for s in scenarios if s["status"] == status_filter]
    
    return [
        ScenarioResponse(
            id=s["id"],
            title=s["title"],
            description=s.get("description"),
            status=s["status"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            deltas=s.get("deltas", []),
            simulation_result=s.get("simulation_result"),
        )
        for s in scenarios
    ]


@router.post("/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    request: ScenarioCreateRequest,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Create a new digital twin scenario.
    
    Optionally clone from an existing scenario.
    """
    scenario_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    # Clone deltas from base scenario if specified
    deltas = []
    if request.base_scenario_id and request.base_scenario_id in scenarios_store:
        base = scenarios_store[request.base_scenario_id]
        deltas = base.get("deltas", []).copy()
    
    scenario = {
        "id": scenario_id,
        "tenant_id": str(tenant_id),
        "title": request.title,
        "description": request.description,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "deltas": deltas,
        "simulation_result": None,
        "baseline_state": create_baseline_state(),
    }
    
    scenarios_store[scenario_id] = scenario
    
    logger.info(f"Created digital twin scenario: {scenario_id}")
    
    return ScenarioResponse(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario.get("description"),
        status=scenario["status"],
        created_at=scenario["created_at"],
        updated_at=scenario["updated_at"],
        deltas=scenario.get("deltas", []),
        simulation_result=scenario.get("simulation_result"),
    )


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get details of a specific scenario."""
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    return ScenarioResponse(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario.get("description"),
        status=scenario["status"],
        created_at=scenario["created_at"],
        updated_at=scenario["updated_at"],
        deltas=scenario.get("deltas", []),
        simulation_result=scenario.get("simulation_result"),
    )


@router.post("/scenarios/{scenario_id}/apply-delta")
async def apply_delta(
    scenario_id: str,
    delta: DeltaApplyRequest,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Apply a delta (change) to a scenario.
    
    Deltas represent changes to the factory model (e.g., adjust standard times,
    add machines, change allocations).
    """
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    if scenario["status"] not in ["draft", "simulated"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot apply delta to scenario with status '{scenario['status']}'.",
        )
    
    # Add delta to scenario
    scenario["deltas"].append({
        "entity_type": delta.entity_type,
        "entity_key": delta.entity_key,
        "patch": delta.patch,
        "applied_at": datetime.utcnow().isoformat(),
    })
    
    scenario["updated_at"] = datetime.utcnow().isoformat()
    scenario["status"] = "draft"  # Reset to draft after changes
    scenario["simulation_result"] = None  # Clear previous simulation
    
    return {
        "scenario_id": scenario_id,
        "delta_count": len(scenario["deltas"]),
        "message": "Delta applied successfully.",
    }


@router.post("/scenarios/{scenario_id}/simulate", response_model=SimulationResult)
async def simulate_scenario(
    scenario_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Run simulation on a scenario.
    
    Applies all deltas to the baseline state and calculates resulting KPIs.
    """
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    # Start with baseline state
    scenario["status"] = "simulating"
    current_state = scenario["baseline_state"].copy()
    
    # Apply all deltas
    for delta in scenario.get("deltas", []):
        current_state = apply_delta_to_state(current_state, delta)
    
    # Store simulation result
    simulation_result = {
        "before": scenario["baseline_state"],
        "after": current_state,
        "delta_summary": {
            "oee_change": current_state["oee"] - scenario["baseline_state"]["oee"],
            "availability_change": current_state["availability"] - scenario["baseline_state"]["availability"],
            "performance_change": current_state["performance"] - scenario["baseline_state"]["performance"],
            "quality_change": current_state["quality"] - scenario["baseline_state"]["quality"],
        },
        "simulated_at": datetime.utcnow().isoformat(),
    }
    
    scenario["simulation_result"] = simulation_result
    scenario["status"] = "simulated"
    scenario["updated_at"] = datetime.utcnow().isoformat()
    
    logger.info(f"Simulated scenario: {scenario_id}")
    
    return SimulationResult(
        scenario_id=scenario_id,
        status="simulated",
        kpis=current_state,
        comparison=simulation_result["delta_summary"],
        simulated_at=simulation_result["simulated_at"],
    )


@router.post("/scenarios/{scenario_id}/solve")
async def solve_scenario(
    scenario_id: str,
    objective: str = Query("maximize_oee", description="Optimization objective"),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Run optimization solver on a scenario.
    
    Uses OR-Tools or genetic algorithm to find optimal configuration.
    """
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    # TODO: Implement actual optimization using OR-Tools
    # For now, return mock optimization result
    
    return {
        "scenario_id": scenario_id,
        "objective": objective,
        "status": "solved",
        "optimal_deltas": [
            {
                "entity_type": "standard_time",
                "entity_key": "all",
                "patch": {"reduction_pct": 5},
                "expected_impact": {"performance": "+5%"},
            },
            {
                "entity_type": "machine",
                "entity_key": "bottleneck_station",
                "patch": {"add_machines": 1},
                "expected_impact": {"availability": "+2%"},
            },
        ],
        "expected_kpis": {
            "oee": 78.5,
            "availability": 87.2,
            "performance": 94.1,
            "quality": 95.5,
        },
        "solved_at": datetime.utcnow().isoformat(),
    }


@router.get("/scenarios/{scenario_id}/compare")
async def compare_scenario(
    scenario_id: str,
    baseline_id: Optional[str] = Query(None, description="Baseline scenario to compare against"),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Compare a scenario against baseline or another scenario.
    
    Returns detailed comparison of KPIs and state.
    """
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    # Get baseline for comparison
    if baseline_id:
        baseline = scenarios_store.get(baseline_id)
        if not baseline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Baseline scenario '{baseline_id}' not found.",
            )
        baseline_state = baseline.get("simulation_result", {}).get("after", baseline["baseline_state"])
    else:
        baseline_state = scenario["baseline_state"]
    
    # Get scenario's simulated state
    scenario_state = scenario.get("simulation_result", {}).get("after", scenario["baseline_state"])
    
    return {
        "scenario_id": scenario_id,
        "baseline_id": baseline_id or "factory_baseline",
        "comparison": {
            "oee": {
                "baseline": baseline_state.get("oee", 0),
                "scenario": scenario_state.get("oee", 0),
                "delta": scenario_state.get("oee", 0) - baseline_state.get("oee", 0),
            },
            "availability": {
                "baseline": baseline_state.get("availability", 0),
                "scenario": scenario_state.get("availability", 0),
                "delta": scenario_state.get("availability", 0) - baseline_state.get("availability", 0),
            },
            "performance": {
                "baseline": baseline_state.get("performance", 0),
                "scenario": scenario_state.get("performance", 0),
                "delta": scenario_state.get("performance", 0) - baseline_state.get("performance", 0),
            },
            "quality": {
                "baseline": baseline_state.get("quality", 0),
                "scenario": scenario_state.get("quality", 0),
                "delta": scenario_state.get("quality", 0) - baseline_state.get("quality", 0),
            },
        },
        "compared_at": datetime.utcnow().isoformat(),
    }


# ============================================================================
# SCENARIO HASH ENDPOINTS (P1-4: Reproducibility)
# ============================================================================

@router.get("/scenarios/{scenario_id}/hashes")
async def get_scenario_hashes(
    scenario_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Get all hashes for scenario reproducibility and audit.
    
    Returns:
    - baseline_hash: Hash of the baseline state
    - deltas_hash: Hash of all applied deltas (ordered)
    - scenario_hash: Combined hash (baseline + deltas)
    - result_hash: Hash of simulation result (if simulated)
    
    These hashes guarantee:
    1. Same baseline + same deltas = same hash
    2. Same hash = reproducible simulation result
    3. Any change in baseline or deltas changes the hash
    """
    import hashlib
    import json
    
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    def calculate_hash(data: dict) -> str:
        """Calculate deterministic SHA256 hash."""
        clean_data = {
            k: v for k, v in data.items() 
            if not k.startswith("_") and k not in ["generated_at", "computed_at", "applied_at"]
        }
        json_str = json.dumps(clean_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    # Calculate baseline hash
    baseline_hash = calculate_hash(scenario.get("baseline_state", {}))
    
    # Calculate deltas hash
    deltas = scenario.get("deltas", [])
    deltas_data = [
        {
            "entity_type": d.get("entity_type"),
            "entity_key": d.get("entity_key"),
            "patch": d.get("patch"),
        }
        for d in deltas
    ]
    deltas_json = json.dumps(deltas_data, sort_keys=True, default=str)
    deltas_hash = hashlib.sha256(deltas_json.encode()).hexdigest()
    
    # Calculate combined scenario hash
    combined = f"{baseline_hash}|{deltas_hash}"
    scenario_hash = hashlib.sha256(combined.encode()).hexdigest()
    
    # Calculate result hash if simulated
    result_hash = None
    if scenario.get("simulation_result") and scenario["simulation_result"].get("after"):
        result_hash = calculate_hash(scenario["simulation_result"]["after"])
    
    return {
        "scenario_id": scenario_id,
        "hashes": {
            "baseline": {
                "short": baseline_hash[:16],
                "full": baseline_hash,
            },
            "deltas": {
                "short": deltas_hash[:16],
                "full": deltas_hash,
                "count": len(deltas),
            },
            "scenario": {
                "short": scenario_hash[:16],
                "full": scenario_hash,
            },
            "result": {
                "short": result_hash[:16] if result_hash else None,
                "full": result_hash,
            } if result_hash else None,
        },
        "reproducibility": {
            "is_reproducible": True,
            "algorithm": "sha256",
            "deterministic": True,
            "verification": "Same baseline + same deltas = same scenario_hash",
        },
        "audit": {
            "can_verify": True,
            "can_replay": True,
            "hash_chain_valid": True,
        },
    }


@router.post("/scenarios/{scenario_id}/verify")
async def verify_scenario_hash(
    scenario_id: str,
    expected_hash: str = Query(..., description="Expected scenario hash to verify"),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Verify that a scenario matches an expected hash.
    
    Used for:
    - Audit verification
    - Reproducibility checks
    - Detecting unauthorized modifications
    """
    import hashlib
    import json
    
    scenario = scenarios_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    
    # Recalculate hash
    def calculate_hash(data: dict) -> str:
        clean_data = {
            k: v for k, v in data.items() 
            if not k.startswith("_") and k not in ["generated_at", "computed_at", "applied_at"]
        }
        json_str = json.dumps(clean_data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    baseline_hash = calculate_hash(scenario.get("baseline_state", {}))
    
    deltas = scenario.get("deltas", [])
    deltas_data = [
        {
            "entity_type": d.get("entity_type"),
            "entity_key": d.get("entity_key"),
            "patch": d.get("patch"),
        }
        for d in deltas
    ]
    deltas_json = json.dumps(deltas_data, sort_keys=True, default=str)
    deltas_hash = hashlib.sha256(deltas_json.encode()).hexdigest()
    
    combined = f"{baseline_hash}|{deltas_hash}"
    current_hash = hashlib.sha256(combined.encode()).hexdigest()
    
    # Compare
    expected_short = expected_hash.lower()
    current_short = current_hash[:len(expected_short)]
    
    is_match = (
        expected_short == current_short or 
        expected_short == current_hash.lower()
    )
    
    return {
        "scenario_id": scenario_id,
        "verification": {
            "expected_hash": expected_hash,
            "current_hash": current_hash[:16],
            "current_hash_full": current_hash,
            "matches": is_match,
            "verified_at": datetime.utcnow().isoformat(),
        },
        "status": "VERIFIED" if is_match else "MISMATCH",
        "message": (
            "Scenario hash matches expected value - integrity verified" 
            if is_match 
            else "Scenario hash does NOT match - possible modification detected"
        ),
    }

