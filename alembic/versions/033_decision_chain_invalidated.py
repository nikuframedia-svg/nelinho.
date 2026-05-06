"""Sprint Q.12 Onda 1.5 — chain-invalidation flag on decision_run.

When ``modify_payload`` rewrites an existing decision's ``input_hash``
the resulting ``audit_hash`` no longer matches the ``prev_hash`` carried
by any decision proposed *after* it: those descendants now reference a
hash that is no longer the source-of-truth for the modified row, so the
chain is silently broken. Sprint Q.12 Onda 1.2 surfaces this via
:meth:`_verify_hash_chain`, but compliance reviewers also want a
durable per-row flag so they can filter the timeline. This migration
adds:

* ``governance.decision_run.chain_invalidated`` (bool, default false)
* ``governance.decision_run.chain_invalidated_at`` (timestamptz, null)
* ``governance.decision_run.chain_invalidated_by_modify_id`` (uuid, FK,
  null) — points back at the decision whose ``modify_payload`` triggered
  the invalidation, so a forensic timeline can answer "which edit broke
  this chain?"

Revision ID: 033_decision_chain_invalidated
Revises: 032_hr_profit_operacoes
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '033_decision_chain_invalidated'
down_revision = '032_hr_profit_operacoes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'decision_run',
        sa.Column(
            'chain_invalidated',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema='governance',
    )
    op.add_column(
        'decision_run',
        sa.Column(
            'chain_invalidated_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema='governance',
    )
    op.add_column(
        'decision_run',
        sa.Column(
            'chain_invalidated_by_modify_id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema='governance',
    )
    op.create_index(
        'ix_decision_run_chain_invalidated',
        'decision_run',
        ['chain_invalidated'],
        schema='governance',
        # Partial index — most rows will be ``false``, so we only index
        # the few that compliance actually filters on.
        postgresql_where=sa.text('chain_invalidated = true'),
    )


def downgrade() -> None:
    op.drop_index(
        'ix_decision_run_chain_invalidated',
        table_name='decision_run',
        schema='governance',
    )
    op.drop_column('decision_run', 'chain_invalidated_by_modify_id', schema='governance')
    op.drop_column('decision_run', 'chain_invalidated_at', schema='governance')
    op.drop_column('decision_run', 'chain_invalidated', schema='governance')
