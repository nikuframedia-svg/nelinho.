"""Q.171.D — índice (tenant_id, action_type, target) em shared.decision_runs.

O job ``auto_propose_signals_job._blocked_targets`` varre TODAS as decisões
do tenant a cada tick de 15 min para não re-propor o mesmo target. Sem
índice composto, é um seq-scan que cresce com o histórico de decisões.

Revision ID: q171d_decision_runs_target_idx
Revises: q167f2_erp_variables
Create Date: 2026-06-10
"""
from alembic import op

revision = "q171d_decision_runs_target_idx"
down_revision = "q167f2_erp_variables"
branch_labels = None
depends_on = None

_IDX = "ix_decision_runs_tenant_action_target"


def upgrade() -> None:
    op.create_index(
        _IDX,
        "decision_runs",
        ["tenant_id", "action_type", "target"],
        schema="shared",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(_IDX, table_name="decision_runs", schema="shared", if_exists=True)
