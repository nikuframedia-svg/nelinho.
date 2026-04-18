"""Create tenant_configuration table (Sprint L — Fase 1)

Per-tenant configuration entries. Desbloqueia Sprints AA, M, O, P, Q, R
(Trust Index, Write-Gate rules, CPO hyperparameters, routing templates,
valor de venda por modelo, mold maintenance thresholds).

Revision ID: 013_tenant_configuration
Revises: 012_plan_schedule_commits
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_tenant_configuration'
down_revision = '012_plan_schedule_commits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tenant_configuration',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(64), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('data_type', sa.String(32), nullable=False),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_to', sa.DateTime(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_modified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('last_modified_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'tenant_id', 'category', 'key', 'valid_from',
            name='uq_tenant_configuration_scope',
        ),
        sa.Index(
            'ix_tenant_configuration_tenant_id', 'tenant_id',
        ),
        sa.Index(
            'ix_tenant_configuration_tenant_cat_key',
            'tenant_id', 'category', 'key',
        ),
        schema='core',
    )


def downgrade() -> None:
    op.drop_table('tenant_configuration', schema='core')
