"""Sprint X.1 — TenantConfiguration.source provenance column.

Plan v4 §4.7 design prompt requires every editable parameter to surface
its provenance: was the value set from the system default, manually by
an operator, or by an applied learned rule? Today the row already
stores `last_modified_by` and `last_modified_at` but not the *origin*
of the value, so the UI cannot render a "Source: manual" badge
reliably (it could only infer from `created_by==system_uid` heuristics).

This migration adds a NOT NULL ``source`` text column with a CHECK
constraint pinning it to the closed vocabulary
``('default', 'manual', 'learned_rule')`` and DEFAULT ``'default'``.
Existing rows are backfilled to ``'default'`` so the read API always
returns a value. Future writes set the column at the service layer.

Revision ID: 046_tenant_configuration_source
Revises: 045_rule_firing_variant_index
Create Date: 2026-05-07
"""

import sqlalchemy as sa
from alembic import op


revision = "046_tenant_configuration_source"
down_revision = "045_rule_firing_variant_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_configuration",
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'default'"),
        ),
        schema="core",
    )
    op.create_check_constraint(
        "ck_tenant_configuration_source",
        "tenant_configuration",
        "source IN ('default', 'manual', 'learned_rule')",
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tenant_configuration_source",
        "tenant_configuration",
        type_="check",
        schema="core",
    )
    op.drop_column(
        "tenant_configuration",
        "source",
        schema="core",
    )
