"""Q.157.E — tabela plan.operation_execution (overlay de picagem).

Overlay de execução real das operações do plano LIVE (COMECEI/ACABEI no tablet
do operador). Desacoplado do ``plan_schedule_commits`` imutável: a fila junta o
plano com este overlay por ``operation_id``.

Revision ID: q157e_operation_execution
Revises: q155c_plan_exclusion_rls
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q157e_operation_execution"
down_revision = "q155c_plan_exclusion_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_execution",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", sa.String(120), nullable=False),
        sa.Column("order_id", sa.String(50), nullable=False, server_default=""),
        sa.Column("worker_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("commit_sha256", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="SCHEDULED"),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operation_execution"),
        sa.UniqueConstraint(
            "tenant_id", "operation_id", name="uq_operation_execution_op",
        ),
        schema="plan",
    )
    op.create_index(
        "ix_operation_execution_operation_id",
        "operation_execution",
        ["operation_id"],
        schema="plan",
    )
    op.create_index(
        "ix_operation_execution_tenant_id",
        "operation_execution",
        ["tenant_id"],
        schema="plan",
    )

    # RLS — padrão Q.62.B
    op.execute("ALTER TABLE plan.operation_execution ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.operation_execution")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON plan.operation_execution
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.operation_execution")
    op.execute("ALTER TABLE plan.operation_execution DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_operation_execution_tenant_id",
        table_name="operation_execution", schema="plan",
    )
    op.drop_index(
        "ix_operation_execution_operation_id",
        table_name="operation_execution", schema="plan",
    )
    op.drop_table("operation_execution", schema="plan")
