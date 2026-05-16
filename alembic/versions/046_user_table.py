"""Sprint Q.22.A — `shared.users` table.

The JWT access token carries an opaque ``sub`` (user_id) plus ``role``,
but the system had no persistent identity store — ``/v1/me`` had no row
to resolve a real ``email`` / ``name`` from. This table is the minimal
backing store: one row per named identity, scoped to a tenant.

``email`` is unique within a tenant (the same address may legitimately
exist under a different tenant in the multi-tenant deployment).

Revision ID: 046_user_table
Revises: 045_rule_firing_variant_index
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "046_user_table"
down_revision = "045_rule_firing_variant_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        schema="shared",
    )
    op.create_index(
        "ix_shared_users_tenant_id",
        "users",
        ["tenant_id"],
        schema="shared",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shared_users_tenant_id",
        table_name="users",
        schema="shared",
    )
    op.drop_table("users", schema="shared")
