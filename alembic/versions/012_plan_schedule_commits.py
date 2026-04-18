"""Create plan_schedule_commits (Sprint K.1 — Schedule-as-Code)

Revision ID: 012_plan_schedule_commits
Revises: 011_ml_model_artifacts
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_plan_schedule_commits'
down_revision = '011_ml_model_artifacts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'plan_schedule_commits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),

        # Self-FK chain (like git parent). No DB-level FK constraint so
        # rollbacks / partial restores don't orphan.
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),

        sa.Column('commit_sha256', sa.String(64), nullable=False),

        sa.Column('author', sa.String(255), nullable=False, server_default='system'),
        sa.Column('message', sa.Text(), nullable=False, server_default=''),

        sa.Column('kpis', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('operations', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('delta', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('alternatives', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('cpo_meta', postgresql.JSONB(), nullable=False, server_default='{}'),

        sa.Column('trust_index', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('operations_count', sa.Integer(), nullable=False, server_default='0'),

        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        sa.Index('idx_commits_tenant_created', 'tenant_id', 'created_at'),
        sa.Index('idx_commits_sha', 'commit_sha256'),
    )


def downgrade() -> None:
    op.drop_table('plan_schedule_commits')
