"""Q.22.D — reports.report_schedule + reports.report_run tables.

Backs the report scheduling / persistence surface:

* ``report_schedule`` — a recurring report definition (Q.22.D).
* ``report_run``      — one execution; carries the generated payload
  and the delivery outcome (Q.22.E/F), pruned by retention (Q.22.G).

Both tenant-scoped (``TenantBase``): ``id`` / ``tenant_id`` /
``created_at`` / ``updated_at`` plus the report-specific columns.

Revision ID: 050_reports
Revises: 049_production_error
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "050_reports"
down_revision = "049_production_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS reports")

    op.create_table(
        "report_schedule",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("cron", sa.String(length=120), nullable=False),
        sa.Column("recipients", JSONB(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="reports",
    )
    op.create_index(
        "ix_report_schedule_tenant_enabled",
        "report_schedule", ["tenant_id", "enabled"], schema="reports",
    )

    op.create_table(
        "report_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=True),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_to", JSONB(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="reports",
    )
    op.create_index(
        "ix_report_run_tenant_generated",
        "report_run", ["tenant_id", "generated_at"], schema="reports",
    )
    op.create_index(
        "ix_report_run_schedule",
        "report_run", ["schedule_id"], schema="reports",
    )


def downgrade() -> None:
    op.drop_index("ix_report_run_schedule", table_name="report_run", schema="reports")
    op.drop_index(
        "ix_report_run_tenant_generated", table_name="report_run", schema="reports",
    )
    op.drop_table("report_run", schema="reports")
    op.drop_index(
        "ix_report_schedule_tenant_enabled",
        table_name="report_schedule", schema="reports",
    )
    op.drop_table("report_schedule", schema="reports")
