"""Q.155.A — tabela governance.boat_complexity.

Índice de complexidade do barco (ICB) por produto: combinação ponderada de
nº de peças (BOM), tinta consumida por OF e nº de fases por OF. Alimenta o
matching "barco difícil ↔ melhores operadores" no CPO + a UI.

Revision ID: q155a_boat_complexity
Revises: q153c_plan_exclusion
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q155a_boat_complexity"
down_revision = "q153c_plan_exclusion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boat_complexity",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.String(80), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("complexity_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_components", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paint_kg_per_of", sa.Float(), nullable=False, server_default="0"),
        sa.Column("n_distinct_phases", sa.Float(), nullable=False, server_default="0"),
        sa.Column("n_ofs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "product_id",
            name="pk_boat_complexity",
        ),
        sa.CheckConstraint(
            "complexity_score BETWEEN 0 AND 1",
            name="ck_boat_complexity_score",
        ),
        schema="governance",
    )
    op.create_index(
        "ix_boat_complexity_tenant_id",
        "boat_complexity",
        ["tenant_id"],
        schema="governance",
    )

    # RLS — padrão Q.62.B
    op.execute("ALTER TABLE governance.boat_complexity ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON governance.boat_complexity")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON governance.boat_complexity
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON governance.boat_complexity")
    op.execute("ALTER TABLE governance.boat_complexity DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_boat_complexity_tenant_id", table_name="boat_complexity", schema="governance"
    )
    op.drop_table("boat_complexity", schema="governance")
