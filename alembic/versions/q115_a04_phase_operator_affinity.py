"""Q.115.A.04 — tabela governance.phase_operator_affinity (afinidade operador/fase).

Score calculado pelo ML world model: quanto bem um operador especifico executa
uma fase especifica, baseado em historico de duracoes. PK composta
(tenant_id, operator_id, phase_id) — um score por par operador+fase por tenant.

phase_id e String(80) para ser compativel com routing_template_phase.phase_id
que e uma string (ex: "INJECAO", "DESMOLDAGEM", etc.).

Revision ID: q115_a04_phase_operator_affinity
Revises: q115_a03_client_priority
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a04_phase_operator_affinity"
down_revision = "q115_a03_client_priority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS governance")

    op.create_table(
        "phase_operator_affinity",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_id", sa.String(80), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column(
            "last_computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 1",
            name="ck_phase_operator_affinity_score",
        ),
        sa.CheckConstraint(
            "sample_count >= 0",
            name="ck_phase_operator_affinity_sample_count",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "operator_id", "phase_id",
            name="pk_phase_operator_affinity",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_governance_phase_operator_affinity_tenant_id",
        "phase_operator_affinity",
        ["tenant_id"],
        schema="governance",
    )

    # RLS — padrao Q.62.B
    op.execute(
        "ALTER TABLE governance.phase_operator_affinity ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON governance.phase_operator_affinity"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation ON governance.phase_operator_affinity
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
        "DROP POLICY IF EXISTS tenant_isolation ON governance.phase_operator_affinity"
    )
    op.execute(
        "ALTER TABLE governance.phase_operator_affinity DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "ix_governance_phase_operator_affinity_tenant_id",
        table_name="phase_operator_affinity",
        schema="governance",
    )
    op.drop_table("phase_operator_affinity", schema="governance")
