"""Sprint E.3 — review_notes column on preference_rule

The `/admin/learned-rules` review flow asks the operator to supply a
reason when rejecting a rule (and optionally when confirming with a
caveat). Prior to this migration the table only tracked
`confirmed_at/confirmed_by`; both confirm and reject now write to the
new `review_notes` field so the audit trail keeps the operator's words
verbatim.

Revision ID: 026_preference_rule_review_notes
Revises: 025a_phase_bonus_payout
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = '026_preference_rule_review_notes'
down_revision = '025a_phase_bonus_payout'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'preference_rule',
        sa.Column('review_notes', sa.Text(), nullable=True),
        schema='governance',
    )


def downgrade() -> None:
    op.drop_column(
        'preference_rule',
        'review_notes',
        schema='governance',
    )
