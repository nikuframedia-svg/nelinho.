"""Q.155.B — tabela governance.phase_preferred_operator.

Lista curada (manual) dos melhores operadores por fase. Alimenta o matching
"barco difícil ↔ melhores operadores" no CPO. employee_code = E_ID do ERP.

Revision ID: q155b_phase_preferred_operator
Revises: q155a_boat_complexity
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q155b_phase_preferred_operator"
down_revision = "q155a_boat_complexity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phase_preferred_operator",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_id", sa.String(80), nullable=False),
        sa.Column("employee_code", sa.String(80), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("set_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "set_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "phase_id", "employee_code",
            name="pk_phase_preferred_operator",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_phase_preferred_operator_tenant_phase",
        "phase_preferred_operator",
        ["tenant_id", "phase_id"],
        schema="governance",
    )

    # RLS — padrão Q.62.B
    op.execute(
        "ALTER TABLE governance.phase_preferred_operator ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON governance.phase_preferred_operator"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON governance.phase_preferred_operator
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON governance.phase_preferred_operator"
    )
    op.execute(
        "ALTER TABLE governance.phase_preferred_operator DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "ix_phase_preferred_operator_tenant_phase",
        table_name="phase_preferred_operator",
        schema="governance",
    )
    op.drop_table("phase_preferred_operator", schema="governance")
