"""
Governance API — Learning Metrics Endpoints (Sprint R.1)
==========================================================

Read-only endpoints that power the Aprendizagem panel in
``/admin/settings``. Three GETs, one per layer the panel surfaces:

* ``GET /v1/governance/learning/pairs``   — Camada 3 bootstrap (DPO)
* ``GET /v1/governance/learning/rules``   — Camada 1 detector state
* ``GET /v1/governance/learning/weights`` — Camada 2 last retrain

The tenant header pattern matches ``api_preference_rules.py`` so the
panel can call all four endpoints with the same auth shim. No write
paths here — observability only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.preference_learning import (
    DEFAULT_MIN_REASON_LEN,
    LearningMetricsService,
)
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/governance/learning", tags=["Governance"])


# ─── Dependencies ────────────────────────────────────────────────────────


from src.shared.auth.headers import require_tenant_header

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID default.
_tenant_id = require_tenant_header


async def _service(
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> LearningMetricsService:
    return LearningMetricsService(session=session, tenant_id=tenant_id)


# ─── Schemas ─────────────────────────────────────────────────────────────


class PairStatsResponse(BaseModel):
    total_commits_with_rejection: int
    total_pairs: int
    eligible_for_dpo: int
    by_category: Dict[str, int]
    by_weekday: Dict[str, int]
    last_30d: Dict[str, int]
    last_90d: Dict[str, int]
    abl_pairs_today: int
    min_reason_len: int


class RuleStatsResponse(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    last_detector_run_at: str | None = None
    rules_re_emitted_count: int


class WeightStatsResponse(BaseModel):
    status: str
    current_weights: Dict[str, float]
    default_weights: Dict[str, float]
    multipliers: Dict[str, float]
    pairs_used: int
    commits_scanned: int
    trained_at: str | None = None
    blend_learned_pct: float
    min_pairs_threshold: int
    reason: str | None = None


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("/pairs", response_model=PairStatsResponse)
async def get_pair_stats(
    window_days: int = Query(90, ge=1, le=365),
    min_reason_len: int = Query(DEFAULT_MIN_REASON_LEN, ge=0, le=500),
    service: LearningMetricsService = Depends(_service),
) -> PairStatsResponse:
    """How many DPO pairs are sitting in commits + how many are usable."""
    stats = await service.pair_stats(
        window_days=window_days,
        min_reason_len=min_reason_len,
    )
    return PairStatsResponse(**stats.to_dict())


@router.get("/rules", response_model=RuleStatsResponse)
async def get_rule_stats(
    service: LearningMetricsService = Depends(_service),
) -> RuleStatsResponse:
    """Rule counts by status × type plus a re-emit hint."""
    stats = await service.rule_stats()
    return RuleStatsResponse(**stats.to_dict())


@router.get("/weights", response_model=WeightStatsResponse)
async def get_weight_stats(
    service: LearningMetricsService = Depends(_service),
) -> WeightStatsResponse:
    """Last persisted retrain payload (or defaults if never trained)."""
    stats = await service.weight_stats()
    return WeightStatsResponse(**stats.to_dict())


# Sprint R.4 — last-N retrains for the audit modal.
class WeightHistoryEntry(BaseModel):
    trained_at: str | None = None
    valid_from: str | None = None
    status: str | None = None
    weights: Dict[str, float]
    multipliers: Dict[str, float]
    pairs_used: int
    explanations: list[Dict[str, Any]]
    warnings: list[Dict[str, Any]]


class WeightHistoryResponse(BaseModel):
    entries: list[WeightHistoryEntry]


@router.get("/weights/history", response_model=WeightHistoryResponse)
async def get_weight_history(
    limit: int = Query(12, ge=1, le=104),
    service: LearningMetricsService = Depends(_service),
) -> WeightHistoryResponse:
    """Sprint R.4 — last ``limit`` retrain versions (newest first)."""
    rows = await service.weight_history(limit=limit)
    return WeightHistoryResponse(
        entries=[WeightHistoryEntry(**r) for r in rows],
    )


# ─── Sprint R.5.3 — adapter promote / rollback ───────────────────────────


_ADAPTER_CONFIG_CATEGORY = "governance"
_ADAPTER_CONFIG_KEY = "active_lora_adapter"
_ADAPTER_HISTORY_KEY = "active_lora_adapter_previous"


from src.shared.auth.headers import AdminContext, require_admin

# Sprint Q.12 Onda 0.2: replaced unsigned ``X-User-Role`` admin gate
# with ``require_admin``. Production now requires a Bearer JWT; dev
# still accepts the legacy headers so existing tests pass.


def _coerce_user_uuid(user_id: str):
    from uuid import UUID as _UUID

    try:
        return _UUID(user_id)
    except (TypeError, ValueError):
        return None


class AdapterPromoteRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=20,
        description="Why this adapter was promoted (≥20 chars, audit trail).",
    )
    decided_by: str = Field(default="unknown", max_length=255)
    intent_match_rate: float | None = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Eval result that justified the promote (audit only).",
    )
    safety_violations_count: int | None = Field(
        default=None, ge=0,
    )


class AdapterRollbackRequest(BaseModel):
    reason: str = Field(..., min_length=20)
    decided_by: str = Field(default="unknown", max_length=255)


class AdapterStateResponse(BaseModel):
    active_version: str | None = None
    promoted_at: str | None = None
    promoted_by: str | None = None
    reason: str | None = None
    intent_match_rate: float | None = None
    safety_violations_count: int | None = None
    has_previous: bool = False


@router.get("/adapter", response_model=AdapterStateResponse)
async def get_active_adapter(
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> AdapterStateResponse:
    """Return the adapter currently in effect (if any)."""
    from src.core.services.tenant_config_service import TenantConfigService

    svc = TenantConfigService(session, tenant_id)
    payload = await svc.get(_ADAPTER_CONFIG_CATEGORY, _ADAPTER_CONFIG_KEY, default=None)
    previous = await svc.get(_ADAPTER_CONFIG_CATEGORY, _ADAPTER_HISTORY_KEY, default=None)
    if not isinstance(payload, dict):
        return AdapterStateResponse(has_previous=isinstance(previous, dict))
    return AdapterStateResponse(
        active_version=payload.get("version"),
        promoted_at=payload.get("promoted_at"),
        promoted_by=payload.get("promoted_by"),
        reason=payload.get("reason"),
        intent_match_rate=payload.get("intent_match_rate"),
        safety_violations_count=payload.get("safety_violations_count"),
        has_previous=isinstance(previous, dict),
    )


@router.post("/adapter/promote/{version}", response_model=AdapterStateResponse)
async def promote_adapter(
    version: str,
    body: AdapterPromoteRequest,
    tenant_id: UUID = Depends(_tenant_id),
    admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdapterStateResponse:
    """Sprint R.5.3 — promote a candidate LoRA adapter to active.

    Stores the previous adapter as ``active_lora_adapter_previous`` so
    rollback (next endpoint) is a one-call restore. Audit trail lives
    in TenantConfig history automatically.
    """
    if not version or not version.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="version path parameter is required",
        )
    from src.core.services.tenant_config_service import TenantConfigService

    svc = TenantConfigService(session, tenant_id)
    user_uuid = _coerce_user_uuid(admin.user_id)

    # Snapshot the current active adapter as the rollback target.
    current = await svc.get(_ADAPTER_CONFIG_CATEGORY, _ADAPTER_CONFIG_KEY, default=None)
    if isinstance(current, dict):
        await svc.set(
            category=_ADAPTER_CONFIG_CATEGORY,
            key=_ADAPTER_HISTORY_KEY,
            value=current,
            user_id=user_uuid,
            data_type="json",
        )

    payload = {
        "version": version.strip(),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "promoted_by": body.decided_by,
        "reason": body.reason.strip(),
        "intent_match_rate": body.intent_match_rate,
        "safety_violations_count": body.safety_violations_count,
    }
    await svc.set(
        category=_ADAPTER_CONFIG_CATEGORY,
        key=_ADAPTER_CONFIG_KEY,
        value=payload,
        user_id=user_uuid,
        data_type="json",
    )
    await session.commit()
    return AdapterStateResponse(
        active_version=payload["version"],
        promoted_at=payload["promoted_at"],
        promoted_by=payload["promoted_by"],
        reason=payload["reason"],
        intent_match_rate=payload["intent_match_rate"],
        safety_violations_count=payload["safety_violations_count"],
        has_previous=True,
    )


@router.post("/adapter/rollback", response_model=AdapterStateResponse)
async def rollback_adapter(
    body: AdapterRollbackRequest = Body(default_factory=AdapterRollbackRequest),
    tenant_id: UUID = Depends(_tenant_id),
    admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdapterStateResponse:
    """Sprint R.5.3 — restore the previous adapter as active.

    Errors with 409 if there is no previous version to roll back to
    (i.e. promote was never called twice).
    """
    from src.core.services.tenant_config_service import TenantConfigService

    svc = TenantConfigService(session, tenant_id)
    previous = await svc.get(
        _ADAPTER_CONFIG_CATEGORY, _ADAPTER_HISTORY_KEY, default=None,
    )
    if not isinstance(previous, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No previous adapter to roll back to",
        )

    user_uuid = _coerce_user_uuid(admin.user_id)
    payload = {
        **previous,
        "rollback_reason": body.reason.strip(),
        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        "rolled_back_by": body.decided_by,
    }
    await svc.set(
        category=_ADAPTER_CONFIG_CATEGORY,
        key=_ADAPTER_CONFIG_KEY,
        value=payload,
        user_id=user_uuid,
        data_type="json",
    )
    await session.commit()
    return AdapterStateResponse(
        active_version=payload.get("version"),
        promoted_at=payload.get("promoted_at"),
        promoted_by=payload.get("promoted_by"),
        reason=payload.get("reason"),
        intent_match_rate=payload.get("intent_match_rate"),
        safety_violations_count=payload.get("safety_violations_count"),
        has_previous=False,
    )
