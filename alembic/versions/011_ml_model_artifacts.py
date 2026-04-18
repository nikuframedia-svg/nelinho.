"""Create ml_model_artifact table (Sprint G — ML Learning Infrastructure)

Revision ID: 011_ml_model_artifacts
Revises: 010_copilot_alerts
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_ml_model_artifacts'
down_revision = '010_copilot_alerts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ml_model_artifact',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('model_name', sa.String(128), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('storage_uri', sa.Text(), nullable=False),
        sa.Column('metrics', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('promoted_by_decision_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('promoted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('promoted_by', sa.String(255), nullable=True),
        sa.Column('trained_by', sa.String(255), nullable=False, server_default='system'),
        sa.Column('training_duration_sec', sa.Float(), nullable=True),
        sa.Column('training_samples', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('idx_ml_artifact_tenant_name', 'tenant_id', 'model_name'),
        sa.Index('idx_ml_artifact_active', 'tenant_id', 'model_name', 'active'),
        sa.Index('idx_ml_artifact_created', 'created_at'),
        sa.UniqueConstraint('tenant_id', 'model_name', 'version', name='uq_ml_artifact_version'),
    )


def downgrade() -> None:
    op.drop_table('ml_model_artifact')
