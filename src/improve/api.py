"""
ProdPlan ONE - Improve (Suggestions) API
=========================================

Endpoints for AI-generated improvement suggestions.

Sprint Q.10 Fase C — moved from in-memory ``suggestions_store`` /
hardcoded ``PREDEFINED_SUGGESTIONS`` to DB-backed ``ImproveService``.
``POST /generate`` now calls Copilot/Ollama via ``chat_with_fallback``
with graceful fallback to per-tenant SEED rows.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.improve.models import ImprovementSuggestion
from src.improve.service import (
    ImproveService,
    SuggestionNotFoundError,
    SuggestionStateError,
)
from src.shared.database import get_session
from src.shared.pagination import validate_pagination

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/improve", tags=["Improve"])


# ============================================================================
# SCHEMAS
# ============================================================================


class SuggestionResponse(BaseModel):
    """Response for a suggestion."""
    id: str
    title: str
    description: str
    domain: str
    action_type: str
    status: str
    source: str  # "seed" | "llm_generated" | "manual"
    estimated_impact: Dict[str, Any]
    confidence: float
    created_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class GenerateSuggestionsRequest(BaseModel):
    """Request to generate new suggestions."""
    scope: Optional[str] = None  # "oee" | "quality" | "supply" | "hr"
    limit: int = Field(default=5, ge=1, le=20)
    factory_state_summary: Optional[Dict[str, Any]] = None


class ActionCatalogEntry(BaseModel):
    """Entry in the actions catalog."""
    type: str
    name: str
    description: str
    domains: List[str]
    parameters: Dict[str, Any]


class RejectRequest(BaseModel):
    reason: Optional[str] = None


# ============================================================================
# ACTION TYPES CATALOG (static; describes the action_type values
# the suggestions can take)
# ============================================================================


ACTION_CATALOG: List[Dict[str, Any]] = [
    {
        "type": "reduce_standard_time",
        "name": "Reduce Standard Time",
        "description": "Reduce the standard time for a specific operation or phase",
        "domains": ["oee", "performance"],
        "parameters": {
            "phase_id": {"type": "string", "required": True},
            "reduction_pct": {"type": "number", "min": 0, "max": 50},
        },
    },
    {
        "type": "add_machine",
        "name": "Add Machine",
        "description": "Add additional machine capacity to a station",
        "domains": ["oee", "availability"],
        "parameters": {
            "station_id": {"type": "string", "required": True},
            "machine_type": {"type": "string", "required": True},
        },
    },
    {
        "type": "improve_quality",
        "name": "Improve Quality Process",
        "description": "Implement quality improvement measures",
        "domains": ["quality", "oee"],
        "parameters": {
            "process_id": {"type": "string", "required": True},
            "improvement_type": {
                "type": "string",
                "enum": ["spc", "inspection", "training"],
            },
        },
    },
    {
        "type": "optimize_schedule",
        "name": "Optimize Schedule",
        "description": "Reschedule production for better performance",
        "domains": ["supply", "otd"],
        "parameters": {
            "objective": {"type": "string", "enum": ["otd", "throughput", "cost"]},
            "horizon_days": {"type": "number", "min": 1, "max": 30},
        },
    },
    {
        "type": "cross_training",
        "name": "Cross-Training Program",
        "description": "Train operators on multiple stations",
        "domains": ["hr", "availability"],
        "parameters": {
            "employee_ids": {"type": "array", "items": {"type": "string"}},
            "target_stations": {"type": "array", "items": {"type": "string"}},
        },
    },
]


# ============================================================================
# DEPENDENCIES
# ============================================================================


def get_tenant_id(
    x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000")),
) -> UUID:
    return x_tenant_id


def get_reviewer_id(
    x_user_id: Optional[UUID] = Header(default=None),
) -> UUID:
    return x_user_id or UUID("00000000-0000-0000-0000-000000000001")


async def get_improve_service(
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ImproveService:
    return ImproveService(session=session, tenant_id=tenant_id)


def _to_response(sug: ImprovementSuggestion) -> SuggestionResponse:
    return SuggestionResponse(
        id=str(sug.id),
        title=sug.title,
        description=sug.description,
        domain=sug.domain,
        action_type=sug.action_type,
        status=sug.status,
        source=sug.source,
        estimated_impact=sug.estimated_impact or {},
        confidence=sug.confidence,
        created_at=sug.created_at.isoformat() if sug.created_at else "",
        reviewed_at=sug.reviewed_at.isoformat() if sug.reviewed_at else None,
        reviewed_by=str(sug.reviewed_by) if sug.reviewed_by else None,
    )


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/suggestions", response_model=List[SuggestionResponse])
async def list_suggestions(
    status_filter: Optional[str] = Query(None, alias="status"),
    domain: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: ImproveService = Depends(get_improve_service),
):
    """List improvement suggestions for the current tenant.

    On first call for a tenant, the service seeds the bucket with the
    5 SEED_SUGGESTIONS so a fresh install isn't blank.
    """
    validate_pagination(limit, offset)
    rows = await service.list_suggestions(
        status=status_filter, domain=domain, limit=limit, offset=offset,
    )
    return [_to_response(s) for s in rows]


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestion(
    suggestion_id: UUID,
    service: ImproveService = Depends(get_improve_service),
):
    """Get details of a specific suggestion."""
    sug = await service.get_suggestion(suggestion_id)
    if sug is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{suggestion_id}' not found.",
        )
    return _to_response(sug)


@router.post("/suggestions/generate", response_model=List[SuggestionResponse])
async def generate_suggestions(
    request: GenerateSuggestionsRequest,
    service: ImproveService = Depends(get_improve_service),
):
    """Generate new suggestions via Copilot/Ollama with graceful fallback
    to seed data when the LLM is unavailable.

    Sprint Q.10 (C.3) — replaces the previous *fake* AI generator that
    only copied ``PREDEFINED_SUGGESTIONS``.
    """
    rows = await service.generate_via_llm(
        scope=request.scope,
        limit=request.limit,
        factory_state_summary=request.factory_state_summary,
    )
    return [_to_response(s) for s in rows]


@router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionResponse)
async def approve_suggestion(
    suggestion_id: UUID,
    reviewer_id: UUID = Depends(get_reviewer_id),
    service: ImproveService = Depends(get_improve_service),
):
    """Approve a pending suggestion."""
    try:
        sug = await service.approve(suggestion_id, reviewer_id)
    except SuggestionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{suggestion_id}' not found.",
        )
    except SuggestionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _to_response(sug)


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
async def reject_suggestion(
    suggestion_id: UUID,
    request: Optional[RejectRequest] = None,
    reviewer_id: UUID = Depends(get_reviewer_id),
    service: ImproveService = Depends(get_improve_service),
):
    """Reject a pending suggestion. Optional ``reason`` in the body is
    stored in ``rejection_reason``."""
    reason = request.reason if request else None
    try:
        sug = await service.reject(suggestion_id, reviewer_id, reason=reason)
    except SuggestionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{suggestion_id}' not found.",
        )
    except SuggestionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return _to_response(sug)


@router.get("/actions", response_model=List[ActionCatalogEntry])
async def get_actions_catalog():
    """Get catalog of available action types for the suggestions."""
    return [ActionCatalogEntry(**a) for a in ACTION_CATALOG]
