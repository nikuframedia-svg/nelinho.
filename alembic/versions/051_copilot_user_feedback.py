"""Q.31.H — copilot_user_feedback table.

Persiste o feedback ad-hoc 👍/👎 + texto livre que a UI do Copilot
(`DailyFeedbackForm`) já enviava para `/api/copilot/feedback/user`. Antes
o endpoint era um stub log-only — o sinal perdia-se.

Tenant-scoped (`TenantBase`): `id` / `tenant_id` / `created_at` /
`updated_at` + as colunas do feedback. Sem schema (tabelas copilot vivem
no schema público, como `copilot_action_logs`).

Revision ID: 051_copilot_user_feedback
Revises: 050_reports
Create Date: 2026-05-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "051_copilot_user_feedback"
down_revision = "050_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "copilot_user_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("thumb", sa.String(length=8), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_copilot_user_feedback_tenant", "copilot_user_feedback", ["tenant_id"],
    )
    op.create_index(
        "idx_copilot_user_feedback_thumb",
        "copilot_user_feedback", ["tenant_id", "thumb"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_copilot_user_feedback_thumb", table_name="copilot_user_feedback",
    )
    op.drop_index(
        "idx_copilot_user_feedback_tenant", table_name="copilot_user_feedback",
    )
    op.drop_table("copilot_user_feedback")
