"""
ProdPlan ONE - Improve (Suggestions) API
=========================================

Endpoints for AI-generated improvement suggestions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

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
    domain: str  # "oee", "quality", "supply", etc.
    action_type: str  # "reduce_standard_time", "add_machine", etc.
    status: str  # "pending", "approved", "rejected", "implemented"
    estimated_impact: Dict[str, Any]
    confidence: float
    created_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class GenerateSuggestionsRequest(BaseModel):
    """Request to generate new suggestions."""
    scope: Optional[str] = None  # "oee", "quality", "supply", or None for all
    limit: int = Field(default=5, ge=1, le=20)


class ActionCatalogEntry(BaseModel):
    """Entry in the actions catalog."""
    type: str
    name: str
    description: str
    domains: List[str]
    parameters: Dict[str, Any]


# ============================================================================
# PREDEFINED SUGGESTIONS (in production, these would be AI-generated)
# ============================================================================

PREDEFINED_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "id": "sug_001",
        "title": "Reduce standard times for Laminagem phase",
        "description": "Analysis shows that Laminagem phase standard times are 15% higher than actual production times. Reducing standard times will improve performance metrics.",
        "domain": "oee",
        "action_type": "reduce_standard_time",
        "status": "pending",
        "estimated_impact": {
            "oee": {"delta": 3.5, "confidence": 0.85},
            "performance": {"delta": 5.0, "confidence": 0.90},
        },
        "confidence": 0.87,
        "created_at": "2026-01-28T10:00:00Z",
    },
    {
        "id": "sug_002",
        "title": "Add backup machine for bottleneck station",
        "description": "Station P003 (Corte) is a bottleneck with 92% utilization. Adding a backup machine would reduce wait times and improve availability.",
        "domain": "oee",
        "action_type": "add_machine",
        "status": "pending",
        "estimated_impact": {
            "oee": {"delta": 2.0, "confidence": 0.80},
            "availability": {"delta": 3.0, "confidence": 0.85},
        },
        "confidence": 0.82,
        "created_at": "2026-01-28T10:30:00Z",
    },
    {
        "id": "sug_003",
        "title": "Implement SPC for quality control",
        "description": "Statistical Process Control at critical quality gates would reduce defects by catching issues earlier in the process.",
        "domain": "quality",
        "action_type": "improve_quality",
        "status": "pending",
        "estimated_impact": {
            "quality": {"delta": 2.5, "confidence": 0.88},
            "oee": {"delta": 1.8, "confidence": 0.85},
        },
        "confidence": 0.86,
        "created_at": "2026-01-28T11:00:00Z",
    },
    {
        "id": "sug_004",
        "title": "Optimize production schedule for OTD improvement",
        "description": "Rescheduling based on delivery deadlines rather than arrival order would improve on-time delivery by 8%.",
        "domain": "supply",
        "action_type": "optimize_schedule",
        "status": "pending",
        "estimated_impact": {
            "otd": {"delta": 8.0, "confidence": 0.78},
            "lead_time": {"delta": -0.5, "confidence": 0.75},
        },
        "confidence": 0.77,
        "created_at": "2026-01-28T11:30:00Z",
    },
    {
        "id": "sug_005",
        "title": "Cross-train operators for multi-station flexibility",
        "description": "Training operators on multiple stations would reduce idle time during absences and improve overall efficiency.",
        "domain": "hr",
        "action_type": "cross_training",
        "status": "pending",
        "estimated_impact": {
            "availability": {"delta": 2.0, "confidence": 0.82},
            "oee": {"delta": 1.5, "confidence": 0.80},
        },
        "confidence": 0.81,
        "created_at": "2026-01-28T12:00:00Z",
    },
]

# In-memory store for suggestions
suggestions_store: Dict[str, Dict[str, Any]] = {s["id"]: s.copy() for s in PREDEFINED_SUGGESTIONS}


# ============================================================================
# ACTION TYPES CATALOG
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
            "improvement_type": {"type": "string", "enum": ["spc", "inspection", "training"]},
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
# HELPERS
# ============================================================================

def get_tenant_id(x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000"))) -> UUID:
    """Extract tenant ID from header."""
    return x_tenant_id


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/suggestions", response_model=List[SuggestionResponse])
async def list_suggestions(
    status_filter: Optional[str] = Query(None, alias="status"),
    domain: Optional[str] = Query(None),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    List improvement suggestions.
    
    Can filter by status and domain.
    """
    suggestions = list(suggestions_store.values())
    
    if status_filter:
        suggestions = [s for s in suggestions if s["status"] == status_filter]
    
    if domain:
        suggestions = [s for s in suggestions if s["domain"] == domain]
    
    return [
        SuggestionResponse(
            id=s["id"],
            title=s["title"],
            description=s["description"],
            domain=s["domain"],
            action_type=s["action_type"],
            status=s["status"],
            estimated_impact=s["estimated_impact"],
            confidence=s["confidence"],
            created_at=s["created_at"],
            reviewed_at=s.get("reviewed_at"),
            reviewed_by=s.get("reviewed_by"),
        )
        for s in suggestions
    ]


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestion(
    suggestion_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get details of a specific suggestion."""
    suggestion = suggestions_store.get(suggestion_id)
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{suggestion_id}' not found.",
        )
    
    return SuggestionResponse(
        id=suggestion["id"],
        title=suggestion["title"],
        description=suggestion["description"],
        domain=suggestion["domain"],
        action_type=suggestion["action_type"],
        status=suggestion["status"],
        estimated_impact=suggestion["estimated_impact"],
        confidence=suggestion["confidence"],
        created_at=suggestion["created_at"],
        reviewed_at=suggestion.get("reviewed_at"),
        reviewed_by=suggestion.get("reviewed_by"),
    )


@router.post("/suggestions/generate", response_model=List[SuggestionResponse])
async def generate_suggestions(
    request: GenerateSuggestionsRequest,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Generate new AI-powered suggestions.
    
    Analyzes current factory state and generates improvement recommendations.
    """
    # In production, this would call an AI model
    # For now, return filtered predefined suggestions
    
    suggestions = list(PREDEFINED_SUGGESTIONS)
    
    if request.scope:
        suggestions = [s for s in suggestions if s["domain"] == request.scope]
    
    suggestions = suggestions[:request.limit]
    
    # Add to store with new IDs
    new_suggestions = []
    for s in suggestions:
        new_id = f"sug_{uuid4().hex[:8]}"
        new_suggestion = s.copy()
        new_suggestion["id"] = new_id
        new_suggestion["created_at"] = datetime.utcnow().isoformat()
        suggestions_store[new_id] = new_suggestion
        new_suggestions.append(new_suggestion)
    
    logger.info(f"Generated {len(new_suggestions)} suggestions")
    
    return [
        SuggestionResponse(
            id=s["id"],
            title=s["title"],
            description=s["description"],
            domain=s["domain"],
            action_type=s["action_type"],
            status=s["status"],
            estimated_impact=s["estimated_impact"],
            confidence=s["confidence"],
            created_at=s["created_at"],
        )
        for s in new_suggestions
    ]


@router.post("/suggestions/{suggestion_id}/approve")
async def approve_suggestion(
    suggestion_id: str,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Approve a suggestion for implementation.
    
    Marks suggestion as approved and creates sandbox scenario.
    """
    suggestion = suggestions_store.get(suggestion_id)
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{suggestion_id}' not found.",
        )
    
    if suggestion["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Suggestion cannot be approved. Current status: {suggestion['status']}",
        )
    
    suggestion["status"] = "approved"
    suggestion["reviewed_at"] = datetime.utcnow().isoformat()
    suggestion["reviewed_by"] = str(tenant_id)
    
    logger.info(f"Approved suggestion: {suggestion_id}")
    
    return {
        "suggestion_id": suggestion_id,
        "status": "approved",
        "message": "Suggestion approved. You can now create a sandbox scenario to test it.",
    }


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: str,
    reason: Optional[str] = None,
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Reject a suggestion.
    
    Marks suggestion as rejected with optional reason.
    """
    suggestion = suggestions_store.get(suggestion_id)
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{suggestion_id}' not found.",
        )
    
    if suggestion["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Suggestion cannot be rejected. Current status: {suggestion['status']}",
        )
    
    suggestion["status"] = "rejected"
    suggestion["reviewed_at"] = datetime.utcnow().isoformat()
    suggestion["reviewed_by"] = str(tenant_id)
    suggestion["rejection_reason"] = reason
    
    logger.info(f"Rejected suggestion: {suggestion_id}, reason: {reason}")
    
    return {
        "suggestion_id": suggestion_id,
        "status": "rejected",
        "reason": reason,
        "message": "Suggestion rejected.",
    }


@router.get("/actions", response_model=List[ActionCatalogEntry])
async def get_actions_catalog():
    """
    Get catalog of available action types.
    
    Lists all action types that can be used in suggestions.
    """
    return [
        ActionCatalogEntry(
            type=a["type"],
            name=a["name"],
            description=a["description"],
            domains=a["domains"],
            parameters=a["parameters"],
        )
        for a in ACTION_CATALOG
    ]





