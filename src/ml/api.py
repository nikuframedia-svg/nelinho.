"""
ProdPlan ONE — ML API (`/v1/ml`)
=================================

Endpoints:
- GET  /v1/ml/models                           — list all model names
- GET  /v1/ml/models/{name}/versions           — list versions (newest first)
- GET  /v1/ml/models/{name}/active             — current active version
- POST /v1/ml/models/{name}/versions/{id}/promote — promote version
                                                    (creates DecisionRun)

Retrain triggers live per-model under `src/ml/models_domain/` in Sprint H;
this router only exposes lifecycle + inspection of already-trained
artifacts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.service import GovernanceService
from src.ml.models.promotion import propose_promotion
from src.ml.models.registry import ModelRegistry
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ml", tags=["ML Learning"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ArtifactResponse(BaseModel):
    # Pydantic v2 reserves "model_" as a protected namespace; we rename the
    # field alias to stay compatible with the existing API contract.
    model_config = {"protected_namespaces": ()}

    id: str
    model_name: str
    version: int
    storage_uri: str
    metrics: Dict[str, Any]
    active: bool
    promoted_at: Optional[str] = None
    promoted_by: Optional[str] = None
    promoted_by_decision_id: Optional[str] = None
    trained_by: str
    training_duration_sec: Optional[float] = None
    training_samples: Optional[int] = None
    created_at: Optional[str] = None


class PromoteRequest(BaseModel):
    via_governance: bool = Field(
        default=True,
        description="If true, create a DecisionRun and wait for approval. "
                    "If false, promote immediately (admin-only).",
    )


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _tenant_id(
    x_tenant_id: UUID = Header(default=UUID("00000000-0000-0000-0000-000000000000")),
) -> UUID:
    return x_tenant_id


def _user_id(x_user_id: str = Header(default="api_user")) -> str:
    return x_user_id


async def _registry(
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> ModelRegistry:
    return ModelRegistry(session=db, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/models", response_model=List[str])
async def list_models(registry: ModelRegistry = Depends(_registry)):
    return await registry.list_models()


@router.get("/models/{model_name}/versions", response_model=List[ArtifactResponse])
async def list_versions(
    model_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    registry: ModelRegistry = Depends(_registry),
):
    versions = await registry.list_versions(model_name, limit=limit)
    return [ArtifactResponse(**ModelRegistry.to_dict(v)) for v in versions]


@router.get("/models/{model_name}/active", response_model=ArtifactResponse)
async def get_active_version(
    model_name: str,
    registry: ModelRegistry = Depends(_registry),
):
    active = await registry.get_active(model_name)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active version for '{model_name}'",
        )
    return ArtifactResponse(**ModelRegistry.to_dict(active))


@router.post("/models/{model_name}/versions/{artifact_id}/promote", response_model=Dict[str, Any])
async def promote_version(
    model_name: str,
    artifact_id: UUID,
    request: PromoteRequest,
    tenant_id: UUID = Depends(_tenant_id),
    user: str = Depends(_user_id),
    db: AsyncSession = Depends(get_session),
):
    """
    Promote a trained version to active.

    With `via_governance=true` (default), this opens a DecisionRun of type
    `model_promotion`. The policy auto-approves low-risk promotions
    (WMAPE improved, delta within bounds) and requires human approval
    otherwise. When auto-approved, the artifact is promoted in the same
    request; otherwise, promotion waits for the approval workflow.
    """
    registry = ModelRegistry(session=db, tenant_id=tenant_id)
    artifact = await registry.get(artifact_id)
    if artifact is None or artifact.model_name != model_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    if not request.via_governance:
        promoted = await registry.promote(
            artifact_id=artifact_id,
            decision_id=None,
            promoted_by=user,
        )
        return {
            "status": "promoted",
            "artifact": ModelRegistry.to_dict(promoted),
            "decision_id": None,
        }

    # Governance-mediated path
    baseline = await registry.get_active(model_name)
    baseline_metrics = baseline.metrics if baseline else None

    governance = GovernanceService(db=db, tenant_id=tenant_id)
    try:
        decision = await propose_promotion(
            governance=governance,
            artifact=artifact,
            baseline_metrics=baseline_metrics,
            proposed_by=user,
        )
    except Exception as e:
        logger.error(f"Governance proposal failed for {artifact_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to open governance decision: {e}",
        )

    promoted_artifact = None
    if decision.get("status") == "approved":
        try:
            decision_id = UUID(decision["id"])
            promoted = await registry.promote(
                artifact_id=artifact_id,
                decision_id=decision_id,
                promoted_by=user,
            )
            promoted_artifact = ModelRegistry.to_dict(promoted)
        except Exception as e:
            logger.warning(f"Auto-promotion post-approval failed: {e}")

    return {
        "status": "awaiting_approval" if promoted_artifact is None else "promoted",
        "decision_id": decision.get("id"),
        "decision_status": decision.get("status"),
        "artifact": promoted_artifact or ModelRegistry.to_dict(artifact),
    }
