"""ProdPlan ONE — User model (Sprint Q.22.A).

Durable backing store for the identity carried in JWT access tokens.
The JWT ``sub`` claim is a ``user_id``; this table resolves it to the
human-readable ``email`` / ``name`` / ``role`` that ``GET /v1/auth/me``
returns to the frontend Sidebar.

Until JWT is fully wired across the API, ``/v1/auth/me`` derives the
identity from request headers (dev fallback). When an ``X-User-Id``
header *does* match a ``shared.users`` row for the request tenant, the
endpoint upgrades to the real persisted profile. It never 404s — the
frontend always needs a usable ``CurrentUser``.
"""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class User(TenantBase):
    """A named identity scoped to a tenant.

    ``id`` matches the JWT ``sub`` claim. ``email`` is unique within a
    tenant — the same address may legitimately exist under a different
    tenant. ``role`` is one of the RBAC roles in
    :mod:`src.shared.auth.rbac` (``admin_platform``, ``manager_operations``,
    ``ceo``, ...); it is stored as a free-form string so a role rename
    does not require a migration.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        {"schema": "shared"},
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
