"""Policy endpoints — list + lookup by decision_type.

Q.67.6.B5 — split from the legacy ``src/governance/api.py``.

Policies define the governance rules (autonomy level, required approvers,
canary %, …) for each decision type. They live in ``DecisionPolicy`` rows but
the API surfaces them as plain dicts via :meth:`GovernanceService.list_policies`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..service import GovernanceService
from ._dependencies import get_governance_service

router = APIRouter(tags=["Governance"])


class PolicyResponse(BaseModel):
    """Response for a policy."""
    decision_type: str
    autonomy_level: str
    requires_approval: bool
    required_approvers: int
    requires_different_approver: bool
    description: Optional[str] = None


@router.get("/policies", response_model=List[PolicyResponse])
async def list_policies(
    service: GovernanceService = Depends(get_governance_service),
):
    """List all decision policies.

    Policies define the governance rules for each decision type.
    """
    return [PolicyResponse(**p) for p in service.list_policies()]


@router.get("/policies/{decision_type}", response_model=PolicyResponse)
async def get_policy(
    decision_type: str,
    service: GovernanceService = Depends(get_governance_service),
):
    """Get policy for a specific decision type."""
    policy = service.get_policy(decision_type)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No policy found for decision type: {decision_type}",
        )
    return PolicyResponse(**policy)


__all__ = ["router", "PolicyResponse"]
