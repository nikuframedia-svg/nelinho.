"""Sprint P.4 — routing_template + routing_template_phase + model_routing_assignment

Revision ID: 016_routing_templates
Revises: 015_transport_batch
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '016_routing_templates'
down_revision = '015_transport_batch'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'routing_template',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('phase_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('model_coverage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_routing_template_code'),
        schema='plan',
    )

    op.create_table(
        'routing_template_phase',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.routing_template.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('phase_id', sa.String(100), nullable=False),
        sa.Column('phase_name', sa.String(255), nullable=True),
        sa.Column('duration_p50_h', sa.Numeric(10, 4), nullable=True),
        sa.Column('duration_p90_h', sa.Numeric(10, 4), nullable=True),
        sa.Column('requires_mold', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('team_size_default', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('can_skip', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('alternative_group_id', sa.String(32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_routing_template_phase_template_seq', 'template_id', 'seq'),
        schema='plan',
    )

    op.create_table(
        'model_routing_assignment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('model_id', sa.String(100), nullable=False, index=True),
        sa.Column('primary_template_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.routing_template.id'), nullable=False),
        sa.Column('alt_template_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.routing_template.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'model_id', name='uq_model_routing_assignment_model'),
        schema='plan',
    )


def downgrade() -> None:
    op.drop_table('model_routing_assignment', schema='plan')
    op.drop_table('routing_template_phase', schema='plan')
    op.drop_table('routing_template', schema='plan')
