"""
ProdPlan ONE - User Model
=========================

Persistent backing store for the identity carried in JWT access tokens.
The JWT ``sub`` claim is a ``user_id``; this table resolves it to the
human-readable ``email`` / ``name`` that the ``/v1/me`` endpoint returns.
"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class User(TenantBase):
    """A named identity scoped to a tenant.

    ``id`` matches the JWT ``sub`` claim. ``email`` is unique within a
    tenant (the same address may exist under a different tenant).
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
