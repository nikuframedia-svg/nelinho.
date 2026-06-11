"""Q.173.D — colunas de proveniência em supply_material_master.

Adiciona `min_stock_source` e `lead_time_source` para distinguir entre
valores impostos pelo ERP, editados manualmente, ou o default do sistema.
Impede que re-runs do ETL clobberem overrides manuais do operador.

Revision ID: q173d_material_master_source_cols
Revises: q171f_user_feedback_user_id
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "q173d_material_master_source_cols"
down_revision = "q171f_user_feedback_user_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supply_material_master",
        sa.Column(
            "min_stock_source",
            sa.String(16),
            nullable=False,
            server_default="default",
        ),
        schema="supply",
    )
    op.add_column(
        "supply_material_master",
        sa.Column(
            "lead_time_source",
            sa.String(16),
            nullable=False,
            server_default="default",
        ),
        schema="supply",
    )


def downgrade() -> None:
    op.drop_column("supply_material_master", "min_stock_source", schema="supply")
    op.drop_column("supply_material_master", "lead_time_source", schema="supply")
