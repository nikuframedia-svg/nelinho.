"""
ProdPlan ONE - Sandbox API
===========================

Endpoints for sandbox scenarios, suggestion testing, and impact preview.

IMPORTANT: This module respects BLOCKED_METRICS from config.py.
Blocked metrics are never simulated with fake values - they show as BLOCKED.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.factory_data_product.config import (
    BLOCKED_METRICS,
    ALLOWED_METRICS,
    TRUST_INDEX,
    SEMANTIC_LABELS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sandbox", tags=["Sandbox"])


# ============================================================================
# SCHEMAS
# ============================================================================

class MetricValue(BaseModel):
    """Represents a metric value with status and metadata."""
    value: Optional[float] = None
    status: str  # "OK", "WARNING", "BLOCKED"
    reason: Optional[str] = None
    semantic_label: Optional[str] = None
    trust_index: Optional[float] = None
    warning: Optional[str] = None
    how_to_enable: Optional[str] = None


class SandboxScenarioCreate(BaseModel):
    """Request to create a sandbox scenario."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    suggestion_id: Optional[str] = None  # Link to a suggestion
    initial_state: Optional[Dict[str, Any]] = None


class ApplySuggestionRequest(BaseModel):
    """Request to apply a suggestion to sandbox."""
    suggestion_id: str


class SandboxScenarioResponse(BaseModel):
    """Response for a sandbox scenario."""
    id: str
    title: str
    description: Optional[str]
    status: str  # "draft", "simulating", "simulated", "published"
    suggestion_id: Optional[str]
    created_at: str
    updated_at: str
    before_state: Dict[str, Any]
    after_state: Optional[Dict[str, Any]] = None
    impact: Optional[Dict[str, Any]] = None


class ExecPackResponse(BaseModel):
    """Execution package for publishing a sandbox scenario."""
    scenario_id: str
    actions: List[Dict[str, Any]]
    validations: List[Dict[str, Any]]
    rollback_plan: Dict[str, Any]


# ============================================================================
# IN-MEMORY STORAGE (would be DB in production)
# ============================================================================

sandbox_store: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# HELPERS
# ============================================================================

