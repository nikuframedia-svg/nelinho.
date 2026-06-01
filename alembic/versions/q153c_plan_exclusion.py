"""Q.153.C1 — plan.plan_exclusion (excluir/adiar barco do plano, reversível).

A presença de uma linha (tenant_id, order_id) significa "barco excluído do
plano automático"; o DELETE repõe-o. O barco continua no ERP — não tocamos
em factory_raw. PK composta; order_id é o OF_ID da NELO (varchar 80).

Revision ID: q153c_plan_exclusion
Revises: 1b7fc2e9a341
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q153c_plan_exclusion"
down_revision = "1b7fc2e9a341"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_exclusion",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("excluded_by", sa.String(80), nullable=False),
        sa.Column(
            "excluded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("tenant_id", "order_id"),
        schema="plan",
    )
    op.create_index(
        "ix_plan_exclusion_tenant",
        "plan_exclusion",
        ["tenant_id"],
        schema="plan",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plan_exclusion_tenant",
        table_name="plan_exclusion",
        schema="plan",
    )
    op.drop_table("plan_exclusion", schema="plan")
