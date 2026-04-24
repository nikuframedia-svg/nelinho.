"""Sprint C 2.1 — preference_rule (Camada 1 aprendizagem)

Creates `governance.preference_rule` — where the PreferenceRuleDetector
lands each pattern it mines from `plan_schedule_commits.rejected_
alternatives`. See the §50 blueprint "moat" discussion: every confirmed
rule is a unit of tacit knowledge the scheduler honours.

Revision ID: 024_preference_rules
Revises: 022_commits_learning
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '024_preference_rules'
down_revision = '022_commits_learning'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS governance")

    op.create_table(
        'preference_rule',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  nullable=False, index=True),
        sa.Column('type', sa.String(64), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('predicate', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('confidence', sa.Numeric(3, 2), nullable=False),
        sa.Column('status', sa.String(32), nullable=False,
                  server_default='detected'),
        sa.Column('detected_from_commits',
                  postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index(
            'ix_preference_rule_tenant_status', 'tenant_id', 'status',
        ),
        sa.Index(
            'ix_preference_rule_tenant_type', 'tenant_id', 'type',
        ),
        schema='governance',
    )


def downgrade() -> None:
    op.drop_table('preference_rule', schema='governance')
