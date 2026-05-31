"""Q.115.A.05 — tabela quality.runbook (runbooks de resolucao de erros).

Cada runbook descreve como resolver um tipo de erro de producao. Pode ser
aprendido automaticamente pelo ML world model (source='learned') ou escrito
manualmente (source='manual'). Requer aprovacao humana antes de ser usado
(approved_by NOT NULL quando confianca e alta).

Revision ID: q115_a05_runbook
Revises: q115_a04_phase_operator_affinity
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a05_runbook"
down_revision = "q115_a04_phase_operator_affinity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runbook",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=False),
        sa.Column("steps_md", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("approved_by", sa.String(80), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("audit_trace_id", sa.String(64), nullable=True),
        sa.CheckConstraint(
            "source IN ('learned','manual')",
            name="ck_runbook_source",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_runbook_confidence",
        ),
        schema="quality",
    )
    op.create_index(
        "ix_quality_runbook_tenant_id",
        "runbook",
        ["tenant_id"],
        schema="quality",
    )
    op.create_index(
        "ix_quality_runbook_error_code",
        "runbook",
        ["error_code"],
        schema="quality",
    )

    # RLS — padrao Q.62.B
    op.execute("ALTER TABLE quality.runbook ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON quality.runbook")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON quality.runbook
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON quality.runbook")
    op.execute("ALTER TABLE quality.runbook DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_quality_runbook_error_code", table_name="runbook", schema="quality")
    op.drop_index("ix_quality_runbook_tenant_id", table_name="runbook", schema="quality")
    op.drop_table("runbook", schema="quality")
