"""
ProdPlan ONE - Sandbox API
===========================

Endpoints for sandbox scenarios, suggestion testing, and impact preview.

Sprint Q.10 Fase B — moved from in-memory ``sandbox_store`` dict to
DB-backed ``SandboxService``. Tenant isolation now real; ``publish``
creates a real ``SharedDecisionRun`` (advisory) instead of a mock UUID.

IMPORTANT: This module respects BLOCKED_METRICS from config.py.
Blocked metrics are never simulated with fake values - they show as BLOCKED.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.config import (
    ALLOWED_METRICS,
    BLOCKED_METRICS,
)
from src.sandbox.service import (
    SandboxNotFoundError,
    SandboxScenario,
    SandboxService,
    SandboxStateError,
)
from src.shared.database import get_session
from src.shared.pagination import validate_pagination

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
    suggestion_id: Optional[str] = None
    initial_state: Optional[Dict[str, Any]] = None


class ApplySuggestionRequest(BaseModel):
    """Request to apply a suggestion to sandbox."""
    suggestion_id: str
    estimated_impact: Optional[Dict[str, Any]] = None


class SandboxScenarioResponse(BaseModel):
    """Response for a sandbox scenario."""
    id: str
    title: str
    description: Optional[str]
    status: str
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
# HELPERS
# ============================================================================


from src.shared.auth.headers import require_tenant_header, require_user_header

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID/'api_user' defaults.
get_tenant_id = require_tenant_header
get_current_user = require_user_header


async def get_sandbox_service(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> SandboxService:
    return SandboxService(session=session, tenant_id=tenant_id)


def _to_response(scenario: SandboxScenario) -> SandboxScenarioResponse:
    return SandboxScenarioResponse(
        id=str(scenario.id),
        title=scenario.title,
        description=scenario.description,
        status=scenario.status,
        suggestion_id=scenario.suggestion_id,
        created_at=scenario.created_at.isoformat() if scenario.created_at else "",
        updated_at=scenario.updated_at.isoformat() if scenario.updated_at else "",
        before_state=scenario.before_state or {},
        after_state=scenario.after_state,
        impact=scenario.impact,
    )


def create_baseline_state() -> Dict[str, Any]:
    """Build the baseline factory state dict used as ``before_state`` when
    the caller doesn't provide one. Mirrors the BLOCKED vs AVAILABLE
    contract from the Factory Data Product so we never simulate metrics
    we can't measure.

    Sprint S7 / Π8: every metric defaults to BLOCKED. The previous "OK"
    values for ``wip_theoretical=1523``, ``lead_time_observed_days=55.5``
    and ``quality_errors_count=89836`` were sample numbers from
    ``Folha_IA_extra.xlsx`` (data discovery), not real factory state. Each
    new tenant inherited those literals as their baseline, which made
    every sandbox impact calculation nonsensical. Callers that have a real
    baseline must pass ``initial_state`` explicitly; the rest get a
    BLOCKED skeleton instead of fake numbers.
    """
    return {
        "oee": MetricValue(
            value=None, status="BLOCKED",
            reason=BLOCKED_METRICS["oee_real"]["reason"],
            how_to_enable="Implementar recolha de dados de paragens/máquinas",
        ).model_dump(),
        "availability": MetricValue(
            value=None, status="BLOCKED",
            reason=BLOCKED_METRICS["availability_oee"]["reason"],
            how_to_enable="Requer: machine_downtime, planned_production_time",
        ).model_dump(),
        "otd": MetricValue(
            value=None, status="BLOCKED",
            reason=BLOCKED_METRICS["otd_official"]["reason"],
            how_to_enable="Requer: promised_delivery_date",
        ).model_dump(),
        "wip_theoretical": MetricValue(
            value=None, status="BLOCKED",
            reason="Pass `initial_state.wip_theoretical` explicitly, or wait for the factory data product to ingest current WIP.",
            how_to_enable="Send the current value in the create-scenario request body, or run the factory data product ingest first.",
        ).model_dump(),
        "lead_time_observed_days": MetricValue(
            value=None, status="BLOCKED",
            reason="Pass `initial_state.lead_time_observed_days` explicitly.",
            how_to_enable="Send the current value in the create-scenario request body.",
        ).model_dump(),
        "quality_errors_count": MetricValue(
            value=None, status="BLOCKED",
            reason="Pass `initial_state.quality_errors_count` explicitly.",
            how_to_enable="Send the current value in the create-scenario request body.",
        ).model_dump(),
    }


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/scenarios", response_model=List[SandboxScenarioResponse])
async def list_sandbox_scenarios(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: SandboxService = Depends(get_sandbox_service),
):
    """List sandbox scenarios for the current tenant."""
    validate_pagination(limit, offset)
    scenarios = await service.list_scenarios(
        status=status_filter, limit=limit, offset=offset,
    )
    return [_to_response(s) for s in scenarios]


@router.post(
    "/scenarios",
    response_model=SandboxScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sandbox_scenario(
    request: SandboxScenarioCreate,
    service: SandboxService = Depends(get_sandbox_service),
):
    """Create a new sandbox scenario for the current tenant."""
    before_state = request.initial_state or create_baseline_state()
    scenario = await service.create_scenario(
        title=request.title,
        description=request.description,
        suggestion_id=request.suggestion_id,
        before_state=before_state,
    )
    return _to_response(scenario)


@router.get("/scenarios/{scenario_id}", response_model=SandboxScenarioResponse)
async def get_sandbox_scenario(
    scenario_id: UUID,
    service: SandboxService = Depends(get_sandbox_service),
):
    """Get details of a sandbox scenario."""
    scenario = await service.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    return _to_response(scenario)


@router.post("/scenarios/{scenario_id}/apply-suggestion")
async def apply_suggestion_to_sandbox(
    scenario_id: UUID,
    request: ApplySuggestionRequest,
    service: SandboxService = Depends(get_sandbox_service),
):
    """Link a suggestion to the scenario and seed ``after_state`` with
    its estimated impact, ready for simulation."""
    suggestion_payload = {
        "id": request.suggestion_id,
        "estimated_impact": request.estimated_impact or {},
    }
    try:
        scenario = await service.apply_suggestion(scenario_id, suggestion_payload)
    except SandboxNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    return {
        "scenario_id": str(scenario.id),
        "suggestion_id": request.suggestion_id,
        "message": "Suggestion linked to sandbox scenario.",
    }


@router.post("/scenarios/{scenario_id}/simulate", response_model=SandboxScenarioResponse)
async def simulate_sandbox(
    scenario_id: UUID,
    service: SandboxService = Depends(get_sandbox_service),
):
    """Compute the before→after impact summary based on the previously
    applied suggestion. Heavy CPO simulation lives in the Twin module."""
    try:
        scenario = await service.simulate(scenario_id)
    except SandboxNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    except SandboxStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _to_response(scenario)


@router.get("/scenarios/{scenario_id}/exec-pack", response_model=ExecPackResponse)
async def get_exec_pack(
    scenario_id: UUID,
    service: SandboxService = Depends(get_sandbox_service),
):
    """Return the action+validation+rollback bundle that ``publish``
    would hand to the governance workflow."""
    scenario = await service.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    if scenario.status != "simulated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario must be simulated before generating exec pack.",
        )
    return ExecPackResponse(
        scenario_id=str(scenario.id),
        actions=[
            {
                "type": "apply_suggestion",
                "suggestion_id": scenario.suggestion_id,
                "estimated_impact": scenario.impact,
            },
        ],
        validations=[
            {"type": "sod_approval", "required_role": "manager_operations"},
            {"type": "blocked_metrics_check"},
        ],
        rollback_plan={
            "strategy": "snapshot_restore",
            "snapshot_id": f"pre_{scenario.id}",
            "max_rollback_window_hours": 24,
        },
    )


@router.post("/scenarios/{scenario_id}/publish")
async def publish_sandbox(
    scenario_id: UUID,
    user_id: str = Depends(get_current_user),
    service: SandboxService = Depends(get_sandbox_service),
):
    """Publish a simulated scenario — creates a real ``SharedDecisionRun``
    (advisory mode until Sprint G ties the ERP)."""
    try:
        scenario = await service.publish(scenario_id, proposed_by=user_id)
    except SandboxNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox scenario '{scenario_id}' not found.",
        )
    except SandboxStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "scenario_id": str(scenario.id),
        "status": "published",
        "message": "Sandbox scenario submitted for approval (advisory mode).",
        "decision_id": str(scenario.decision_id) if scenario.decision_id else None,
        "advisory_mode": True,
    }


@router.get("/blocked-metrics")
async def get_sandbox_blocked_metrics():
    """Return list of metrics that cannot be simulated due to data limitations."""
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
        "note": (
            "Blocked metrics will show status='BLOCKED' in sandbox scenarios. "
            "They cannot be simulated because the source data does not "
            "contain the required information."
        ),
    }
