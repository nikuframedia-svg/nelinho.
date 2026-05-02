"""Sprint Q.10 Fase B — sandbox.sandbox_scenarios

Replaces the in-memory ``sandbox_store`` dict with a real DB-backed
table. One row per sandbox scenario, scoped per tenant. The
``decision_id`` column is populated when ``publish`` creates a
``SharedDecisionRun`` (advisory mode until Sprint G).

Revision ID: 030_sandbox_scenarios
Revises: 029_curated_modelo
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '030_sandbox_scenarios'
down_revision = '029_curated_modelo'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS sandbox")

    op.create_table(
        'sandbox_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('suggestion_id', sa.String(64), nullable=True),
        sa.Column('before_state', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('after_state', postgresql.JSONB(), nullable=True),
        sa.Column('impact', postgresql.JSONB(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_sandbox_scenarios_tenant_status', 'tenant_id', 'status'),
        sa.Index('ix_sandbox_scenarios_suggestion', 'suggestion_id'),
        schema='sandbox',
    )


def downgrade() -> None:
    op.drop_table('sandbox_scenarios', schema='sandbox')
    op.execute("DROP SCHEMA IF EXISTS sandbox CASCADE")
