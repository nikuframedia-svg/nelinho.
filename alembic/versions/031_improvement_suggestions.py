"""Sprint Q.10 Fase C — improve.improvement_suggestions

Replaces the in-memory ``suggestions_store`` dict + 5 hardcoded
``PREDEFINED_SUGGESTIONS`` in ``src/improve/api.py``. The 5 entries
are seeded per-tenant on first list (handled in service code) so we
don't bake tenant ids into the migration.

Revision ID: 031_improvement_suggestions
Revises: 030_sandbox_scenarios
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '031_improvement_suggestions'
down_revision = '030_sandbox_scenarios'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS improve")

    op.create_table(
        'improvement_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('domain', sa.String(32), nullable=False),
        sa.Column('action_type', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('source', sa.String(20), nullable=False, server_default='seed'),
        sa.Column('estimated_impact', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_improve_suggestions_tenant_status', 'tenant_id', 'status'),
        sa.Index('ix_improve_suggestions_domain', 'tenant_id', 'domain'),
        schema='improve',
    )


def downgrade() -> None:
    op.drop_table('improvement_suggestions', schema='improve')
    op.execute("DROP SCHEMA IF EXISTS improve CASCADE")
