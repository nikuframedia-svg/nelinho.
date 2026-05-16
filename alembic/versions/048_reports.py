"""Sprint Q.22.D — `reports` schema: report_schedule + report_run.

The reports module is net-new. ``report_schedule`` holds recurring
report definitions (type + cron + recipients + retention policy);
``report_run`` records each execution (ad-hoc or schedule-driven) with
the generated payload and delivery outcome.

The ``reports`` schema is created here (and added to the bootstrap
``_SCHEMAS`` tuple) so a from-scratch DB has it before the tables land.

Revision ID: 048_reports
Revises: 047_production_error
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "048_reports"
down_revision = "047_production_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS reports")

    op.create_table(
        "report_schedule",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("cron", sa.String(120), nullable=False),
        sa.Column("recipients", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("format", sa.String(16), nullable=False, server_default="csv"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("retention_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="reports",
    )
    op.create_index("ix_report_schedule_tenant_id", "report_schedule", ["tenant_id"], schema="reports")
    op.create_index(
        "ix_report_schedule_tenant_enabled",
        "report_schedule",
        ["tenant_id", "enabled"],
        schema="reports",
    )

    op.create_table(
        "report_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", UUID(as_uuid=True), nullable=True),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_to", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="reports",
    )
    op.create_index("ix_report_run_tenant_id", "report_run", ["tenant_id"], schema="reports")
    op.create_index(
        "ix_report_run_tenant_generated",
        "report_run",
        ["tenant_id", "generated_at"],
        schema="reports",
    )
    op.create_index("ix_report_run_schedule", "report_run", ["schedule_id"], schema="reports")


def downgrade() -> None:
    op.drop_index("ix_report_run_schedule", table_name="report_run", schema="reports")
    op.drop_index("ix_report_run_tenant_generated", table_name="report_run", schema="reports")
    op.drop_index("ix_report_run_tenant_id", table_name="report_run", schema="reports")
    op.drop_table("report_run", schema="reports")
    op.drop_index("ix_report_schedule_tenant_enabled", table_name="report_schedule", schema="reports")
    op.drop_index("ix_report_schedule_tenant_id", table_name="report_schedule", schema="reports")
    op.drop_table("report_schedule", schema="reports")
