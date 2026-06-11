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
from starlette.requests import Request

from src.governance.service import GovernanceService
from src.ml.models.promotion import propose_promotion
from src.ml.models.registry import ModelRegistry
from src.shared.auth.headers import AdminContext
from src.shared.config import settings
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/ml", tags=["ML Learning"])

# ---------------------------------------------------------------------------
# Q.115.U — modelos em memória (singleton por processo)
# ---------------------------------------------------------------------------

# Q.170.F — os endpoints /sequence-risk e /throughput-forecast foram
# REMOVIDOS: os globals nunca eram atribuídos em lado nenhum (404 permanente
# desde Q.115.U — achado CRITICAL da auditoria, violação do invariante #8),
# o retrain job treina e DEITA FORA o modelo (devolve só métricas), lê de
# fases_of_history (VAZIA em produção desde Q.150) e zero consumidores
# (frontend/copiloto). Os modelos (models_domain/sequence_mining.py,
# throughput_forecast.py) e os jobs ficam como fundação: religar = repontar
# o treino para factory_raw.of_fp + publicar o modelo treinado num registry
# que a API leia (campanha própria, se a feature for pedida).


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

from src.shared.auth.headers import require_tenant_header, require_user_header

_tenant_id = require_tenant_header
_user_id = require_user_header


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


def _optional_admin(
    request: Request,
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
) -> Optional[AdminContext]:
    """Like ``require_admin`` but returns None instead of raising when
    the caller isn't admin. Lets a single endpoint accept anonymous
    callers on its safe path while gating its admin-only path
    (FASE 2.1 / CRIT-02 — `via_governance=false` requires admin).
    """
    from src.shared.auth.headers import (
        AdminContext,
        _ADMIN_ROLES,
        _try_jwt,
    )
    payload = _try_jwt(request)
    if payload is not None and payload.role.lower() in _ADMIN_ROLES:
        return AdminContext(user_id=payload.sub, role=payload.role, source="jwt")
    if settings.environment == "production":
        return None
    if x_user_role and x_user_role.lower() in _ADMIN_ROLES:
        x_user_id = request.headers.get("x-user-id") or request.headers.get("X-User-Id")
        return AdminContext(
            user_id=(x_user_id or "").strip() or "admin",
            role=x_user_role.lower(),
            source="legacy_header",
        )
    return None


@router.post("/models/{model_name}/versions/{artifact_id}/promote", response_model=Dict[str, Any])
async def promote_version(
    model_name: str,
    artifact_id: UUID,
    request: PromoteRequest,
    tenant_id: UUID = Depends(_tenant_id),
    user: str = Depends(_user_id),
    admin: Optional[AdminContext] = Depends(_optional_admin),
    db: AsyncSession = Depends(get_session),
):
    """
    Promote a trained version to active.

    With `via_governance=true` (default), this opens a DecisionRun of type
    `model_promotion`. The policy auto-approves low-risk promotions
    (WMAPE improved, delta within bounds) and requires human approval
    otherwise. When auto-approved, the artifact is promoted in the same
    request; otherwise, promotion waits for the approval workflow.

    With `via_governance=false`, the artifact is promoted immediately
    without going through governance — this bypasses the audit trail and
    is reserved for **admins only** (FASE 2.1 / CRIT-02). Non-admin
    callers are rejected with 403.
    """
    registry = ModelRegistry(session=db, tenant_id=tenant_id)
    artifact = await registry.get(artifact_id)
    if artifact is None or artifact.model_name != model_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    if not request.via_governance:
        # FASE 2.1 (CRIT-02) — admin gate. Only admins may bypass governance.
        if admin is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "via_governance=false requires an admin role. "
                    "Either set via_governance=true to flow through governance, "
                    "or call this endpoint as admin (Bearer JWT in production, "
                    "X-User-Role: admin in dev)."
                ),
            )
        promoted = await registry.promote(
            artifact_id=artifact_id,
            decision_id=None,
            promoted_by=admin.user_id,
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


# ---------------------------------------------------------------------------
# Q.115.U — SequenceMining endpoint



# ---------------------------------------------------------------------------
# Q.115.U — Drift endpoint
# ---------------------------------------------------------------------------

class DriftEventResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str
    feature_name: Optional[str] = None
    metric: str
    value: float
    threshold: float
    severity: str
    detected_at: Optional[str] = None


@router.get("/drift", response_model=List[DriftEventResponse])
async def get_drift_events(
    model_name: str = Query(..., description="Nome do modelo ML"),
    since: str = Query(default="7d", description="Período: ex '7d', '30d'"),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """
    GET /v1/ml/drift?model_name=X&since=7d

    Lista eventos de drift registados para o modelo no período dado.
    """
    from datetime import timedelta
    from sqlalchemy import select, and_

    from src.ml.models.drift_event import DriftEvent

    # Parse "7d" → timedelta
    try:
        days = int(since.rstrip("d"))
        cutoff = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ) - timedelta(days=days)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"since inválido: '{since}'. Use formato '7d' ou '30d'.",
        )

    stmt = (
        select(DriftEvent)
        .where(
            and_(
                DriftEvent.tenant_id == tenant_id,
                DriftEvent.model_name == model_name,
                DriftEvent.detected_at >= cutoff,
            )
        )
        .order_by(DriftEvent.detected_at.desc())
        .limit(200)
    )
    try:
        result = await db.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:
        # F4.E — padrão Q.170.G: a lista vazia continua a ser o contrato
        # (o painel mostra "sem drift" em vez de rebentar), mas a falha
        # deixa de ser invisível — fica contada em silent_fallback_total.
        logger.warning("drift endpoint: query falhou: %s", exc)
        try:
            from src.shared.metrics import bump_silent_fallback
            bump_silent_fallback("ml_drift", "query_failed")
        except Exception as metric_exc:  # pragma: no cover — best-effort
            logger.debug("métrica ml_drift falhou: %s", metric_exc)
        rows = []

    return [
        DriftEventResponse(
            model_name=r.model_name,
            feature_name=r.feature_name,
            metric=r.metric,
            value=r.value,
            threshold=r.threshold,
            severity=r.severity,
            detected_at=r.detected_at.isoformat() if r.detected_at else None,
        )
        for r in rows
    ]
