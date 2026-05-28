"""Q.115.X6.A — tabela governance.boat_phase_score.

Afinidade barco/fase: throughput histórico e taxa de defeitos por modelo.
Complementa phase_operator_affinity (Q.115.A.04) — mesma lógica mas para
o barco (boat_id = código do produto/modelo de barco), não o operador.

Revision ID: q115_x6a_boat_phase_score
Revises: q115_a10_ml_drift_event
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_x6a_boat_phase_score"
down_revision = "q115_a10_ml_drift_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boat_phase_score",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boat_id", sa.String(80), nullable=False),
        sa.Column("phase_id", sa.String(80), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column(
            "last_computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "boat_id", "phase_id",
            name="pk_boat_phase_score",
        ),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name="ck_boat_phase_score_score"),
        sa.CheckConstraint("sample_count >= 0", name="ck_boat_phase_score_sample_count"),
        schema="governance",
    )
    op.create_index(
        "ix_boat_phase_score_tenant_id",
        "boat_phase_score",
        ["tenant_id"],
        schema="governance",
    )
    op.create_index(
        "ix_boat_phase_score_boat_id",
        "boat_phase_score",
        ["boat_id"],
        schema="governance",
    )

    # RLS — padrão Q.62.B
    op.execute("ALTER TABLE governance.boat_phase_score ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON governance.boat_phase_score")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON governance.boat_phase_score
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON governance.boat_phase_score")
    op.execute("ALTER TABLE governance.boat_phase_score DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_boat_phase_score_boat_id", table_name="boat_phase_score", schema="governance")
    op.drop_index("ix_boat_phase_score_tenant_id", table_name="boat_phase_score", schema="governance")
    op.drop_table("boat_phase_score", schema="governance")
