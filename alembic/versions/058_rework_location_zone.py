"""Q.51 — quality.rework_entry.location_zone (F11 — mapa de defeitos por zona).

O retrabalho era analisado por operador / modelo / molde / fase, mas nunca
pela ZONA do casco onde o defeito foi marcado. Esta coluna guarda essa zona
(derivada de ``OFCH_LOCAL`` × ``PROBS_LOCAL`` pelo mirror de qualidade) para
o heatmap de defeitos por zona.

Nullable: incidentes legados importados da camada curada sem zona ficam a
NULL. Em dev a coluna é criada por ``Base.metadata.create_all``; esta
migração cobre produção.

Revision ID: 058_rework_location_zone
Revises: 057_factory_calendar_day
Create Date: 2026-05-19
"""

import sqlalchemy as sa
from alembic import op


revision = "058_rework_location_zone"
down_revision = "057_factory_calendar_day"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rework_entry",
        sa.Column("location_zone", sa.String(length=255), nullable=True),
        schema="quality",
    )
    op.create_index(
        "ix_rework_entry_location_zone",
        "rework_entry",
        ["location_zone"],
        schema="quality",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rework_entry_location_zone",
        table_name="rework_entry",
        schema="quality",
    )
    op.drop_column("rework_entry", "location_zone", schema="quality")
