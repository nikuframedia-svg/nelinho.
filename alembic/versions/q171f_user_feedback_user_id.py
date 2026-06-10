"""Q.171.F — coluna user_id em copilot_user_feedback.

A triagem do backlog (F4.E) apanhou o POST /feedback/user a gravar
feedback tenant-anónimo: sem actor, o loop de aprendizagem não sabe QUEM
disse "ajudou / não ajudou". O endpoint passa a exigir UserContext e a
gravar user_id (nullable — linhas antigas ficam válidas).

Revision ID: q171f_user_feedback_user_id
Revises: q171d_decision_runs_target_idx
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q171f_user_feedback_user_id"
down_revision = "q171d_decision_runs_target_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "copilot_user_feedback",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_copilot_user_feedback_user_id",
        "copilot_user_feedback",
        ["user_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_copilot_user_feedback_user_id",
        table_name="copilot_user_feedback",
        if_exists=True,
    )
    op.drop_column("copilot_user_feedback", "user_id")
