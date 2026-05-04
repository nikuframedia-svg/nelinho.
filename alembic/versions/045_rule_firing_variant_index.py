"""Sprint Q.14.C — composite index for variant adoption queries.

The A/B adoption stats endpoint groups rule_firing rows by
``(tenant_id, rule_id, variant_id, outcome)`` to compute acceptance
rates per variant. Without an index, that aggregation does a sequential
scan over the whole table — fine at 10k rows, painful past 1M.

This index covers the entire WHERE + GROUP BY of the hot query so
Postgres serves it via index-only scan. The tail order column
``fired_at DESC`` lets the same index also serve "give me the last 100
firings for this rule + variant" without an extra index.

Revision ID: 045_rule_firing_variant_index
Revises: 044_rule_firing_pg_notify
Create Date: 2026-05-04
"""

import sqlalchemy as sa
from alembic import op


revision = "045_rule_firing_variant_index"
down_revision = "044_rule_firing_pg_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial index: only rows that have a variant_id assigned (the
    # bulk of audit-only firings have variant_id NULL and don't need
    # this lookup path). Smaller index = cheaper writes + scans.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_rule_firing_variant_adoption
        ON governance.rule_firing
            (tenant_id, rule_id, variant_id, outcome, fired_at DESC)
        WHERE variant_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS governance.ix_rule_firing_variant_adoption"
    )
