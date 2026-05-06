"""Sprint Q.12 Onda 2.2 — durable kill-switch state.

The previous ``activate_kill_switch`` implementation flipped a decision
row to EXECUTED, emitted a Kafka warning, and that was it. Nothing else
in the system consulted the kill switch, so the docstring promise that
"Decisions in scope are now blocked" was a polite fiction. This adds a
small ``governance.kill_switch_active`` table that handlers consult
before mutating domain state, plus the schema for the per-tenant API.

Tables:
* ``governance.kill_switch_active`` — one row per active scope per
  tenant. Composite PK (tenant_id, scope) — re-activating a scope is
  idempotent. ``deactivated_at`` is stamped on revoke instead of
  deleting the row so the audit trail survives.

Revision ID: 034_kill_switch_active
Revises: 033_decision_chain_invalidated
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '034_kill_switch_active'
down_revision = '033_decision_chain_invalidated'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'kill_switch_active',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope', sa.String(255), nullable=False),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('activated_by', sa.String(100), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deactivated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('tenant_id', 'scope'),
        schema='governance',
    )
    op.create_index(
        'ix_kill_switch_active_open',
        'kill_switch_active',
        ['tenant_id', 'scope'],
        schema='governance',
        # Partial index — handlers only ever care about *currently*
        # active rows, so don't waste pages on the historical tail.
        postgresql_where=sa.text('deactivated_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'ix_kill_switch_active_open',
        table_name='kill_switch_active',
        schema='governance',
    )
    op.drop_table('kill_switch_active', schema='governance')
