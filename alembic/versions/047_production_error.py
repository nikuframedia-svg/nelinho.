"""Sprint Q.22.C — `plan.production_errors` table.

The legacy ``/api/errors`` and ``/api/errors/stats`` endpoints returned
hard-coded empty structures because no ``ProductionError`` model
existed. The frontend already ships the ``ProductionError`` / typed
``ErrorsStats`` interfaces and calls these endpoints — so the gap was a
missing table, not a missing feature.

Maps the Nelo ERP ``OrdemFabricoErros`` table (~89.836 rows). No FK on
``order_id`` — consistent with ``plan.production_orders`` — so the ERP
ingest can land error rows independently of order migration.

Revision ID: 047_production_error
Revises: 046_user_table
Create Date: 2026-05-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision = "047_production_error"
down_revision = "046_user_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_errors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("phase_name", sa.String(255), nullable=False),
        sa.Column("eval_phase_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", sa.Integer, nullable=False),
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
        schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_id",
        "production_errors",
        ["tenant_id"],
        schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_order",
        "production_errors",
        ["tenant_id", "order_id"],
        schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_severity",
        "production_errors",
        ["tenant_id", "severity"],
        schema="plan",
    )
    op.create_index(
        "ix_production_errors_tenant_phase",
        "production_errors",
        ["tenant_id", "phase_name"],
        schema="plan",
    )


def downgrade() -> None:
    for ix in (
        "ix_production_errors_tenant_phase",
        "ix_production_errors_tenant_severity",
        "ix_production_errors_tenant_order",
        "ix_production_errors_tenant_id",
    ):
        op.drop_index(ix, table_name="production_errors", schema="plan")
    op.drop_table("production_errors", schema="plan")
