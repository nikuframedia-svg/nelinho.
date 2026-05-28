"""Q.115.A.02 — tabela core.daily_revenue_target (meta de receita diaria).

Append-only por data (UNIQUE tenant_id, effective_from). A meta mais recente
para cada data vence. Permite historiar mudancas de objetivo sem perder registo.

Revision ID: q115_a02_daily_revenue_target
Revises: q115_a01_user_input
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a02_daily_revenue_target"
down_revision = "q115_a01_user_input"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_revenue_target",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "target_eur",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("audit_trace_id", sa.String(64), nullable=True),
        sa.CheckConstraint("target_eur > 0", name="ck_daily_revenue_target_positive"),
        sa.UniqueConstraint(
            "tenant_id", "effective_from",
            name="uq_daily_revenue_target_tenant_date",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_daily_revenue_target_tenant_id",
        "daily_revenue_target",
        ["tenant_id"],
        schema="core",
    )

    # RLS — padrao Q.62.B
    op.execute("ALTER TABLE core.daily_revenue_target ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.daily_revenue_target")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON core.daily_revenue_target
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.daily_revenue_target")
    op.execute("ALTER TABLE core.daily_revenue_target DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_core_daily_revenue_target_tenant_id",
        table_name="daily_revenue_target",
        schema="core",
    )
    op.drop_table("daily_revenue_target", schema="core")
