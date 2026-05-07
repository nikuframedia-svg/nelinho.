"""Q.17.C — REST endpoints for tenant_rule lifecycle.

Mounted under ``/v1/governance/yaml-policy/`` via the parent governance
router. Six endpoints:

- ``POST   /rules/propose``           — NL → LLM → validated rule (status=proposed)
- ``GET    /rules``                   — list rules with optional status filter
- ``GET    /rules/{rule_id}``         — single rule detail + revisions
- ``POST   /rules/{rule_id}/approve`` — admin/manager: proposed → active
- ``POST   /rules/{rule_id}/reject``  — admin/manager: proposed → rejected
- ``POST   /rules/{rule_id}/suspend`` — admin/manager: active → suspended
- ``POST   /rules/{rule_id}/rollback``— admin: any → rolled_back

Always-human-approval (Luis 2026-05-06): the propose endpoint never
auto-activates. The approve endpoint requires manager+ role.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.yaml_policy.models import RuleLifecycleStatus
from src.governance.yaml_policy.nl_translator import (
    RuleTranslationError,
    translate_nl_to_rule,
)
from src.governance.yaml_policy.safety_checks import RuleSafetyError
from src.governance.yaml_policy.service import (
    RuleProposalError,
    RuleProposalService,
    serialize_rule,
)
from src.shared.auth.headers import (
    AdminContext,
    require_admin,
    require_tenant_header,
    require_user_uuid,
)
from src.shared.database import get_session

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/yaml-policy", tags=["YAML Policy (Q.17)"])


# ---------------------------------------------------------------------------
# Request/response shapes
# ---------------------------------------------------------------------------


class ProposeRuleRequest(BaseModel):
    nl_text: str = Field(
        ..., min_length=4, max_length=2000,
        description="Natural-language rule description in PT-PT.",
    )


class ApprovalRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class RejectionRequest(BaseModel):
    reason: str = Field(..., min_length=4, max_length=2000)


class RollbackRequest(BaseModel):
    reason: str = Field(..., min_length=4, max_length=2000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/rules/propose", status_code=status.HTTP_201_CREATED)
async def propose_rule(
    body: ProposeRuleRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """NL → LLM → validated rule. Persists as ``status=proposed``.

    Returns the full rule shape so the frontend can render the diff
    modal immediately. Requires admin to approve before activation.
    """
    try:
        rule = await translate_nl_to_rule(body.nl_text)
    except RuleTranslationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "translation_failed",
                "message": str(exc),
                "last_validation_error": exc.last_validation_error,
            },
        ) from exc

    svc = RuleProposalService(session, tenant_id)
    try:
        row = await svc.propose(
            rule=rule,
            proposed_by_user_id=user_id,
            nl_source=body.nl_text,
        )
    except RuleProposalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await session.commit()
    return {"rule": serialize_rule(row)}


@router.get("/rules")
async def list_rules(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    parsed_status: RuleLifecycleStatus | None = None
    if status_filter:
        try:
            parsed_status = RuleLifecycleStatus(status_filter)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown status_filter {status_filter!r}; allowed: {[s.value for s in RuleLifecycleStatus]}",
            ) from exc
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be in [1, 200]")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    svc = RuleProposalService(session, tenant_id)
    rows = await svc.list_rules(status=parsed_status, limit=limit, offset=offset)
    return {"rules": [serialize_rule(r) for r in rows], "total": len(rows)}


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RuleProposalService(session, tenant_id)
    row = await svc.get_rule(rule_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"rule {rule_id!r} not found")
    revisions = await svc.get_revisions(row.id)
    return {
        "rule": serialize_rule(row),
        "revisions": [
            {
                "id": str(rev.id),
                "action": rev.action.value,
                "actor_user_id": str(rev.actor_user_id) if rev.actor_user_id else None,
                "reason": rev.reason,
                "created_at": rev.created_at.isoformat() if rev.created_at else None,
            }
            for rev in revisions
        ],
    }


@router.post("/rules/{rule_id}/approve")
async def approve_rule(
    rule_id: str,
    body: ApprovalRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    _admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RuleProposalService(session, tenant_id)
    try:
        row = await svc.approve(rule_id=rule_id, approver_user_id=user_id, reason=body.reason)
    except RuleSafetyError as exc:
        # Q.17.E — surface axiom + conflict violations as structured 422
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "safety_check_failed",
                "violations": [
                    {
                        "code": v.code,
                        "severity": v.severity,
                        "detail": v.detail,
                        "context": v.context,
                    }
                    for v in exc.violations
                ],
            },
        ) from exc
    except RuleProposalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return {"rule": serialize_rule(row)}


@router.post("/rules/{rule_id}/reject")
async def reject_rule(
    rule_id: str,
    body: RejectionRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    _admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RuleProposalService(session, tenant_id)
    try:
        row = await svc.reject(rule_id=rule_id, actor_user_id=user_id, reason=body.reason)
    except RuleProposalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return {"rule": serialize_rule(row)}


@router.post("/rules/{rule_id}/suspend")
async def suspend_rule(
    rule_id: str,
    body: ApprovalRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    _admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RuleProposalService(session, tenant_id)
    try:
        row = await svc.suspend(rule_id=rule_id, actor_user_id=user_id, reason=body.reason)
    except RuleProposalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return {"rule": serialize_rule(row)}


@router.post("/rules/{rule_id}/rollback")
async def rollback_rule(
    rule_id: str,
    body: RollbackRequest,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    _admin: AdminContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = RuleProposalService(session, tenant_id)
    try:
        row = await svc.rollback(rule_id=rule_id, actor_user_id=user_id, reason=body.reason)
    except RuleProposalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return {"rule": serialize_rule(row)}
