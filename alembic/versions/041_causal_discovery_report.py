"""Sprint Q.13.D D.2 — `governance.causal_discovery_report` table.

Persists the output of the weekly PCMCI+ run so:

  * Operators can review candidate edges in the admin surface before
    they touch :data:`src.copilot.causal.nelo_dag.ALL_NODES`
    (engineering artefact, not stats lottery).
  * The audit trail records *why* a row was approved / rejected, the
    sample size the run was based on, and the engine version, so
    later forensics has a defensible answer to "where did edge X
    come from?".

Schema mirrors `PreferenceRule` deliberately — same review-state
pattern (pending/approved/rejected) so the frontend gets it for free.

Revision ID: 041_causal_discovery_report
Revises: 040_slow_query_logging
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "041_causal_discovery_report"
down_revision = "040_slow_query_logging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "causal_discovery_report",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "engine",
            sa.String(64),
            nullable=False,
            server_default="tigramite-pcmci+",
        ),
        sa.Column("run_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tau_max", sa.Integer, nullable=False, server_default="0"),
        sa.Column("nodes_examined", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "candidate_edges",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(120), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        schema="governance",
    )
    op.create_index(
        "ix_causal_discovery_tenant_status",
        "causal_discovery_report",
        ["tenant_id", "review_status"],
        schema="governance",
    )
    op.create_index(
        "ix_causal_discovery_discovered_at",
        "causal_discovery_report",
        ["discovered_at"],
        schema="governance",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_causal_discovery_discovered_at",
        table_name="causal_discovery_report",
        schema="governance",
    )
    op.drop_index(
        "ix_causal_discovery_tenant_status",
        table_name="causal_discovery_report",
        schema="governance",
    )
    op.drop_table("causal_discovery_report", schema="governance")
