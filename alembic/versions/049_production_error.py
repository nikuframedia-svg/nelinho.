"""Q.22.C — plan.production_errors table.

Backs the ``/api/errors`` and ``/api/errors/stats`` legacy endpoints.
One row per quality defect detected against a phase of a production
order. ``order_id`` carries no FK so the ERP ingest can land error
rows even when the owning order is not yet migrated.

Tenant-scoped (``TenantBase``): ``id`` / ``tenant_id`` / ``created_at``
/ ``updated_at`` plus the defect-specific columns.

Revision ID: 049_production_error
Revises: 048_user_table
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op


revision = "049_production_error"
down_revision = "048_user_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_errors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("phase_name", sa.String(length=255), nullable=False),
        sa.Column("eval_phase_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_order",
        "production_errors", ["tenant_id", "order_id"], schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_severity",
        "production_errors", ["tenant_id", "severity"], schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_phase",
        "production_errors", ["tenant_id", "phase_name"], schema="plan",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_production_errors_tenant_phase",
        table_name="production_errors", schema="plan",
    )
    op.drop_index(
        "ix_production_errors_tenant_severity",
        table_name="production_errors", schema="plan",
    )
    op.drop_index(
        "ix_production_errors_tenant_order",
        table_name="production_errors", schema="plan",
    )
    op.drop_table("production_errors", schema="plan")
