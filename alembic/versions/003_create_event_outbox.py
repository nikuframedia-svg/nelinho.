"""Create event outbox tables

Revision ID: 003_event_outbox
Revises: 002_add_copilot_conversations
Create Date: 2026-01-18

Implements Outbox Pattern for exactly-once event delivery:
- event_outbox: Stores events before publishing to Kafka
- event_dlq: Dead Letter Queue for failed events
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_event_outbox'
down_revision = '002_add_conversations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Event Outbox table
    op.create_table(
        'event_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregate_type', sa.String(50), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        # UNIQUE constraint for idempotency (prevents duplicate events)
        sa.UniqueConstraint('tenant_id', 'aggregate_id', 'event_type', name='uq_event_outbox_idempotency'),
    )
    
    # Index for fetching pending events efficiently
    op.create_index(
        'idx_event_outbox_pending',
        'event_outbox',
        ['status', 'created_at'],
        postgresql_where=sa.text("status = 'pending'"),
    )
    
    # Index for tenant queries
    op.create_index('idx_event_outbox_tenant', 'event_outbox', ['tenant_id'])
    
    # Event Dead Letter Queue table
    op.create_table(
        'event_dlq',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_outbox_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('retry_attempt', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['event_outbox_id'], ['event_outbox.id'], name='fk_event_dlq_outbox'),
    )
    
    # Index for DLQ queries
    op.create_index('idx_event_dlq_created', 'event_dlq', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_event_dlq_created', table_name='event_dlq')
    op.drop_table('event_dlq')
    op.drop_index('idx_event_outbox_tenant', table_name='event_outbox')
    op.drop_index('idx_event_outbox_pending', table_name='event_outbox')
    op.drop_table('event_outbox')



