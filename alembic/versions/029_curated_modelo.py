"""Sprint Q.8 Fase 3 — factory_curated.modelo

Materialise the product/model catalogue from the Excel sheet `Modelos`
(899 rows; the sheet name is "Modelos" but its rows are products with
`Produto_*` prefixes — the curated table keeps the planning-level name
`modelo`). The ORM is also created via `Base.metadata.create_all()` at
app startup; this migration is the explicit, versioned record.

Revision ID: 029_curated_modelo
Revises: 028_curated_allocation
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision = '029_curated_modelo'
down_revision = '028_curated_allocation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS factory_curated")
    op.create_table(
        'modelo',
        sa.Column('id', PGUUID(as_uuid=True), primary_key=True),
        sa.Column('ingestion_id', PGUUID(as_uuid=True), nullable=False),
        sa.Column('produto_id', sa.String(length=100), nullable=False),
        sa.Column('produto_nome', sa.String(length=500), nullable=True),
        sa.Column('modelo_id', sa.String(length=100), nullable=True),
        sa.Column('tamanho_id', sa.String(length=100), nullable=True),
        sa.Column('peso_desmolde_kg', sa.Numeric(8, 3), nullable=True),
        sa.Column('peso_acabamento_kg', sa.Numeric(8, 3), nullable=True),
        sa.Column('qtd_gel_deck', sa.Numeric(8, 3), nullable=True),
        sa.Column('qtd_gel_casco', sa.Numeric(8, 3), nullable=True),
        sa.Column('numero_pocos_id', sa.String(length=100), nullable=True),
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
        'ix_curated_modelo_ingestion',
        'modelo',
        ['ingestion_id'],
        schema='factory_curated',
    )
    op.create_index(
        'ix_curated_modelo_produto',
        'modelo',
        ['produto_id'],
        schema='factory_curated',
    )
    op.create_index(
        'ix_curated_modelo_modelo_id',
        'modelo',
        ['modelo_id'],
        schema='factory_curated',
    )


def downgrade() -> None:
    op.drop_index(
        'ix_curated_modelo_modelo_id',
        table_name='modelo',
        schema='factory_curated',
    )
    op.drop_index(
        'ix_curated_modelo_produto',
        table_name='modelo',
        schema='factory_curated',
    )
    op.drop_index(
        'ix_curated_modelo_ingestion',
        table_name='modelo',
        schema='factory_curated',
    )
    op.drop_table('modelo', schema='factory_curated')
