"""Q.115.A.08 — tabela plan.fases_of_history (historico de fases de OF).

Alta cardinalidade (milions de linhas do ERP historico). BIGINT IDENTITY PK
para performance em inserts sequenciais. duration_min e coluna normal nullable
(calculada pela app ou ETL) em vez de GENERATED ALWAYS AS porque fase_fim
e nullable — Postgres rejeita generated columns que referenciam colunas
nullable com operacoes que podem produzir NULL.

Revision ID: q115_a08_fases_of_history
Revises: q115_a07_rework_entry_boat_id
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_a08_fases_of_history"
down_revision = "q115_a07_rework_entry_boat_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fases_of_history",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("of_id", sa.String(80), nullable=False),
        sa.Column("phase_id", sa.String(80), nullable=False),
        sa.Column("fase_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fase_fim", sa.DateTime(timezone=True), nullable=True),
        # duration_min calculada pela app (EXTRACT(EPOCH FROM (fase_fim - fase_inicio))/60)
        # nao usamos GENERATED ALWAYS AS porque fase_fim e nullable.
        sa.Column("duration_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mold_id", sa.String(80), nullable=True),
        sa.Column("source_run_id", sa.String(80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="plan",
    )
    op.create_index(
        "ix_plan_fases_of_history_tenant_id",
        "fases_of_history",
        ["tenant_id"],
        schema="plan",
    )
    op.create_index(
        "ix_plan_fases_of_history_of_id",
        "fases_of_history",
        ["of_id"],
        schema="plan",
    )
    # indice composto para queries tipicas (tenant + of + tempo)
    op.create_index(
        "ix_plan_fases_of_history_tenant_of_inicio",
        "fases_of_history",
        ["tenant_id", "of_id", "fase_inicio"],
        schema="plan",
    )

    # RLS — padrao Q.62.B
    op.execute("ALTER TABLE plan.fases_of_history ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.fases_of_history")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON plan.fases_of_history
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON plan.fases_of_history")
    op.execute("ALTER TABLE plan.fases_of_history DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_plan_fases_of_history_tenant_of_inicio",
        table_name="fases_of_history",
        schema="plan",
    )
    op.drop_index(
        "ix_plan_fases_of_history_of_id",
        table_name="fases_of_history",
        schema="plan",
    )
    op.drop_index(
        "ix_plan_fases_of_history_tenant_id",
        table_name="fases_of_history",
        schema="plan",
    )
    op.drop_table("fases_of_history", schema="plan")
