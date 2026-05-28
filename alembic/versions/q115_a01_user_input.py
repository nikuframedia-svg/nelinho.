"""Q.115.A.01 — tabela core.user_input (pedidos de evolucao do utilizador).

Cada vez que o utilizador quer pedir uma evolucao ao sistema (nova feature,
correcao, melhoria), regista aqui com rastreabilidade completa: o que pede,
onde na UI pediu, porquê economicamente, e que claude_run_id processou.

Revision ID: q115_a01_user_input
Revises: 060_q66_e_agent_actions
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a01_user_input"
down_revision = "060_q66_e_agent_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_input",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("author", sa.String(80), nullable=False),
        sa.Column("what", sa.Text(), nullable=False),
        sa.Column("where_page", sa.String(20), nullable=False),
        sa.Column("economic_reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("result_pr_url", sa.String(500), nullable=True),
        sa.Column("claude_run_id", sa.String(80), nullable=True),
        sa.Column("audit_trace_id", sa.String(64), nullable=True),
        sa.CheckConstraint("char_length(what) >= 10", name="ck_user_input_what_min"),
        sa.CheckConstraint(
            "char_length(economic_reason) >= 30",
            name="ck_user_input_economic_reason_min",
        ),
        sa.CheckConstraint(
            "where_page IN ('decisoes','overall','llm','configuracoes')",
            name="ck_user_input_where_page",
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','done','rejected')",
            name="ck_user_input_status",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_user_input_tenant_id",
        "user_input",
        ["tenant_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_user_input_audit_trace_id",
        "user_input",
        ["audit_trace_id"],
        schema="core",
    )

    # RLS — padrao Q.62.B
    op.execute("ALTER TABLE core.user_input ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.user_input")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON core.user_input
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.user_input")
    op.execute("ALTER TABLE core.user_input DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_core_user_input_audit_trace_id", table_name="user_input", schema="core")
    op.drop_index("ix_core_user_input_tenant_id", table_name="user_input", schema="core")
    op.drop_table("user_input", schema="core")
