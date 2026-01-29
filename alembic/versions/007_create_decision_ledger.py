"""Create decision ledger tables

Revision ID: 007_decision_ledger
Revises: 006_copilot_action_logs
Create Date: 2026-01-19

Implements decision management and approval workflow:
- decision_runs: Tracks decisions through lifecycle (PROPOSED → APPROVED → EXECUTED → ROLLED_BACK)
- decision_approvals: Individual approver records with SoD enforcement
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_decision_ledger'
down_revision = '006_copilot_action_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Decision Runs table
    op.create_table(
        'decision_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),  # "INCREASE_SS", "ADJUST_PRICE", etc.
        sa.Column('target', sa.String(255), nullable=False),  # SKU ID, product ID, etc.
        sa.Column('status', sa.String(20), nullable=False, server_default='PROPOSED'),
        sa.Column('sandbox_result', postgresql.JSONB(), nullable=True),
        sa.Column('before_state', postgresql.JSONB(), nullable=False),
        sa.Column('after_state', postgresql.JSONB(), nullable=True),
        sa.Column('proposed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('proposed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rolled_back_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='shared'
    )
    
    # Decision Approvals table
    op.create_table(
        'decision_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('approver_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['decision_id'], ['shared.decision_runs.id'], ondelete='CASCADE'),
        schema='shared'
    )
    
    # Indexes for decision_runs
    op.create_index(
        'idx_decision_runs_status_created',
        'decision_runs',
        ['status', 'created_at'],
        schema='shared'
    )
    op.create_index(
        'idx_decision_runs_tenant_status',
        'decision_runs',
        ['tenant_id', 'status'],
        schema='shared'
    )
    op.create_index(
        'idx_decision_runs_proposed_by',
        'decision_runs',
        ['proposed_by'],
        schema='shared'
    )
    
    # Indexes for decision_approvals
    op.create_index(
        'idx_decision_approvals_decision',
        'decision_approvals',
        ['decision_id'],
        schema='shared'
    )
    op.create_index(
        'idx_decision_approvals_approver',
        'decision_approvals',
        ['approver_id'],
        schema='shared'
    )
    op.create_index(
        'idx_decision_approvals_status',
        'decision_approvals',
        ['status'],
        schema='shared'
    )


def downgrade() -> None:
    op.drop_index('idx_decision_approvals_status', table_name='decision_approvals', schema='shared')
    op.drop_index('idx_decision_approvals_approver', table_name='decision_approvals', schema='shared')
    op.drop_index('idx_decision_approvals_decision', table_name='decision_approvals', schema='shared')
    op.drop_index('idx_decision_runs_proposed_by', table_name='decision_runs', schema='shared')
    op.drop_index('idx_decision_runs_tenant_status', table_name='decision_runs', schema='shared')
    op.drop_index('idx_decision_runs_status_created', table_name='decision_runs', schema='shared')
    op.drop_table('decision_approvals', schema='shared')
    op.drop_table('decision_runs', schema='shared')










