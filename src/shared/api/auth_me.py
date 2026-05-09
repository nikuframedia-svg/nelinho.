"""GET /v1/auth/me — minimal "current user" endpoint.

Sprint Q.18.UI.A.1.

Does what it says: returns identity + role + tenant for the request,
in a shape the frontend Sidebar can consume to render the user chip.

This deliberately predates JWT integration. In dev/test the response
is derived from the legacy headers (`X-Tenant-Id`, optional
`X-User-Id`, optional `X-User-Role`) via the dev-friendly fallbacks
in :mod:`src.shared.auth.headers`. Production needs a real Bearer JWT
(same gate as the rest of the API).

Once `get_current_user` (jwt_handler.py) is wired across the API,
the dependency below is swapped without changing the response shape.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from src.shared.auth.headers import require_tenant_header

router = APIRouter(prefix="/v1/auth", tags=["auth"])


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
        description="Display email; placeholder while no User table exists.",
    )
    umwelt: str = Field(
        default="manager",
        description=(
            "Operating mode: 'manager' (default), 'operator' (kiosk), or "
            "'ceo' (read-only KPIs). Used by the UmweltSwitcher."
        ),
    )


@router.get("/me", response_model=CurrentUser)
async def get_me(
    tenant_id: UUID = Depends(require_tenant_header),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_umwelt: str | None = Header(default=None, alias="X-Umwelt"),
) -> CurrentUser:
    """Return the current user identity derived from headers / JWT.

    All optional headers default to safe placeholders so dev clients
    (frontend ``lib/api.ts`` request helper) get a usable payload
    without yet plumbing a real auth flow.
    """
    user_uuid: UUID | None = None
    if x_user_id:
        try:
            user_uuid = UUID(x_user_id)
        except (TypeError, ValueError):
            user_uuid = None

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
