"""Q.66.E.1 - backoff exponencial em EventOutbox.

Antes: retry no proximo ciclo do dispatcher (imediato). Kafka instavel =
busy-loop (dispatcher pega no mesmo event_outbox 5x em ~25s e move para
DLQ sem nunca dar tempo ao Kafka de recuperar).

Agora: coluna `next_retry_at` indexed. Dispatcher faz
SELECT WHERE status='pending' AND (next_retry_at IS NULL OR next_retry_at <= now()).
Em falha, dispatcher escreve next_retry_at = now() + min(2^retry_count * 1s, 5min).
Sequencia: retry 0 -> 1s, retry 1 -> 2s, retry 2 -> 4s, retry 4 -> 16s,
retry 8 -> 256s, retry >=9 -> capped a 300s (5min).

Revision ID: 059_q66_e_outbox_backoff
Revises: 058_q66_b_audit_trace_id
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = "059_q66_e_outbox_backoff"
down_revision = "058_q66_b_audit_trace_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_outbox",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_event_outbox_next_retry_at",
        "event_outbox",
        ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_outbox_next_retry_at", table_name="event_outbox")
    op.drop_column("event_outbox", "next_retry_at")
