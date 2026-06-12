"""Q.174.F4 — plan.worker_absence (override local de ausências).

Fonte primária = factory_raw.ent_mov (MET_MET_ID=2, lida direto pelo CPO);
esta tabela cobre ausências ad-hoc ('add') e anulações de ausências ERP
erradas ('ignore_erp', via erp_movent_id). employee_code = E_ID::text.

Revision ID: q174a_worker_absence
Revises: q173f_inventory_ledger_erp_of_id
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q174a_worker_absence"
down_revision = "q173f_inventory_ledger_erp_of_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_absence",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(40), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=True),
        sa.Column("mode", sa.String(10), nullable=False, server_default="add"),
        sa.Column("erp_movent_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="plan",
    )
    op.create_index(
        "ix_worker_absence_tenant_emp",
        "worker_absence",
        ["tenant_id", "employee_code"],
        schema="plan",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_worker_absence_tenant_emp",
        table_name="worker_absence",
        schema="plan",
    )
    op.drop_table("worker_absence", schema="plan")
