"""Sprint O.1 — supply material master, in-transit, reconciliation

Revision ID: 014_supply_master
Revises: 013_tenant_configuration
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '014_supply_master'
down_revision = '013_tenant_configuration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'supply_material_master',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('sku_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('unit_of_measure', sa.String(20), nullable=False, server_default='UN'),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('default_supplier_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('lead_time_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('min_stock_qty', sa.Numeric(18, 6), nullable=False, server_default='0'),
        sa.Column('reorder_qty', sa.Numeric(18, 6), nullable=False, server_default='0'),
        sa.Column('safety_stock_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_flag', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_supply_material_master_sku', 'sku_id'),
        sa.Index('ix_supply_material_master_tenant_sku', 'tenant_id', 'sku_id', unique=True),
        schema='supply',
    )

    op.create_table(
        'supply_material_in_transit',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('sku_id', sa.String(50), nullable=False),
        sa.Column('purchase_order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('qty', sa.Numeric(18, 6), nullable=False),
        sa.Column('eta', sa.Date(), nullable=False),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_supply_material_in_transit_sku', 'sku_id'),
        sa.Index('ix_supply_material_in_transit_eta', 'eta'),
        sa.Index('ix_supply_material_in_transit_tenant_sku_status', 'tenant_id', 'sku_id', 'status'),
        schema='supply',
    )

    op.create_table(
        'supply_stock_reconciliation',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('sku_id', sa.String(50), nullable=False),
        sa.Column('theoretical_qty', sa.Numeric(18, 6), nullable=False),
        sa.Column('physical_qty', sa.Numeric(18, 6), nullable=False),
        sa.Column('variance_qty', sa.Numeric(18, 6), nullable=False),
        sa.Column('variance_pct', sa.Float(), nullable=True),
        sa.Column('counted_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('counted_by', sa.String(100), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('resolved_ledger_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_supply_stock_reconciliation_sku', 'sku_id'),
        sa.Index('ix_supply_stock_reconciliation_tenant_date', 'tenant_id', 'counted_at'),
        schema='supply',
    )


def downgrade() -> None:
    op.drop_table('supply_stock_reconciliation', schema='supply')
    op.drop_table('supply_material_in_transit', schema='supply')
    op.drop_table('supply_material_master', schema='supply')
