"""Q.115.A.09 — tabela hr.worker_phase_assignment (atribuicao operador/fase OF).

Alta cardinalidade. BIGINT IDENTITY PK. Regista tanto atribuicoes planeadas
(assignment_type='planned') como as reais (assignment_type='actual').
Permite auditoria de desvios entre plano e execucao.

Revision ID: q115_a09_worker_phase_assignment
Revises: q115_a08_fases_of_history
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a09_worker_phase_assignment"
down_revision = "q115_a08_fases_of_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_phase_assignment",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("of_id", sa.String(80), nullable=False),
        sa.Column("phase_id", sa.String(80), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignment_type", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "assignment_type IN ('planned','actual')",
            name="ck_worker_phase_assignment_type",
        ),
        schema="hr",
    )
    op.create_index(
        "ix_hr_worker_phase_assignment_tenant_id",
        "worker_phase_assignment",
        ["tenant_id"],
        schema="hr",
    )
    op.create_index(
        "ix_hr_worker_phase_assignment_tenant_worker_assigned",
        "worker_phase_assignment",
        ["tenant_id", "worker_id", "assigned_at"],
        schema="hr",
    )
    op.create_index(
        "ix_hr_worker_phase_assignment_tenant_of",
        "worker_phase_assignment",
        ["tenant_id", "of_id"],
        schema="hr",
    )

    # RLS — padrao Q.62.B
    op.execute(
        "ALTER TABLE hr.worker_phase_assignment ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON hr.worker_phase_assignment"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON hr.worker_phase_assignment
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
        "DROP POLICY IF EXISTS tenant_isolation ON hr.worker_phase_assignment"
    )
    op.execute(
        "ALTER TABLE hr.worker_phase_assignment DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "ix_hr_worker_phase_assignment_tenant_of",
        table_name="worker_phase_assignment",
        schema="hr",
    )
    op.drop_index(
        "ix_hr_worker_phase_assignment_tenant_worker_assigned",
        table_name="worker_phase_assignment",
        schema="hr",
    )
    op.drop_index(
        "ix_hr_worker_phase_assignment_tenant_id",
        table_name="worker_phase_assignment",
        schema="hr",
    )
    op.drop_table("worker_phase_assignment", schema="hr")
