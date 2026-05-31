"""Q.115.X6.B — tabela governance.boat_potential.

Score de potencialidade por barco: combinação ponderada de margem média,
throughput médio, taxa de defeitos baixa e lead-time curto.
Barcos com score alto são candidatos prioritários para planning.

Revision ID: q115_x6b_boat_potential
Revises: q115_x6a_boat_phase_score
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q115_x6b_boat_potential"
down_revision = "q115_x6a_boat_phase_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boat_potential",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boat_id", sa.String(80), nullable=False),
        sa.Column("potential_score", sa.Float(), nullable=False),
        sa.Column(
            "revenue_eur_lifetime",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "boat_id",
            name="pk_boat_potential",
        ),
        sa.CheckConstraint(
            "potential_score BETWEEN 0 AND 1",
            name="ck_boat_potential_score",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_boat_potential_tenant_id",
        "boat_potential",
        ["tenant_id"],
        schema="governance",
    )

    # RLS — padrão Q.62.B
    op.execute("ALTER TABLE governance.boat_potential ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON governance.boat_potential")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON governance.boat_potential
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON governance.boat_potential")
    op.execute("ALTER TABLE governance.boat_potential DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_boat_potential_tenant_id", table_name="boat_potential", schema="governance")
    op.drop_table("boat_potential", schema="governance")
