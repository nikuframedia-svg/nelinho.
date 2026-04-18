"""Sprint P.2 — transport_batch + transport_batch_assignment

Revision ID: 015_transport_batch
Revises: 014_supply_master
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '015_transport_batch'
down_revision = '014_supply_master'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'transport_batch',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('transport_date', sa.Date(), nullable=False),
        sa.Column('truck_capacity_units', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('destination', sa.String(255), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='OPEN'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_transport_batch_date', 'transport_date'),
        sa.Index('ix_transport_batch_tenant_date_status', 'tenant_id', 'transport_date', 'status'),
        schema='plan',
    )

    op.create_table(
        'transport_batch_assignment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.transport_batch.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'order_id', name='uq_transport_batch_assignment_order'),
        schema='plan',
    )


def downgrade() -> None:
    op.drop_table('transport_batch_assignment', schema='plan')
    op.drop_table('transport_batch', schema='plan')
