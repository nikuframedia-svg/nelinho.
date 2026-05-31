"""Q.115.A.03 — tabela core.client_priority (prioridade de cliente).

Um registo por cliente com score 1-5 (1=baixo, 5=maximo). FK soft para
core.customers — sem CASCADE para nao bloquear gestao de clientes.

Revision ID: q115_a03_client_priority
Revises: q115_a02_daily_revenue_target
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a03_client_priority"
down_revision = "q115_a02_daily_revenue_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_priority",
        # FK soft — client_id referencia core.customers.id mas sem
        # FK constraint para nao bloquear gestao de clientes ERP.
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.String(80), nullable=False),
        sa.CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="ck_client_priority_range",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_client_priority_tenant_id",
        "client_priority",
        ["tenant_id"],
        schema="core",
    )

    # RLS — padrao Q.62.B
    op.execute("ALTER TABLE core.client_priority ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.client_priority")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON core.client_priority
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.client_priority")
    op.execute("ALTER TABLE core.client_priority DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_core_client_priority_tenant_id",
        table_name="client_priority",
        schema="core",
    )
    op.drop_table("client_priority", schema="core")
