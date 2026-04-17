"""Create copilot_alerts table (Sprint C — Fase 5)

Revision ID: 010_copilot_alerts
Revises: 009_twin_scenarios
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_copilot_alerts'
down_revision = '009_twin_scenarios'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'copilot_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message_pt', sa.Text(), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('entity_refs', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', sa.String(255), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('idx_copilot_alerts_tenant_status', 'tenant_id', 'status', 'created_at'),
        sa.Index('idx_copilot_alerts_code', 'code'),
    )


def downgrade() -> None:
    op.drop_table('copilot_alerts')
