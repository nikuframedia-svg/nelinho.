"""Q.53.D — purchase-order tracking (supply.purchase_orders)

Tracks supplier deliveries: what was ordered, from whom, the ETA and the
reception state. Mirrored from the NELO ERP `MOVIMENTO` table (movement
type 9 = "Pedidos a fornecedor") by the supply `purchase_orders` ETL, or
created inside ProdPlan with `erp_movement_id` NULL.

Revision ID: 054_purchase_orders
Revises: 053_warehouse_stock
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "054_purchase_orders"
down_revision = "053_warehouse_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("erp_movement_id", sa.Integer(), nullable=True),
        sa.Column("po_number", sa.String(50), nullable=True),
        sa.Column("supplier_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("supplier_erp_id", sa.Integer(), nullable=True),
        sa.Column("product_code", sa.String(50), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=True),
        sa.Column("qty_ordered", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("qty_received", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("unit_of_measure", sa.String(20), nullable=False, server_default="UN"),
        sa.Column("ordered_at", sa.Date(), nullable=True),
        sa.Column("eta", sa.Date(), nullable=True),
        sa.Column("received_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("source", sa.String(40), nullable=False, server_default="prodplan"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Index("ix_purchase_orders_product_code", "product_code"),
        sa.Index("ix_purchase_orders_po_number", "po_number"),
        sa.Index("ix_purchase_orders_eta", "eta"),
        sa.Index("ix_purchase_orders_status", "status"),
        sa.UniqueConstraint(
            "tenant_id",
            "erp_movement_id",
            name="uq_purchase_orders_tenant_erp_movement",
        ),
        schema="supply",
    )


def downgrade() -> None:
    op.drop_table("purchase_orders", schema="supply")
