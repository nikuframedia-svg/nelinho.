"""Sprint Q.14.A — `governance.rule_firing` log.

Closes the trust-breaking gap identified in the post-Q.13.H audit:
*"why did the system suggest moving this batch 3 weeks ago?"* — the
16 deterministic + LLM detectors in the codebase produce suggestions
that flow into the operator surface, but none of them log the
trigger that fired them. Forensics today require git blame + manual
reading of detector source.

Schema deliberately mirrors `PreferenceRule` (same review-state
lifecycle: ``proposed → accepted | rejected | expired | superseded``).
JSONB ``trigger_payload`` carries the inputs that caused the fire;
``rule_output`` carries the suggestion / alert produced. The pair lets
operators reconstruct the decision long after the source data has
moved on.

``dedupe_key`` is the anti-spam mechanism: the alerts engine scans
every 15 minutes; without dedupe a single underlying problem (batch
B-1 with 3 unassigned boats) would create 96 rows per day per
detector. With dedupe, repeated firings collapse to a single row
whose ``fired_at`` is updated. Indexes pick up the (tenant, dedupe)
lookup in O(log n).

``variant_id`` is forward-look for the A/B framework (Q.14.C). NULL
today; populated when a decorator wraps multiple variants of the
same rule.

Revision ID: 043_rule_firing_log
Revises: 042_hot_query_indexes
Create Date: 2026-05-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "043_rule_firing_log"
down_revision = "042_hot_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rule_firing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column("variant_id", sa.String(120), nullable=True),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "trigger_payload",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "rule_output",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        sa.Column(
            "outcome",
            sa.String(32),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        # Spam-collapse counter: each repeated firing within the dedupe
        # window increments instead of inserting a new row. NULL/0 = first.
        sa.Column(
            "fire_count",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "last_fired_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="governance",
    )

    # Hot path: list latest firings per (tenant, rule_id) for the audit page.
    op.create_index(
        "ix_rule_firing_tenant_rule_fired",
        "rule_firing",
        ["tenant_id", "rule_id", sa.text("fired_at DESC")],
        schema="governance",
    )
    # Dedupe path: decorator looks up "is there an open row for this key?"
    op.create_index(
        "ix_rule_firing_tenant_dedupe_fired",
        "rule_firing",
        ["tenant_id", "dedupe_key", sa.text("fired_at DESC")],
        schema="governance",
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    # Adoption stats path (foundation for Q.14.C):
    # "for rule X, group by outcome".
    op.create_index(
        "ix_rule_firing_outcome_fired",
        "rule_firing",
        ["outcome", sa.text("fired_at DESC")],
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rule_firing_outcome_fired",
        table_name="rule_firing",
        schema="governance",
    )
    op.drop_index(
        "ix_rule_firing_tenant_dedupe_fired",
        table_name="rule_firing",
        schema="governance",
    )
    op.drop_index(
        "ix_rule_firing_tenant_rule_fired",
        table_name="rule_firing",
        schema="governance",
    )
    op.drop_table("rule_firing", schema="governance")
