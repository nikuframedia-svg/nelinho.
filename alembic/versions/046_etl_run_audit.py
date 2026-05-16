"""Q.20.A — `core.etl_run` ETL audit table.

The Nelo ERP→Postgres sync (Q.20) writes one row per mirror execution:
which source, when, how many rows in/out, and the outcome. Without it a
nightly sync is a black box — an operator can't tell whether last
night's run actually moved data or silently no-op'd.

Schema mirrors `src.infrastructure.erp.etl.models.EtlRun`.

Revision ID: 046_etl_run_audit
Revises: 045_rule_firing_variant_index
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "046_etl_run_audit"
down_revision = "045_rule_firing_variant_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etl_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="running",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_read", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        schema="core",
    )
    op.create_index(
        "ix_core_etl_run_tenant_id", "etl_run", ["tenant_id"], schema="core",
    )
    op.create_index(
        "ix_core_etl_run_source", "etl_run", ["source"], schema="core",
    )
    # Hot path: "latest run per source" for the sync-status surface.
    op.create_index(
        "ix_etl_run_source_started",
        "etl_run",
        ["source", sa.text("started_at DESC")],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_etl_run_source_started", table_name="etl_run", schema="core")
    op.drop_index("ix_core_etl_run_source", table_name="etl_run", schema="core")
    op.drop_index("ix_core_etl_run_tenant_id", table_name="etl_run", schema="core")
    op.drop_table("etl_run", schema="core")
