"""Q.32.B.2 — liga copilot_user_feedback à sugestão que o originou.

A tabela `copilot_user_feedback` (051) era um sinal órfão: 👍/👎 gravados
sem qualquer ligação à resposta avaliada nem a quem avaliou. Sem isso o
loop de aprendizagem (Q.32.C.1) não consegue juntar feedback↔intent.

Adiciona três colunas nullable (as linhas existentes ficam a NULL):
- `suggestion_id`   — UUID da `copilot_suggestion` avaliada (+ índice).
- `correlation_id`  — UUID de correlação do pedido.
- `actor_id`        — UUID de quem submeteu o feedback.

Revision ID: 053_copilot_feedback_audit_link
Revises: 052_user_password_hash
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from alembic import op


revision = "053_copilot_feedback_audit_link"
down_revision = "052_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "copilot_user_feedback",
        sa.Column("suggestion_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "copilot_user_feedback",
        sa.Column("correlation_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "copilot_user_feedback",
        sa.Column("actor_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "idx_copilot_user_feedback_suggestion",
        "copilot_user_feedback",
        ["suggestion_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_copilot_user_feedback_suggestion",
        table_name="copilot_user_feedback",
    )
    op.drop_column("copilot_user_feedback", "actor_id")
    op.drop_column("copilot_user_feedback", "correlation_id")
    op.drop_column("copilot_user_feedback", "suggestion_id")
