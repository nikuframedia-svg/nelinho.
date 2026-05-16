"""Q.22.A — shared.users table.

Durable identity store behind ``GET /v1/auth/me``. The JWT ``sub``
claim is a ``user_id``; this table resolves it to the human-readable
``email`` / ``name`` / ``role`` the frontend Sidebar renders.

Tenant-scoped (``TenantBase``): ``id``, ``tenant_id``, ``created_at``,
``updated_at`` plus ``email`` / ``name`` / ``role``. ``email`` is unique
within a tenant (``uq_users_tenant_email``).

Revision ID: 048_user_table
Revises: 047_etl_run_audit
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op


revision = "048_user_table"
down_revision = "047_etl_run_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS shared")
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        schema="shared",
    )
    op.create_index(
        "ix_shared_users_tenant_id", "users", ["tenant_id"], schema="shared",
    )


def downgrade() -> None:
    op.drop_index("ix_shared_users_tenant_id", table_name="users", schema="shared")
    op.drop_table("users", schema="shared")
