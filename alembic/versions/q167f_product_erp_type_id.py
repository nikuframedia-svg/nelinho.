"""Q.167.F — core.products.erp_product_type_id (espelha P_TP_ID).

O COGS precisa de saber o tipo de produto cru do ERP (``PRODUTO.P_TP_ID``)
para aplicar o factor de correcção de mão-de-obra (``VARIAVEIS.VAR_ID=2``) aos
componentes ``P_TP_ID=90`` — fórmula canónica do ERP
(``Ordemfabrico_Compara_Custo_com_Standard`` / ``PrecoCusto_OF_Inflacionado``).
O ``product_type`` ENUM já existia mas é uma classificação derivada; faltava o
id cru. Coluna aditiva/nullable (segura, sem backfill: o ETL preenche-a no
próximo sync de master-data).

Revision ID: q167f_product_erp_type_id
Revises: q167e_drop_offp_rework
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "q167f_product_erp_type_id"
down_revision = "q167e_drop_offp_rework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("erp_product_type_id", sa.Integer(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("products", "erp_product_type_id", schema="core")