def get_tenant_id(x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000"))) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


def create_baseline_state() -> Dict[str, Any]:
    """
    Create baseline factory state for sandbox.
    
    CRITICAL: Uses BLOCKED_METRICS to mark unavailable KPIs.
    Only theoretical/available metrics get values.
    
    This function respects the "Truth by Design" principle:
    - Blocked metrics show status=BLOCKED with reason
    - Available metrics show actual/estimated values with trust scores
    """
    return {
        # =====================================================================
        # BLOCKED METRICS (no data available in Folha_IA_extra.xlsx)
        # =====================================================================
        "oee": MetricValue(
            value=None,
            status="BLOCKED",
            reason=BLOCKED_METRICS["oee_real"]["reason"],
            how_to_enable="Implementar recolha de dados de paragens/máquinas",
        ).model_dump(),
        
        "availability": MetricValue(
            value=None,
            status="BLOCKED",
            reason=BLOCKED_METRICS["availability_oee"]["reason"],
            how_to_enable="Requer: machine_downtime, planned_production_time",
        ).model_dump(),
        
        "performance": MetricValue(
            value=None,
            status="BLOCKED",
            reason="Não existem dados de velocidade/ciclos de máquinas",
            how_to_enable="Requer: actual_cycle_time, ideal_cycle_time",
        ).model_dump(),
        
        "quality_rate": MetricValue(
            value=None,
            status="BLOCKED",
            reason="Taxa de qualidade requer dados de defeitos vs produção total",
            how_to_enable="Requer: good_units, total_units_produced",
        ).model_dump(),
        
        "otd": MetricValue(
            value=None,
            status="BLOCKED",
            reason=BLOCKED_METRICS["otd_official"]["reason"],
            how_to_enable="Requer: promised_delivery_date",
        ).model_dump(),
        
        "productivity_individual": MetricValue(
            value=None,
            status="BLOCKED",
            reason=BLOCKED_METRICS["productivity_individual_real"]["reason"],
            how_to_enable="Requer: actual_labor_hours_per_employee",
        ).model_dump(),
        
        "cost_real_per_order": MetricValue(
            value=None,
            status="BLOCKED",
            reason=BLOCKED_METRICS["cost_real_per_order"]["reason"],
            how_to_enable="Requer: actual_labor_hours_per_employee",
        ).model_dump(),
        
        # =====================================================================
        # AVAILABLE METRICS (can be calculated with Folha_IA_extra.xlsx data)
        # =====================================================================
        "wip_theoretical": MetricValue(
            value=1523,  # Would come from SemanticQueries.wip()
            status="OK",
            semantic_label=SEMANTIC_LABELS["wip"],
            trust_index=TRUST_INDEX.get("OrdensFabrico", 82) / 100,
        ).model_dump(),
        
        "backlog_hours_theoretical": MetricValue(
            value=12450,  # Would come from SemanticQueries.backlog_by_phase()
            status="WARNING",
            semantic_label=SEMANTIC_LABELS["bottleneck"],
            trust_index=TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58) / 100,
            warning="56.6% dos registos têm HorasPrevistas=0 - backlog pode estar subestimado",
        ).model_dump(),
        
        "backlog_days_theoretical": MetricValue(
            value=155.6,  # backlog_hours / 8 hours per day
            status="WARNING",
            semantic_label=SEMANTIC_LABELS["bottleneck"],
            trust_index=TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58) / 100,
            warning="Baseado em capacidade teórica de 8h/dia",
        ).model_dump(),
        
        "lead_time_observed_days": MetricValue(
            value=55.5,  # From SemanticQueries.lead_time_analysis()
            status="OK",
            semantic_label=SEMANTIC_LABELS["lead_time"],
            trust_index=TRUST_INDEX.get("OrdensFabrico", 82) / 100,
        ).model_dump(),
        
        "cost_per_unit_theoretical": MetricValue(
            value=45.50,  # Estimated from FuncionarioValorHora * HorasPrevistas
            status="WARNING",
            semantic_label=SEMANTIC_LABELS["cost"],
            trust_index=TRUST_INDEX.get("Funcionarios", 75) / 100,
            warning="Custo teórico - não inclui horas reais por funcionário",
        ).model_dump(),
        
        "quality_errors_count": MetricValue(
            value=89836,  # From OrdemFabricoErros
            status="OK",
            semantic_label=SEMANTIC_LABELS["quality"],
            trust_index=TRUST_INDEX.get("OrdemFabricoErros", 67) / 100,
        ).model_dump(),
        
        "mold_conflict_potential": MetricValue(
            value=23,  # Potential conflicts detected
            status="WARNING",
            semantic_label=SEMANTIC_LABELS["mold_conflict"],
            trust_index=TRUST_INDEX.get("FasesOrdemFabrico_DataPrevista", 35) / 100,
            warning="DataPrevista tem apenas 4.8% de cobertura - conflitos podem estar subestimados",
        ).model_dump(),
        
        "skills_risk_phases": MetricValue(
            value=5,  # Number of phases with skills risk
            status="DEGRADED",
            semantic_label=SEMANTIC_LABELS["skills"],
            trust_index=TRUST_INDEX.get("FuncionariosFasesAptos", 55) / 100,
            warning="Cobertura limitada de funcionários aptos por fase",
        ).model_dump(),
        
        "capacity_theoretical_hours": MetricValue(
            value=800,  # Sum of Fase_CapacidadeHorasDia
            status="OK",
            semantic_label=SEMANTIC_LABELS["capacity"],
            trust_index=TRUST_INDEX.get("Fases", 85) / 100,
        ).model_dump(),
    }


def simulate_impact(before: Dict[str, Any], suggestion_type: str) -> Dict[str, Any]:
    """
    Simulate impact of a suggestion.
    
    CRITICAL: Only modifies metrics that are NOT BLOCKED.
    Blocked metrics remain blocked - we cannot simulate what we cannot measure.
    """
    after = {}
    
    # Copy all metrics, preserving blocked status
    for key, value in before.items():
        if isinstance(value, dict):
            after[key] = value.copy()
        else:
            after[key] = {"value": value, "status": "OK"}
    
    # Define impact deltas by suggestion type (only for available metrics)
    impacts = {
        "reduce_backlog": {
            "backlog_hours_theoretical": -500,
            "backlog_days_theoretical": -62.5,
            "lead_time_observed_days": -2,
        },
        "increase_capacity": {
            "backlog_hours_theoretical": -800,
            "backlog_days_theoretical": -100,
            "capacity_theoretical_hours": 100,
        },
        "improve_quality": {
            "quality_errors_count": -1000,
        },
        "reduce_mold_conflicts": {
            "mold_conflict_potential": -5,
        },
        "optimize_schedule": {
            "lead_time_observed_days": -3,
            "wip_theoretical": -100,
        },
        "default": {
            "wip_theoretical": -50,
        },
    }
    
    impact_deltas = impacts.get(suggestion_type, impacts["default"])
    
    # Apply impacts only to available (non-blocked) metrics
    for metric, delta in impact_deltas.items():
        if metric not in after:
            continue
        
        metric_data = after[metric]
        
        # Skip blocked metrics
        if metric_data.get("status") == "BLOCKED":
            logger.info(f"Skipping blocked metric in simulation: {metric}")
            continue
        
        # Apply delta
        current = metric_data.get("value", 0)
        if current is not None:
            new_value = current + delta
            after[metric]["value"] = max(0, new_value)  # Prevent negative values
            after[metric]["simulated"] = True
    
    return after


