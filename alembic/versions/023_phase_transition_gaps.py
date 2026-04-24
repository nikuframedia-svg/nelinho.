"""Sprint A / D2+ST1 — phase_transition_gap (curing/drying constraints)

Blueprint v2.0 §3.8 — 16 transitions with mandatory minimum wait between
consecutive phases. Prevents the scheduler from generating physically
impossible plans (ex: sand paint before it has dried).

Revision ID: 023_phase_gaps
Revises: 025a_phase_bonus
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '023_phase_gaps'
down_revision = '025a_phase_bonus'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'phase_transition_gap',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  nullable=False, index=True),
        sa.Column('from_phase_code', sa.String(64), nullable=False),
        sa.Column('to_phase_code', sa.String(64), nullable=False),
        sa.Column('min_gap_hours', sa.Numeric(5, 2), nullable=False),
        sa.Column('reason', sa.String(128), nullable=True),
        sa.Column('n_observations', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'tenant_id', 'from_phase_code', 'to_phase_code',
            name='uq_phase_transition_gap_pair',
        ),
        sa.Index('ix_phase_transition_gap_lookup',
                 'tenant_id', 'from_phase_code', 'to_phase_code'),
        schema='plan',
    )


def downgrade() -> None:
    op.drop_table('phase_transition_gap', schema='plan')
