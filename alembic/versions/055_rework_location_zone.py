"""Q.53.A — hull zone on rework_entry (quality.rework_entry.location_zone)

The Qualidade page "Mapa do casco" needs each rework event tagged with the
zone of the kayak hull it affected (casco / convés / cockpit / interior /
acabamento / molde / outro). The NELO ERP checklist does not carry an
explicit zone, so the column is nullable and the backfill below derives a
best-effort zone from the error-code prefix and the checklist phase name —
the same heuristic the defect-zones endpoint uses at read time for rows
that arrive without a zone.

Revision ID: 055_rework_location_zone
Revises: 054_purchase_orders
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = "055_rework_location_zone"
down_revision = "054_purchase_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rework_entry",
        sa.Column("location_zone", sa.String(32), nullable=True),
        schema="quality",
    )
    op.create_index(
        "ix_rework_entry_location_zone",
        "rework_entry",
        ["location_zone"],
        schema="quality",
    )

    # Best-effort backfill: derive the zone from the error-code prefix and
    # the checklist phase name. Mirrors src.quality.services.defect_zone_
    # service.derive_zone so historical and future rows agree.
    op.execute(
        """
        UPDATE quality.rework_entry SET location_zone = CASE
            WHEN error_code ILIKE 'laminagem%' OR error_code ILIKE 'interior%'
                 OR error_code ILIKE 'gel%' OR error_code ILIKE 'massaresina%'
                 OR error_code ILIKE 'excesso-de-resina%' THEN 'casco'
            WHEN error_code ILIKE 'pintura%'  THEN 'acabamento'
            WHEN error_code ILIKE 'molde%'    THEN 'molde'
            WHEN error_code ILIKE 'danos%'    THEN 'conves'
            WHEN error_code ILIKE 'falta%'    THEN 'montagem'
            WHEN COALESCE(context->>'phase_name','') ILIKE '%lamina%'  THEN 'casco'
            WHEN COALESCE(context->>'phase_name','') ILIKE '%pintura%' THEN 'acabamento'
            WHEN COALESCE(context->>'phase_name','') ILIKE '%desmolde%' THEN 'conves'
            WHEN COALESCE(context->>'phase_name','') ILIKE '%molde%'   THEN 'molde'
            WHEN COALESCE(context->>'phase_name','') ILIKE '%lixagem%' THEN 'acabamento'
            WHEN COALESCE(context->>'phase_name','') ILIKE '%montagem%' THEN 'montagem'
            ELSE 'outro'
        END
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rework_entry_location_zone", table_name="rework_entry", schema="quality"
    )
    op.drop_column("rework_entry", "location_zone", schema="quality")
