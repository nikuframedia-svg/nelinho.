"""Create copilot action logs table

Revision ID: 006_copilot_action_logs
Revises: 005_supply_tables
Create Date: 2026-01-18

Implements audit log for Copilot actions:
- copilot_action_logs: Tracks all executed actions with before/after state
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_copilot_action_logs'
down_revision = '005_supply_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Copilot Action Logs table
    op.create_table(
        'copilot_action_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('before_state', postgresql.JSONB(), nullable=False),
        sa.Column('after_state', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='executed'),  # executed, failed, rolled_back
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('rollback_until', sa.DateTime(timezone=True), nullable=True),  # 24h window for undo
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Indexes
    op.create_index('idx_copilot_action_logs_tenant', 'copilot_action_logs', ['tenant_id'])
    op.create_index('idx_copilot_action_logs_user', 'copilot_action_logs', ['user_id'])
    op.create_index('idx_copilot_action_logs_plan', 'copilot_action_logs', ['plan_id'])
    op.create_index('idx_copilot_action_logs_status', 'copilot_action_logs', ['status'])
    op.create_index('idx_copilot_action_logs_rollback', 'copilot_action_logs', ['rollback_until'], postgresql_where=sa.text("status = 'executed'"))


def downgrade() -> None:
    op.drop_index('idx_copilot_action_logs_rollback', table_name='copilot_action_logs')
    op.drop_index('idx_copilot_action_logs_status', table_name='copilot_action_logs')
    op.drop_index('idx_copilot_action_logs_plan', table_name='copilot_action_logs')
    op.drop_index('idx_copilot_action_logs_user', table_name='copilot_action_logs')
    op.drop_index('idx_copilot_action_logs_tenant', table_name='copilot_action_logs')
    op.drop_table('copilot_action_logs')










