"""Sprint Q.8 Fase 2 — factory_curated.allocation

Materialise the worker × order-phase allocations from the Excel sheet
`FuncionariosFaseOrdemFabrico` (423,769 rows). Until now the ORM class
existed only via `Base.metadata.create_all()` at app startup; this
migration captures the schema explicitly so production deploys have a
versioned record (Alembic + create_all are both idempotent — running
both is safe).

Revision ID: 028_curated_allocation
Revises: 027_decision_rejection_category
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision = '028_curated_allocation'
# Q.62.A.2 — rebase: 028b cria factory_meta.ingestion_run, FK target.
down_revision = '028b_q62_factory_meta'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS factory_curated")
    op.create_table(
        'allocation',
        sa.Column('id', PGUUID(as_uuid=True), primary_key=True),
        sa.Column('ingestion_id', PGUUID(as_uuid=True), nullable=False),
        sa.Column('fase_of_id', sa.String(length=100), nullable=False),
        sa.Column('funcionario_id', sa.String(length=100), nullable=False),
        sa.Column('is_chefe', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_quarantined', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('quarantine_reason', sa.String(length=500), nullable=True),
        sa.Column('quarantine_code', sa.String(length=50), nullable=True),
        sa.Column('quarantined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at_utc', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['ingestion_id'], ['factory_meta.ingestion_run.id'],
        ),
        schema='factory_curated',
    )
    op.create_index(
        'ix_curated_allocation_ingestion',
        'allocation',
        ['ingestion_id'],
        schema='factory_curated',
    )
    op.create_index(
        'ix_curated_allocation_fase_of',
        'allocation',
        ['fase_of_id'],
        schema='factory_curated',
    )
    op.create_index(
        'ix_curated_allocation_funcionario',
        'allocation',
        ['funcionario_id'],
        schema='factory_curated',
    )
    op.create_index(
        'ix_curated_allocation_composite',
        'allocation',
        ['fase_of_id', 'funcionario_id'],
        schema='factory_curated',
    )


def downgrade() -> None:
    op.drop_index(
        'ix_curated_allocation_composite',
        table_name='allocation',
        schema='factory_curated',
    )
    op.drop_index(
        'ix_curated_allocation_funcionario',
        table_name='allocation',
        schema='factory_curated',
    )
    op.drop_index(
        'ix_curated_allocation_fase_of',
        table_name='allocation',
        schema='factory_curated',
    )
    op.drop_index(
        'ix_curated_allocation_ingestion',
        table_name='allocation',
        schema='factory_curated',
    )
    op.drop_table('allocation', schema='factory_curated')
