"""Sprint Q.2 — rejection_category column on governance.approval

Plan v4 §8 / WG07 requires that every rejection of a decision carries a
*category* (dropdown of 6 values) so the Camada 1 learner has a
machine-readable signal beyond the free-text reason. Free text remains in
`reason`; the new column stores the categorical signal.

Allowed values (validated at the API layer):
    COST | QUALITY | CUSTOMER | CAPACITY | MOLD | WORKFORCE | OTHER

Revision ID: 027_decision_rejection_category
Revises: 026_preference_rule_review_notes
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa


revision = '027_decision_rejection_category'
down_revision = '026_preference_rule_review_notes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'approval',
        sa.Column('rejection_category', sa.String(length=32), nullable=True),
        schema='governance',
    )
    op.create_index(
        'ix_approval_rejection_category',
        'approval',
        ['rejection_category'],
        schema='governance',
    )


def downgrade() -> None:
    op.drop_index(
        'ix_approval_rejection_category',
        table_name='approval',
        schema='governance',
    )
    op.drop_column(
        'approval',
        'rejection_category',
        schema='governance',
    )
