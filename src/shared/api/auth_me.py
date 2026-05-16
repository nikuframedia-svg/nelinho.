"""
ProdPlan ONE - Current User API
================================

`GET /v1/me` resolves the identity carried in the request (JWT ``sub``
claim, or the dev/test ``X-User-Id`` header) against the ``shared.users``
table and returns the human-readable profile.

There is no placeholder fallback: an unknown user_id returns ``404`` so
the frontend renders an explicit error state rather than a fake email.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header, require_user_uuid
from src.shared.database import get_session
from src.shared.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Me"])


class MeResponse(BaseModel):
    """The current user's profile."""

    id: UUID
    email: str
    name: str
    tenant_id: UUID
    role: str


@router.get("/me", response_model=MeResponse)
async def get_me(
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: UUID = Depends(require_user_uuid),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    """Return the profile of the authenticated user.

    404 when the user_id has no row under this tenant — callers must
    handle the empty state explicitly.
    """
    result = await session.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user {user_id} under tenant {tenant_id}",
        )

    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        tenant_id=user.tenant_id,
        role=user.role,
    )
