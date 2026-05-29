"""Q.118.R — merge das duas heads alembic da branch -> single head.

A branch feat/q115-painel-4-paginas tinha 2 heads (débito pré-existente):
``q115_x5a_soft_delete_fields`` e ``q117d_kpi_snapshot`` (este encadeia o
q116d). Esta migração de merge (vazia — só junta as cadeias) resolve o
``test_alembic_chain_has_single_head`` sem tocar em esquema.

Revision ID: q118r_merge_heads
Revises: q115_x5a_soft_delete_fields, q117d_kpi_snapshot
Create Date: 2026-05-29
"""

revision = "q118r_merge_heads"
down_revision = ("q115_x5a_soft_delete_fields", "q117d_kpi_snapshot")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge — sem alterações de esquema."""
    pass


def downgrade() -> None:
    """Merge — sem alterações de esquema."""
    pass
