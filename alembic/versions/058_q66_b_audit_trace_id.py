"""Q.66.B.1 — coluna trace_id dedicada em core.audit_log.

Antes (Q.61.18): trace_id era hackado no campo `reason` como
`[trace_id=<uuid>] <razao>`. Query por trace_id exigia
`LIKE '%trace_id=...%'` (full table scan, sem indice).

Agora: coluna `trace_id` dedicada + indice. `audit_change()` escreve
directamente; o `reason` deixa de ter o prefixo `[trace_id=...]`.

Backfill: para linhas pre-existentes, extract `[trace_id=X]` do
prefixo do `reason` para a coluna nova e limpa o `reason`.

Revision ID: 058_q66_b_audit_trace_id
Revises: 057_q62_d_commit_status
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = "058_q66_b_audit_trace_id"
down_revision = "057_q62_d_commit_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column("trace_id", sa.String(64), nullable=True),
        schema="core",
    )
    op.create_index(
        "ix_audit_log_trace_id",
        "audit_log",
        ["trace_id"],
        schema="core",
    )
    # Backfill: extract `[trace_id=X]` prefix do `reason` para a coluna.
    # `substring(...)` devolve NULL se o pattern nao casar — seguro para
    # linhas sem trace_id.
    op.execute(
        r"""
        UPDATE core.audit_log
        SET trace_id = substring(reason from '\[trace_id=([^\]]+)\]'),
            reason = NULLIF(
                trim(both ' ' from regexp_replace(
                    reason, '^\[trace_id=[^\]]+\]\s*', ''
                )),
                ''
            )
        WHERE reason ~ '^\[trace_id='
        """
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_trace_id", table_name="audit_log", schema="core")
    op.drop_column("audit_log", "trace_id", schema="core")
