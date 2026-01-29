"""Create supply chain tables

Revision ID: 005_supply_tables
Revises: 004_dqa_tables
Create Date: 2026-01-18

Implements Supply Chain Planning module:
- inventory_ledger_entries: Inventory ledger (event sourcing pattern)
- supply_forecasts: Forecast history
- supply_rop_configs: ROP configuration per SKU
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_supply_tables'
down_revision = '004_dqa_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create Supply schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS supply")
    
    # Inventory Ledger Entries table
    op.create_table(
        'inventory_ledger_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sku_id', sa.String(50), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('qty_opening', sa.Numeric(18, 6), nullable=False, server_default='0'),
        sa.Column('qty_in', sa.Numeric(18, 6), nullable=False, server_default='0'),  # Receipts
        sa.Column('qty_out', sa.Numeric(18, 6), nullable=False, server_default='0'),  # Consumptions
        sa.Column('qty_closing', sa.Numeric(18, 6), nullable=False, server_default='0'),  # On-hand after movement
        sa.Column('transaction_type', sa.String(20), nullable=False),  # 'consume', 'receive', 'adjust'
        sa.Column('reference_id', postgresql.UUID(as_uuid=True), nullable=True),  # operation_id or po_id
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='supply',
    )
    
    # Indexes for inventory ledger
    op.create_index(
        'idx_inventory_ledger_sku_date',
        'inventory_ledger_entries',
        ['sku_id', 'date'],
        unique=False,
        schema='supply',
    )
    op.create_index('idx_inventory_ledger_tenant', 'inventory_ledger_entries', ['tenant_id'], schema='supply')
    op.create_index('idx_inventory_ledger_sku', 'inventory_ledger_entries', ['sku_id'], schema='supply')
    
    # Supply Forecasts table
    op.create_table(
        'supply_forecasts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sku_id', sa.String(50), nullable=False),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('qty_p50', sa.Numeric(18, 6), nullable=False),  # Median forecast
        sa.Column('qty_p90', sa.Numeric(18, 6), nullable=False),  # Upper interval
        sa.Column('wmape', sa.Float(), nullable=True),  # Weighted MAPE
        sa.Column('quality', sa.String(10), nullable=False),  # 'good', 'fair', 'poor'
        sa.Column('periods_ahead', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='supply',
    )
    
    # Indexes for forecasts
    op.create_index('idx_forecast_sku_date', 'supply_forecasts', ['sku_id', 'forecast_date'], schema='supply')
    op.create_index('idx_forecast_tenant', 'supply_forecasts', ['tenant_id'], schema='supply')
    
    # ROP Configs table
    op.create_table(
        'supply_rop_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sku_id', sa.String(50), nullable=False),
        sa.Column('avg_daily_demand', sa.Numeric(18, 6), nullable=False),
        sa.Column('lead_time_days', sa.Integer(), nullable=False),
        sa.Column('lead_time_std_dev', sa.Float(), nullable=False),
        sa.Column('service_level', sa.Float(), nullable=False, server_default='0.95'),  # 95% fill rate
        sa.Column('rop', sa.Numeric(18, 6), nullable=False),
        sa.Column('base_rop', sa.Numeric(18, 6), nullable=False),
        sa.Column('safety_stock', sa.Numeric(18, 6), nullable=False),
        sa.Column('z_score', sa.Float(), nullable=False),
        sa.Column('last_calculated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='supply',
    )
    
    # Indexes for ROP configs
    op.create_index('idx_rop_config_sku', 'supply_rop_configs', ['sku_id'], unique=True, schema='supply')
    op.create_index('idx_rop_config_tenant', 'supply_rop_configs', ['tenant_id'], schema='supply')


def downgrade() -> None:
    op.drop_index('idx_rop_config_tenant', table_name='supply_rop_configs', schema='supply')
    op.drop_index('idx_rop_config_sku', table_name='supply_rop_configs', schema='supply')
    op.drop_table('supply_rop_configs', schema='supply')
    
    op.drop_index('idx_forecast_tenant', table_name='supply_forecasts', schema='supply')
    op.drop_index('idx_forecast_sku_date', table_name='supply_forecasts', schema='supply')
    op.drop_table('supply_forecasts', schema='supply')
    
    op.drop_index('idx_inventory_ledger_sku', table_name='inventory_ledger_entries', schema='supply')
    op.drop_index('idx_inventory_ledger_tenant', table_name='inventory_ledger_entries', schema='supply')
    op.drop_index('idx_inventory_ledger_sku_date', table_name='inventory_ledger_entries', schema='supply')
    op.drop_table('inventory_ledger_entries', schema='supply')
    
    # Drop schema (optional - may fail if other objects exist)
    op.execute("DROP SCHEMA IF EXISTS supply CASCADE")










