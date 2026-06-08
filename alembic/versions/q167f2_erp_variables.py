"""Q.167.F — tabela core.erp_variables (espelho de dbo.VARIAVEIS).

Espelha as variáveis de configuração do ERP. A relevante é ``VAR_ID = 2`` =
factor de correcção das mãos-de-obra ('1.065'), que o COGS aplica aos
componentes ``P_TP_ID = 90``. Espelhar o valor real (dados honestos) em vez
de gravar o literal 1.065.

Revision ID: q167f2_erp_variables
Revises: q167f_product_erp_type_id
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q167f2_erp_variables"
down_revision = "q167f_product_erp_type_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "erp_variables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("var_id", sa.Integer(), nullable=False),
        sa.Column("var_value", sa.String(255), nullable=True),
        sa.Column("var_description", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_erp_variables"),
        sa.UniqueConstraint("tenant_id", "var_id", name="uq_erp_variables_tenant_var"),
        schema="core",
    )
    op.create_index(
        "ix_erp_variables_var_id", "erp_variables", ["var_id"], schema="core"
    )

    # RLS — padrão Q.62.B
    op.execute("ALTER TABLE core.erp_variables ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.erp_variables")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON core.erp_variables
            USING (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.tenant_id', true)::uuid
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON core.erp_variables")
    op.execute("ALTER TABLE core.erp_variables DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_erp_variables_var_id", table_name="erp_variables", schema="core")
    op.drop_table("erp_variables", schema="core")
