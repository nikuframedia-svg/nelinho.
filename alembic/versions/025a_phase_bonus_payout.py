"""Sprint A / CX4 — phase_bonus_payout (CoeficienteX moved to profit)

The ERP field `ProdutoFase_CoeficienteX` is the monetary bonus paid per
(product × phase), NOT the second worker's time. This migration creates
the canonical table that owns that value in profit/.

Revision ID: 025a_phase_bonus
Revises: 020_mold_maintenance
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '025a_phase_bonus'
down_revision = '020_mold_maintenance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS profit")

    op.create_table(
        'phase_bonus_payout',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  nullable=False, index=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.products.id'), nullable=False),
        sa.Column('phase_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bonus_eur', sa.Numeric(18, 4), nullable=False),
        sa.Column('currency_code', sa.String(3), nullable=False,
                  server_default='EUR'),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('source', sa.String(32), nullable=False,
                  server_default='ERP_STANDARD'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'tenant_id', 'product_id', 'phase_id', 'valid_from',
            name='uq_phase_bonus_payout_validity',
        ),
        sa.Index('ix_phase_bonus_payout_product_phase',
                 'tenant_id', 'product_id', 'phase_id'),
        schema='profit',
    )


def downgrade() -> None:
    op.drop_table('phase_bonus_payout', schema='profit')
