"""Sprint B / CO1 — rejected_alternatives + user_preference_signal on commits

Adds the four columns that turn each `plan_schedule_commits` row into a
learning data point (Plan 22/04 Part 4). Without these columns the
PreferenceRuleDetector, AdaptiveFitnessWeights and DPODatasetBuilder
layers have no input — every approval/rejection would be lost.

Schema changes:
* `rejected_alternatives JSONB` — KPIs + delta + reason for each MAP-Elites
  alternative the operator did NOT choose.
* `user_preference_signal JSONB` — who chose what and when (weekday/hour
  for temporal patterns).
* `evidence_refs JSONB` — links to the factory state / events that fed
  this plan (for DoWhy / Trust Index upstream tracing).
* `scenarios_tested INTEGER` — how many POETIQ iterations / MAP-Elites
  cells contributed before the final commit.

Revision ID: 022_commits_learning
Revises: 023_phase_gaps
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '022_commits_learning'
down_revision = '023_phase_gaps'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'plan_schedule_commits',
        sa.Column(
            'rejected_alternatives',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        'plan_schedule_commits',
        sa.Column(
            'user_preference_signal',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        'plan_schedule_commits',
        sa.Column(
            'evidence_refs',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        'plan_schedule_commits',
        sa.Column(
            'scenarios_tested',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('0'),
        ),
    )


def downgrade() -> None:
    op.drop_column('plan_schedule_commits', 'scenarios_tested')
    op.drop_column('plan_schedule_commits', 'evidence_refs')
    op.drop_column('plan_schedule_commits', 'user_preference_signal')
    op.drop_column('plan_schedule_commits', 'rejected_alternatives')
