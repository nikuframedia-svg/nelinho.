"""Sprint R.6 — mold + mold_health + mold_maintenance_event + mold_defect_log + mold_usage_counter

Revision ID: 020_mold_maintenance
Revises: 019_schedule_quality
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '020_mold_maintenance'
down_revision = '019_schedule_quality'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mold',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('mold_code', sa.String(100), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('pocket_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('mold_type', sa.String(64), nullable=True),
        sa.Column('acquired_date', sa.Date(), nullable=True),
        sa.Column('purchase_cost_eur', sa.Numeric(18, 4), nullable=True),
        sa.Column('expected_life_cycles', sa.Integer(), nullable=True),
        sa.Column('replacement_date', sa.Date(), nullable=True),
        sa.Column('depreciated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'mold_code', name='uq_mold_code'),
        sa.Index('ix_mold_model', 'model_id'),
        schema='plan',
    )

    op.create_table(
        'mold_health',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('mold_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.mold.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score_0_100', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('risk_category', sa.String(16), nullable=False, server_default='green'),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assessed_by', sa.String(100), nullable=True),
        sa.Column('next_assessment_due', sa.Date(), nullable=True),
        sa.Column('components', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_mold_health_mold', 'mold_id'),
        sa.Index('ix_mold_health_tenant_score', 'tenant_id', 'score_0_100'),
        schema='plan',
    )

    op.create_table(
        'mold_maintenance_event',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('mold_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.mold.id', ondelete='CASCADE'), nullable=False),
        sa.Column('maintenance_type', sa.String(32), nullable=False, server_default='preventive'),
        sa.Column('planned_date', sa.Date(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_duration_h', sa.Numeric(10, 2), nullable=True),
        sa.Column('technician_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=True),
        sa.Column('parts_cost_eur', sa.Numeric(18, 4), nullable=True),
        sa.Column('labor_cost_eur', sa.Numeric(18, 4), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='PLANNED'),
        sa.Column('defects_fixed', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_mold_maint_event_mold', 'mold_id'),
        sa.Index('ix_mold_maint_event_date', 'planned_date'),
        schema='plan',
    )

    op.create_table(
        'mold_defect_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('mold_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.mold.id', ondelete='CASCADE'), nullable=False),
        sa.Column('defect_type', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, server_default='medium'),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('detected_by', sa.String(100), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('linked_rework_ids', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('corrected_by_event_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.mold_maintenance_event.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_mold_defect_mold', 'mold_id'),
        sa.Index('ix_mold_defect_detected', 'tenant_id', 'detected_at'),
        schema='plan',
    )

    op.create_table(
        'mold_usage_counter',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('mold_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('plan.mold.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shot_count_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cycles_since_last_maint', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'mold_id', name='uq_mold_usage_counter'),
        schema='plan',
    )


def downgrade() -> None:
    op.drop_table('mold_usage_counter', schema='plan')
    op.drop_table('mold_defect_log', schema='plan')
    op.drop_table('mold_maintenance_event', schema='plan')
    op.drop_table('mold_health', schema='plan')
    op.drop_table('mold', schema='plan')
