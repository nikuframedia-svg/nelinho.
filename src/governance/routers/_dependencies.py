"""Shared FastAPI dependencies for governance sub-routers.

Q.67.6.B5 — extracted from the original ``src/governance/api.py`` so the four
sub-routers (policies, decisions, timeline, rbac) can share the same
``GovernanceService`` builder + tenant/user header dependencies without
re-declaring them.

Sprint Q.12 Onda 0.1 history: tenant/user headers are fail-closed (401 when
missing). Sprint Q.18.A.1 history: irreversible ops (bulk, payload patch,
execute, rollback, kill-switch) require :func:`require_admin` — not just an
authenticated user.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import (
    AdminContext,
    require_admin,
    require_tenant_header,
    require_user_header,
)
from src.shared.database import get_session

from ..service import GovernanceService

# Public re-exports — kept as module-level names so tests / external code
# can monkeypatch the same handles the legacy ``api.py`` exposed.
get_tenant_id = require_tenant_header
get_current_user = require_user_header


async def get_governance_service(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_session),
) -> GovernanceService:
    """Get governance service with DB session."""
    return GovernanceService(db=db, tenant_id=tenant_id)


__all__ = [
    "AdminContext",
    "get_current_user",
    "get_governance_service",
    "get_tenant_id",
    "require_admin",
    "require_tenant_header",
    "require_user_header",
]