def calculate_impact_summary(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate impact summary between before and after states.
    
    Only includes metrics that can actually be compared (not blocked).
    """
    impact = {}
    
    for key in before:
        before_data = before.get(key, {})
        after_data = after.get(key, {})
        
        # Skip blocked metrics
        if before_data.get("status") == "BLOCKED" or after_data.get("status") == "BLOCKED":
            impact[key] = {
                "status": "BLOCKED",
                "reason": before_data.get("reason", "Metric is blocked"),
                "simulable": False,
            }
            continue
        
        before_value = before_data.get("value", 0) or 0
        after_value = after_data.get("value", 0) or 0
        
        delta = after_value - before_value
        delta_pct = (delta / before_value * 100) if before_value != 0 else 0
        
        impact[key] = {
            "before": before_value,
            "after": after_value,
            "delta": round(delta, 2),
            "delta_pct": round(delta_pct, 2),
            "improved": delta < 0 if key in ["backlog_hours_theoretical", "lead_time_observed_days", "quality_errors_count", "mold_conflict_potential"] else delta > 0,
            "simulable": True,
            "trust_index": after_data.get("trust_index"),
        }
    
    return impact


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/scenarios", response_model=List[SandboxScenarioResponse])
async def list_sandbox_scenarios(
    status_filter: Optional[str] = Query(None, alias="status"),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """List all sandbox scenarios."""
    scenarios = list(sandbox_store.values())
    
    if status_filter:
        scenarios = [s for s in scenarios if s["status"] == status_filter]
    
    return [
        SandboxScenarioResponse(
            id=s["id"],
            title=s["title"],
            description=s.get("description"),
            status=s["status"],
            suggestion_id=s.get("suggestion_id"),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            before_state=s["before_state"],
            after_state=s.get("after_state"),
            impact=s.get("impact"),
        )
        for s in scenarios
    ]


@router.post("/scenarios", response_model=SandboxScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_sandbox_scenario(
    request: SandboxScenarioCreate,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Create a new sandbox scenario.
    
    The baseline state will include:
    - BLOCKED metrics (OEE, OTD, etc.) with status="BLOCKED" and reasons
    - Available metrics with actual/estimated values and trust scores
    """
    scenario_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    before_state = request.initial_state or create_baseline_state()
    
    scenario = {
        "id": scenario_id,
        "tenant_id": str(tenant_id),
        "title": request.title,
        "description": request.description,
        "status": "draft",
        "suggestion_id": request.suggestion_id,
        "created_at": now,
        "updated_at": now,
        "before_state": before_state,
        "after_state": None,
        "impact": None,
    }
    
    sandbox_store[scenario_id] = scenario
    
    logger.info(f"Created sandbox scenario: {scenario_id}")
    
    return SandboxScenarioResponse(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario.get("description"),
        status=scenario["status"],
        suggestion_id=scenario.get("suggestion_id"),
        created_at=scenario["created_at"],
        updated_at=scenario["updated_at"],
        before_state=scenario["before_state"],
        after_state=scenario.get("after_state"),
        impact=scenario.get("impact"),
    )


@router.get("/scenarios/{scenario_id}", response_model=SandboxScenarioResponse)
async def get_sandbox_scenario(
    scenario_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get details of a sandbox scenario."""
    scenario = sandbox_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    
    return SandboxScenarioResponse(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario.get("description"),
        status=scenario["status"],
        suggestion_id=scenario.get("suggestion_id"),
        created_at=scenario["created_at"],
        updated_at=scenario["updated_at"],
        before_state=scenario["before_state"],
        after_state=scenario.get("after_state"),
        impact=scenario.get("impact"),
    )


@router.post("/scenarios/{scenario_id}/apply-suggestion")
async def apply_suggestion_to_sandbox(
    scenario_id: str,
    request: ApplySuggestionRequest,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Apply a suggestion to a sandbox scenario.
    
    Links the suggestion and prepares for simulation.
    """
    scenario = sandbox_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    
    scenario["suggestion_id"] = request.suggestion_id
    scenario["updated_at"] = datetime.utcnow().isoformat()
    scenario["status"] = "draft"
    
    return {
        "scenario_id": scenario_id,
        "suggestion_id": request.suggestion_id,
        "message": "Suggestion linked to sandbox scenario.",
    }


@router.post("/scenarios/{scenario_id}/simulate", response_model=SandboxScenarioResponse)
async def simulate_sandbox(
    scenario_id: str,
    suggestion_type: str = Query("default", description="Type of suggestion to simulate"),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Run simulation on a sandbox scenario.
    
    IMPORTANT: Only non-blocked metrics can be simulated.
    Blocked metrics (OEE, OTD, etc.) will remain as BLOCKED in the results.
    
    Query params:
    - suggestion_type: Type of simulation (reduce_backlog, increase_capacity, improve_quality, etc.)
    """
    scenario = sandbox_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    
    scenario["status"] = "simulating"
    
    # Run simulation
    before_state = scenario["before_state"]
    after_state = simulate_impact(before_state, suggestion_type)
    
    # Calculate impact (only for simulable metrics)
    impact = calculate_impact_summary(before_state, after_state)
    
    # Count blocked vs simulable
    blocked_count = sum(1 for k, v in impact.items() if not v.get("simulable", True))
    simulable_count = len(impact) - blocked_count
    
    scenario["after_state"] = after_state
    scenario["impact"] = {
        "metrics": impact,
        "summary": {
            "blocked_metrics_count": blocked_count,
            "simulable_metrics_count": simulable_count,
            "suggestion_type": suggestion_type,
            "disclaimer": "Blocked metrics cannot be simulated due to missing data in source Excel.",
        },
    }
    scenario["status"] = "simulated"
    scenario["updated_at"] = datetime.utcnow().isoformat()
    
    logger.info(f"Simulated sandbox scenario: {scenario_id} (type: {suggestion_type})")
    
    return SandboxScenarioResponse(
        id=scenario["id"],
        title=scenario["title"],
        description=scenario.get("description"),
        status=scenario["status"],
        suggestion_id=scenario.get("suggestion_id"),
        created_at=scenario["created_at"],
        updated_at=scenario["updated_at"],
        before_state=scenario["before_state"],
        after_state=scenario.get("after_state"),
        impact=scenario.get("impact"),
    )


@router.get("/scenarios/{scenario_id}/exec-pack", response_model=ExecPackResponse)
async def get_exec_pack(
    scenario_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Get execution package for publishing a sandbox scenario.
    
    Contains all actions needed to apply changes to production.
    """
    scenario = sandbox_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    
    if scenario["status"] != "simulated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario must be simulated before generating exec pack.",
        )
    
    return ExecPackResponse(
        scenario_id=scenario_id,
        actions=[
            {
                "type": "update_parameter",
                "target": "standard_times",
                "operation": "multiply",
                "value": 0.95,  # 5% reduction
                "description": "Reduce standard times by 5%",
            },
        ],
        validations=[
            {
                "type": "range_check",
                "field": "backlog_hours_theoretical",
                "min": 0,
                "max": 100000,
            },
            {
                "type": "sod_approval",
                "required_role": "manager_operations",
            },
            {
                "type": "blocked_metrics_check",
                "description": "Ensure no blocked metrics are affected",
            },
        ],
        rollback_plan={
            "strategy": "snapshot_restore",
            "snapshot_id": f"pre_{scenario_id}",
            "max_rollback_window_hours": 24,
        },
    )


@router.post("/scenarios/{scenario_id}/publish")
async def publish_sandbox(
    scenario_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Publish a sandbox scenario to production.
    
    Creates a Decision proposal for approval workflow.
    """
    scenario = sandbox_store.get(scenario_id)
    
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    
    if scenario["status"] != "simulated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario must be simulated before publishing.",
        )
    
    # In production, this would create a Decision proposal
    scenario["status"] = "published"
    scenario["updated_at"] = datetime.utcnow().isoformat()
    
    return {
        "scenario_id": scenario_id,
        "status": "published",
        "message": "Sandbox scenario submitted for approval.",
        "decision_id": str(uuid4()),  # Mock decision ID
    }


@router.get("/blocked-metrics")
async def get_sandbox_blocked_metrics():
    """
    Return list of metrics that cannot be simulated due to data limitations.
    
    Useful for explaining to users why certain KPIs show as "BLOCKED".
    """
    return {
        "blocked_metrics": [
            {
                "id": metric_id,
                "reason": info["reason"],
                "required_data": info.get("required_data", []),
            }
            for metric_id, info in BLOCKED_METRICS.items()
        ],
        "available_metrics": ALLOWED_METRICS,
        "note": "Blocked metrics will show status='BLOCKED' in sandbox scenarios. "
                "They cannot be simulated because the source data (Folha_IA_extra.xlsx) "
                "does not contain the required information.",
    }
