"""Create DQA tables

Revision ID: 004_dqa_tables
Revises: 003_event_outbox
Create Date: 2026-01-18

Implements Data Quality Autopilot tables:
- trust_index_snapshots: Historical TrustIndex snapshots
- data_quality_issues: Detected issues
- auto_repair_logs: Auto-repair actions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_dqa_tables'
down_revision = '003_event_outbox'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create DQA schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS dqa")
    
    # Trust Index Snapshots table
    op.create_table(
        'trust_index_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('trust_index', sa.Float(), nullable=False),
        sa.Column('components', postgresql.JSONB(), nullable=False),
        sa.Column('issues_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('repair_applied', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='dqa',
    )
    
    # Indexes
    op.create_index('idx_trust_index_entity', 'trust_index_snapshots', ['entity_id', 'entity_type'], schema='dqa')
    op.create_index('idx_trust_index_tenant_created', 'trust_index_snapshots', ['tenant_id', 'created_at'], schema='dqa')
    
    # Data Quality Issues table
    op.create_table(
        'data_quality_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('issue_type', sa.String(50), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('issue_description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='dqa',
    )
    
    # Indexes
    op.create_index('idx_dqa_issues_entity', 'data_quality_issues', ['entity_id'], schema='dqa')
    op.create_index('idx_dqa_issues_resolved', 'data_quality_issues', ['resolved'], schema='dqa')
    
    # Auto Repair Logs table
    op.create_table(
        'auto_repair_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('trust_index_before', sa.Float(), nullable=False),
        sa.Column('trust_index_after', sa.Float(), nullable=False),
        sa.Column('repair_actions', postgresql.JSONB(), nullable=False),
        sa.Column('repair_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='dqa',
    )
    
    # Indexes
    op.create_index('idx_repair_logs_entity', 'auto_repair_logs', ['entity_id'], schema='dqa')
    op.create_index('idx_repair_logs_created', 'auto_repair_logs', ['created_at'], schema='dqa')


def downgrade() -> None:
    op.drop_index('idx_repair_logs_created', table_name='auto_repair_logs', schema='dqa')
    op.drop_index('idx_repair_logs_entity', table_name='auto_repair_logs', schema='dqa')
    op.drop_table('auto_repair_logs', schema='dqa')
    
    op.drop_index('idx_dqa_issues_resolved', table_name='data_quality_issues', schema='dqa')
    op.drop_index('idx_dqa_issues_entity', table_name='data_quality_issues', schema='dqa')
    op.drop_table('data_quality_issues', schema='dqa')
    
    op.drop_index('idx_trust_index_tenant_created', table_name='trust_index_snapshots', schema='dqa')
    op.drop_index('idx_trust_index_entity', table_name='trust_index_snapshots', schema='dqa')
    op.drop_table('trust_index_snapshots', schema='dqa')
    
    # Drop schema (optional - may fail if other objects exist)
    op.execute("DROP SCHEMA IF EXISTS dqa CASCADE")










