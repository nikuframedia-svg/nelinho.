"""Sprint R.1 — quality schema + error_catalog + rework_entry

Revision ID: 018_quality_rework
Revises: 017_product_pricing
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '018_quality_rework'
down_revision = '017_product_pricing'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS quality")

    op.create_table(
        'error_catalog',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('error_code', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('typical_phase', sa.String(100), nullable=True),
        sa.Column('severity_hint', sa.String(16), nullable=False, server_default='medium'),
        sa.Column('preventive_action_hint', sa.Text(), nullable=True),
        sa.Column('mold_related', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'error_code', name='uq_error_catalog_code'),
        sa.Index('ix_error_catalog_typical_phase', 'typical_phase'),
        schema='quality',
    )

    op.create_table(
        'rework_entry',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('original_op_id', sa.String(100), nullable=True),
        sa.Column('rework_op_id', sa.String(100), nullable=True),
        sa.Column('of_id', sa.String(100), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=True),
        sa.Column('causer_employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=True),
        sa.Column('chefe_employee_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('core.employees.id'), nullable=True),
        sa.Column('phase_id_causer', sa.String(100), nullable=True),
        sa.Column('phase_id_rework', sa.String(100), nullable=True),
        sa.Column('error_code', sa.String(64), nullable=False),
        sa.Column('error_description', sa.Text(), nullable=True),
        sa.Column('root_cause_category', sa.String(64), nullable=True),
        sa.Column('mold_id', sa.String(100), nullable=True),
        sa.Column('material_lot_id', sa.String(100), nullable=True),
        sa.Column('supplier_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('detected_by', sa.String(100), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('cost_estimate_eur', sa.Numeric(18, 4), nullable=True),
        sa.Column('hours_lost', sa.Numeric(10, 2), nullable=True),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('ix_rework_entry_of', 'of_id'),
        sa.Index('ix_rework_entry_causer', 'causer_employee_id'),
        sa.Index('ix_rework_entry_error_code', 'error_code'),
        sa.Index('ix_rework_entry_mold', 'mold_id'),
        sa.Index('ix_rework_entry_tenant_detected', 'tenant_id', 'detected_at'),
        schema='quality',
    )


def downgrade() -> None:
    op.drop_table('rework_entry', schema='quality')
    op.drop_table('error_catalog', schema='quality')
