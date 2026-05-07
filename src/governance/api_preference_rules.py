"""
Governance API — Preference Rules Endpoints (Sprint E.3)
==========================================================

Thin FastAPI layer on top of ``PreferenceRuleService``. Backs the
``/admin/learned-rules`` page:

* ``GET    /v1/governance/preference-rules`` — list (filter by status,
  type, min_confidence; paged).
* ``GET    /v1/governance/preference-rules/{id}`` — single.
* ``POST   /v1/governance/preference-rules/{id}/confirm`` — operator
  confirms; optional notes.
* ``POST   /v1/governance/preference-rules/{id}/reject`` — operator
  rejects; **reason is mandatory** (audit trail).
* ``PATCH  /v1/governance/preference-rules/{id}`` — tweak description
  / predicate / confidence while the rule is still ``detected``.

Tenant + user plumbing uses the same header pattern as
``src/governance/api.py`` (``X-Tenant-ID`` / ``X-User-Id``). A real
role guard will move in once JWT lands — until then the comment in
``_assert_admin`` documents the contract so downstream reviewers see
the gap.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
)
from src.governance.preference_learning.rule_service import (
    PreferenceRuleInvalidTransitionError,
    PreferenceRuleNotFoundError,
    PreferenceRuleService,
)
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/governance/preference-rules", tags=["Governance"])


# ─── Dependencies ────────────────────────────────────────────────────────


from src.shared.auth.headers import (
    AdminContext,
    require_admin,
    require_tenant_header,
)

# Sprint Q.12 Onda 0.1: replaced silent zero-UUID/'api_user' defaults
# with fail-closed dependencies that 401 when the header is absent.
# Sprint Q.12 Onda 0.2: ``_assert_admin`` was an unsigned header check.
# Replaced by ``require_admin`` which prefers JWT and only falls back
# to legacy ``X-User-Role`` headers in non-production environments.
_tenant_id = require_tenant_header


async def _service(
    tenant_id: UUID = Depends(_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PreferenceRuleService:
    return PreferenceRuleService(session=session, tenant_id=tenant_id)


# ─── Schemas ─────────────────────────────────────────────────────────────


class PreferenceRuleResponse(BaseModel):
    id: UUID
    type: str
    description: str
    predicate: Dict[str, Any]
    confidence: float
    status: str
    detected_from_commits: List[str] = Field(default_factory=list)
    confirmed_at: Optional[str] = None
    confirmed_by: Optional[UUID] = None
    review_notes: Optional[str] = None

    @classmethod
    def from_orm_row(cls, rule: PreferenceRule) -> "PreferenceRuleResponse":
        return cls(
            id=rule.id,
            type=rule.type,
            description=rule.description,
            predicate=rule.predicate or {},
            confidence=float(rule.confidence),
            status=rule.status,
            detected_from_commits=list(rule.detected_from_commits or []),
            confirmed_at=rule.confirmed_at.isoformat() if rule.confirmed_at else None,
            confirmed_by=rule.confirmed_by,
            review_notes=rule.review_notes,
        )


class ConfirmRequest(BaseModel):
    review_notes: Optional[str] = Field(
        default=None,
        description="Optional note the operator wants saved alongside the confirm.",
    )


class RejectRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        description="Mandatory free-text justification — kept for audit.",
    )


class PatchRequest(BaseModel):
    description: Optional[str] = None
    predicate: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=List[PreferenceRuleResponse])
async def list_preference_rules(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="One of detected / confirmed / rejected",
    ),
    rule_type: Optional[str] = Query(
        None,
        alias="type",
        description="One of temporal_block / tradeoff_preference / operator_affinity / phase_threshold",
    ),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: PreferenceRuleService = Depends(_service),
) -> List[PreferenceRuleResponse]:
    try:
        rules = await service.list_rules(
            status=status_filter,
            rule_type=rule_type,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [PreferenceRuleResponse.from_orm_row(r) for r in rules]


@router.get("/{rule_id}", response_model=PreferenceRuleResponse)
async def get_preference_rule(
    rule_id: UUID,
    service: PreferenceRuleService = Depends(_service),
) -> PreferenceRuleResponse:
    try:
        rule = await service.get_rule(rule_id)
    except PreferenceRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return PreferenceRuleResponse.from_orm_row(rule)


@router.post("/{rule_id}/confirm", response_model=PreferenceRuleResponse)
async def confirm_preference_rule(
    rule_id: UUID,
    body: ConfirmRequest = Body(default_factory=ConfirmRequest),
    admin: AdminContext = Depends(require_admin),
    service: PreferenceRuleService = Depends(_service),
) -> PreferenceRuleResponse:
    user_uuid = _coerce_user_uuid(admin.user_id)
    try:
        rule = await service.confirm(
            rule_id,
            confirmed_by=user_uuid,
            review_notes=body.review_notes,
        )
    except PreferenceRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PreferenceRuleInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return PreferenceRuleResponse.from_orm_row(rule)


@router.post("/{rule_id}/reject", response_model=PreferenceRuleResponse)
async def reject_preference_rule(
    rule_id: UUID,
    body: RejectRequest,
    admin: AdminContext = Depends(require_admin),
    service: PreferenceRuleService = Depends(_service),
) -> PreferenceRuleResponse:
    user_uuid = _coerce_user_uuid(admin.user_id)
    try:
        rule = await service.reject(
            rule_id,
            rejected_by=user_uuid,
            reason=body.reason,
        )
    except PreferenceRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PreferenceRuleInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PreferenceRuleResponse.from_orm_row(rule)


@router.patch(
    "/{rule_id}",
    response_model=PreferenceRuleResponse,
    dependencies=[Depends(require_admin)],
)
async def patch_preference_rule(
    rule_id: UUID,
    body: PatchRequest,
    service: PreferenceRuleService = Depends(_service),
) -> PreferenceRuleResponse:
    try:
        rule = await service.update_metadata(
            rule_id,
            description=body.description,
            predicate=body.predicate,
            confidence=body.confidence,
        )
    except PreferenceRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PreferenceRuleInvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PreferenceRuleResponse.from_orm_row(rule)


# ─── Helpers ─────────────────────────────────────────────────────────────


def _coerce_user_uuid(user_id: str) -> UUID:
    """``X-User-Id`` may carry either a UUID (production) or an opaque
    string like ``"api_user"`` (dev). When it's not parseable we fall
    back to a zero UUID so dev tooling still works; the string is
    logged so later audits can trace the action back."""
    try:
        return UUID(user_id)
    except (TypeError, ValueError):
        logger.debug(
            "preference-rules: non-UUID X-User-Id %r, storing zero UUID",
            user_id,
        )
        return UUID("00000000-0000-0000-0000-000000000000")
