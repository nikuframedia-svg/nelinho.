"""Q.20.A — core.etl_run audit table.

Every ERP→Postgres sync (Q.20 mirrors: master_data, molds, skills,
quality, time_mining) writes one ``core.etl_run`` row recording the
source, timing, row counts and outcome. This satisfies the project
invariant *"audit trail intact"* for the new data-integration surface —
"why does the system have this data" is answerable without ``git blame``.

The table is tenant-scoped (``TenantBase``): ``id``, ``tenant_id``,
``created_at``, ``updated_at`` plus the run-specific columns.

Revision ID: 047_etl_run_audit
Revises: 046_tenant_configuration_source
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op


revision = "047_etl_run_audit"
down_revision = "046_tenant_configuration_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etl_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_inserted", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_etl_run_tenant_id", "etl_run", ["tenant_id"], schema="core",
    )
    op.create_index(
        "ix_core_etl_run_source", "etl_run", ["source"], schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_core_etl_run_source", table_name="etl_run", schema="core")
    op.drop_index("ix_core_etl_run_tenant_id", table_name="etl_run", schema="core")
    op.drop_table("etl_run", schema="core")
