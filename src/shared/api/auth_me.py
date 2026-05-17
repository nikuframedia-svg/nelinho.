"""GET /v1/auth/me — minimal "current user" endpoint.

Sprint Q.18.UI.A.1 · upgraded Q.22.A (real ``shared.users`` lookup).

Does what it says: returns identity + role + tenant for the request,
in a shape the frontend Sidebar can consume to render the user chip.

Resolution order:

1. If the request carries an ``X-User-Id`` (or, later, a JWT ``sub``)
   that matches a :class:`~src.shared.models.user.User` row for the
   request tenant → return that row's real ``email`` / ``name`` / ``role``.
2. Otherwise (dev without a populated table, or an unknown id) → derive
   a usable payload from the legacy headers (``X-Tenant-Id``,
   ``X-User-*``, ``X-Umwelt``).

This endpoint **never 404s**: the frontend boot (Sidebar chip,
UmweltSwitcher, role-gating) always needs a usable ``CurrentUser``.
The route, the response model and the ``umwelt`` field are a stable
contract — frontend ``lib/api.ts`` ``authApi.me()`` depends on them.

Once ``get_current_user`` (jwt_handler.py) is wired across the API the
header dependency is swapped for the JWT one without changing the
response shape.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(prefix="/v1/auth", tags=["auth"])

_log = logging.getLogger("auth.me")


class CurrentUser(BaseModel):
    """Identity payload returned by /v1/auth/me.

    Stable contract — frontend consumers (Sidebar chip, role-gating in
    pages) depend on these field names.
    """

    user_id: UUID | None = Field(
        default=None,
        description="User UUID; null until JWT is wired (dev/test).",
    )
    tenant_id: UUID = Field(description="Resolved tenant UUID for the request.")
    role: str = Field(
        default="manager",
        description=(
            "Role hint. Falls back to 'manager' until RBAC is fully wired. "
            "When JWT lands, comes from the token claim."
        ),
    )
    name: str = Field(
        default="Gestor",
        description="Display name for the user chip.",
    )
    email: str = Field(
        default="—",
        description="Display email; '—' placeholder when no User row matches.",
    )
    umwelt: str = Field(
        default="manager",
        description=(
            "Operating mode: 'manager' (default), 'operator' (kiosk), or "
            "'ceo' (read-only KPIs). Used by the UmweltSwitcher."
        ),
    )


async def _lookup_user(
    session: AsyncSession, tenant_id: UUID, user_uuid: UUID
):
    """Return the ``shared.users`` row for this id+tenant, or ``None``.

    Tenant-scoped: a user belonging to another tenant is invisible.
    Any DB / schema error is swallowed and treated as "no match" so the
    endpoint degrades to the header fallback instead of failing.
    """
    from src.shared.models.user import User

    try:
        result = await session.execute(
            select(User).where(
                User.id == user_uuid,
                User.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()
    except Exception as exc:  # pragma: no cover — DB/schema unavailable in dev
        _log.debug("auth/me user lookup failed, using header fallback: %s", exc)
        return None


@router.get("/me", response_model=CurrentUser)
async def get_me(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_umwelt: str | None = Header(default=None, alias="X-Umwelt"),
) -> CurrentUser:
    """Return the current user identity.

    When ``X-User-Id`` matches a real ``shared.users`` row for the
    request tenant, the persisted profile wins. Otherwise every field
    falls back to a safe placeholder derived from the request headers,
    so dev clients (frontend ``lib/api.ts`` request helper) always get
    a usable payload without a real auth flow.
    """
    user_uuid: UUID | None = None
    if x_user_id:
        try:
            user_uuid = UUID(x_user_id)
        except (TypeError, ValueError):
            user_uuid = None

    # 1. Real User row — persisted profile wins when it exists.
    if user_uuid is not None:
        user = await _lookup_user(session, tenant_id, user_uuid)
        if user is not None:
            role = (user.role or "manager").strip().lower() or "manager"
            # Umwelt still honours an explicit X-Umwelt override (the
            # UmweltSwitcher lets a user view another mode); else the role.
            umwelt = (x_umwelt or role).strip().lower() or "manager"
            return CurrentUser(
                user_id=user.id,
                tenant_id=tenant_id,
                role=role,
                name=(user.name or "Gestor").strip() or "Gestor",
                email=(user.email or "—").strip() or "—",
                umwelt=umwelt,
            )

    # 2. Header-derived fallback — dev / no JWT / unknown user id.
    role = (x_user_role or "manager").strip().lower() or "manager"
    umwelt = (x_umwelt or role).strip().lower() or "manager"
    name = (x_user_name or "Gestor").strip() or "Gestor"
    email = (x_user_email or "—").strip() or "—"

    return CurrentUser(
        user_id=user_uuid,
        tenant_id=tenant_id,
        role=role,
        name=name,
        email=email,
        umwelt=umwelt,
    )
