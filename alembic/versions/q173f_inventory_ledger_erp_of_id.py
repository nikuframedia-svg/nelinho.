"""Q.173.F — coluna erp_of_id em supply.inventory_ledger_entries.

Liga cada linha do ledger à Ordem de Fabrico do ERP (MOV_OF_ID). Necessário
para o consumo-por-barco nas Fases 4/5 da campanha Q.173.

Revision ID: q173f_inventory_ledger_erp_of_id
Revises: q173d_material_master_source_cols
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "q173f_inventory_ledger_erp_of_id"
down_revision = "q173d_material_master_source_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_ledger_entries",
        sa.Column("erp_of_id", sa.Integer(), nullable=True),
        schema="supply",
    )


def downgrade() -> None:
    op.drop_column("inventory_ledger_entries", "erp_of_id", schema="supply")
