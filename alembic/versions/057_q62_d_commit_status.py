"""Q.62.D.4 — `ScheduleCommit.status` column DRAFT|LIVE.

Schedule-as-code: commits criados pelo CPO scheduler começam DRAFT.
Approver revê e via `PUT /v1/plan/cpo/schedule/job/{job_id}/approve`
promove para LIVE. Decision-as-code mais granular do que o auto-commit
existente.

Q.62.D.2 — endpoint sync `POST /schedule` continua a criar commits
(transitória), mas o async path com Arq cria DRAFT que requer approve.

Revision ID: 057_q62_d_commit_status
Revises: 056_q62_b_rls_enable
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = "057_q62_d_commit_status"
down_revision = "056_q62_b_rls_enable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plan_schedule_commits",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="DRAFT",
        ),
        # plan_schedule_commits vive no schema default (public) — sem schema=
    )
    op.create_index(
        "ix_plan_schedule_commits_status",
        "plan_schedule_commits",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_plan_schedule_commits_status", "plan_schedule_commits")
    op.drop_column("plan_schedule_commits", "status")
