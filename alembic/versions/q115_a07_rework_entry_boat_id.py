"""Q.115.A.07 — ADD COLUMN quality.rework_entry.boat_id.

Adiciona boat_id (referencia ao barco especifico, ex: numero de serie ou
identificador interno) a rework_entry. Nullable para nao quebrar registos
existentes. Backfill vem em script separado quando Q.115.E for implementado.

quality.rework_entry foi criada em 018_quality_rework (main).

Revision ID: q115_a07_rework_entry_boat_id
Revises: q115_a06_error_type_runbook_link
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "q115_a07_rework_entry_boat_id"
down_revision = "q115_a06_error_type_runbook_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rework_entry",
        sa.Column("boat_id", sa.String(80), nullable=True),
        schema="quality",
    )
    op.create_index(
        "ix_quality_rework_entry_boat_id",
        "rework_entry",
        ["boat_id"],
        schema="quality",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quality_rework_entry_boat_id",
        table_name="rework_entry",
        schema="quality",
    )
    op.drop_column("rework_entry", "boat_id", schema="quality")
