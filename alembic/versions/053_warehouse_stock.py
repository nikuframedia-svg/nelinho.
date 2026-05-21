"""Q.52.K — per-warehouse stock mirror (supply.warehouse_stock)

Snapshot of the NELO ERP view `dbo.produto_stocks_por_armazem` — stock
on-hand split across the ~20 factory warehouses. One row per
(tenant, product_code, warehouse_id), upserted by the supply stock ETL.

Revision ID: 053_warehouse_stock
Revises: 052_user_password_hash
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "053_warehouse_stock"
down_revision = "052_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warehouse_stock",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("product_code", sa.String(50), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_name", sa.String(120), nullable=False),
        sa.Column("stock", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Index("ix_warehouse_stock_product_code", "product_code"),
        sa.UniqueConstraint(
            "tenant_id",
            "product_code",
            "warehouse_id",
            name="uq_warehouse_stock_tenant_product_warehouse",
        ),
        schema="supply",
    )


def downgrade() -> None:
    op.drop_table("warehouse_stock", schema="supply")
