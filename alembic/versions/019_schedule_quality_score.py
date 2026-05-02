"""Sprint R.2 — add quality_risk_score to production_schedules

Revision ID: 019_schedule_quality
Revises: 018_quality_rework
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = '019_schedule_quality'
down_revision = '018b_create_production_schedules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'production_schedules',
        sa.Column(
            'quality_risk_score', sa.Numeric(5, 4), nullable=True,
        ),
        schema='plan',
    )
    op.add_column(
        'production_schedules',
        sa.Column(
            'quality_risk_scored_at', sa.DateTime(timezone=True), nullable=True,
        ),
        schema='plan',
    )
    op.create_index(
        'ix_production_schedules_risk',
        'production_schedules',
        ['quality_risk_score'],
        schema='plan',
    )


def downgrade() -> None:
    op.drop_index('ix_production_schedules_risk', table_name='production_schedules', schema='plan')
    op.drop_column('production_schedules', 'quality_risk_scored_at', schema='plan')
    op.drop_column('production_schedules', 'quality_risk_score', schema='plan')
