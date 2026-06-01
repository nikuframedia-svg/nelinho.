"""Q.138.I: unique partial index em copilot_alerts para dedup robusto

Revision ID: 1b7fc2e9a341
Revises: 0a6edb6dbc74
Create Date: 2026-06-01 05:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b7fc2e9a341'
down_revision: Union[str, None] = '0a6edb6dbc74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Unique partial index (tenant_id, code) WHERE status='active'.

    Garante que existe no maximo 1 alerta activo por (tenant, code),
    a nivel de BD — independente da logica Python. Permite INSERT ...
    ON CONFLICT DO UPDATE (upsert nativo) no _upsert_cpo_alert.

    Antes de criar o index, limpa duplicados activos existentes
    (mantém o mais recente por tenant/code).
    """
    conn = op.get_bind()

    # 1. Limpar duplicados activos — manter o mais recente por (tenant, code)
    conn.execute(sa.text(
        """
        UPDATE copilot_alerts
        SET status = 'resolved',
            resolved_at = NOW(),
            updated_at  = NOW()
        WHERE status = 'active'
          AND id NOT IN (
            SELECT DISTINCT ON (tenant_id, code) id
            FROM copilot_alerts
            WHERE status = 'active'
            ORDER BY tenant_id, code, created_at DESC
          )
        """
    ))

    # 2. Criar unique partial index (production-safe: CONCURRENTLY nao disponivel
    # dentro de transaccao Alembic, por isso usa CREATE UNIQUE INDEX normal;
    # a limpeza acima garante que nao ha conflito no momento da criacao).
    op.create_index(
        'uq_copilot_alerts_active_tenant_code',
        'copilot_alerts',
        ['tenant_id', 'code'],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Remove o unique partial index."""
    op.drop_index(
        'uq_copilot_alerts_active_tenant_code',
        table_name='copilot_alerts',
    )
