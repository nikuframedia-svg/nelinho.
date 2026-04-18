"""Sprint Q.0/Q.2 — product_pricing + order_revenue + shipping_rate

Revision ID: 017_product_pricing
Revises: 016_routing_templates
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '017_product_pricing'
down_revision = '016_routing_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS profit")

    op.create_table(
        'product_pricing',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.products.id'), nullable=False),
        sa.Column('sale_value_default_eur', sa.Numeric(18, 4), nullable=False),
        sa.Column('currency_code', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'product_id', 'valid_from',
                            name='uq_product_pricing_validity'),
        sa.Index('ix_product_pricing_product', 'product_id'),
        sa.Index('ix_product_pricing_tenant_product_valid',
                 'tenant_id', 'product_id', 'valid_from'),
        schema='profit',
    )

    op.create_table(
        'order_revenue',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('order_id', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 6), nullable=False, server_default='1'),
        sa.Column('unit_price_eur', sa.Numeric(18, 4), nullable=False),
        sa.Column('total_revenue_eur', sa.Numeric(18, 4), nullable=False),
        sa.Column('currency_code', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('recognised_at', sa.Date(), nullable=True),
        sa.Column('source', sa.String(32), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'order_id', name='uq_order_revenue_order'),
        sa.Index('ix_order_revenue_tenant_order', 'tenant_id', 'order_id'),
        schema='profit',
    )

    op.create_table(
        'shipping_rate',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('destination', sa.String(100), nullable=False, server_default='ANY'),
        sa.Column('sku_category', sa.String(64), nullable=False, server_default='ANY'),
        sa.Column('flat_cost_eur', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('cost_formula_expr', sa.Text(), nullable=True),
        sa.Column('currency_code', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'destination', 'sku_category',
                            name='uq_shipping_rate_dest_category'),
        sa.Index('ix_shipping_rate_dest', 'destination'),
        schema='profit',
    )


def downgrade() -> None:
    op.drop_table('shipping_rate', schema='profit')
    op.drop_table('order_revenue', schema='profit')
    op.drop_table('product_pricing', schema='profit')
