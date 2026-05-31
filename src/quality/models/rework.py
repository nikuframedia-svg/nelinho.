"""
ProdPlan ONE - Rework + Error Catalog (Sprint R.1 / QA01 / QA02)
=================================================================

QA01 — "Registo de retrabalho com ID do causador (campo chefe)"
QA02 — "Pintura: retrabalho volta para quem causou o erro"

`ReworkEntry` is the single row per rework event, carrying the causer
(chefe when applicable) and the root-cause classification. `ErrorCatalog`
is the normalised vocabulary so reports aggregate cleanly across years
of data (89k events in NELO history).

Both tables live in the `quality` schema.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class ErrorCatalog(TenantBase):
    """Canonical error codes. `error_code` is unique per tenant."""

    __tablename__ = "error_catalog"
    __table_args__ = (
        UniqueConstraint("tenant_id", "error_code", name="uq_error_catalog_code"),
        Index("ix_error_catalog_typical_phase", "typical_phase"),
        {"schema": "quality"},
    )

    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    typical_phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # See factory_data_product.ingest.gravidade.GRAVIDADE_TO_SEVERITY for
    # the source mapping (OFCH_GRAVIDADE 1/2/3 → low/medium/high);
    # confirmed with NELO CEO 2026-04-26. (Onda 3.4 — moved out of the
    # deleted curated_transformer.py.)
    severity_hint: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    preventive_action_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mold_related: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ReworkEntry(TenantBase):
    """A rework event tied to its causer and original op.

    The `causer_employee_id` column is NULLABLE because legacy quality
    events imported from the curated layer don't always identify the
    worker. When the causer is unknown the auto-routing (QA02) simply
    can't fire, and we log a warning.
    """

    __tablename__ = "rework_entry"
    __table_args__ = (
        Index("ix_rework_entry_of", "of_id"),
        Index("ix_rework_entry_causer", "causer_employee_id"),
        Index("ix_rework_entry_error_code", "error_code"),
        Index("ix_rework_entry_mold", "mold_id"),
        Index("ix_rework_entry_location_zone", "location_zone"),
        Index("ix_rework_entry_tenant_detected", "tenant_id", "detected_at"),
        {"schema": "quality"},
    )

    original_op_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rework_op_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    of_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Barco a que o retrabalho diz respeito. A coluna já existe na BD
    # (migração q115_a07_rework_entry_boat_id); mapeada aqui para fechar o
    # drift ORM↔BD detetado na auditoria 2026-05-30.
    boat_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    # Causer — the worker responsible (QA01).
    causer_employee_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=True,
    )
    chefe_employee_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=True,
    )

    phase_id_causer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phase_id_rework: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Q.53.A — hull zone the defect affected (casco / conves / cockpit /
    # interior / acabamento / molde / montagem / outro). Nullable: the NELO
    # checklist has no explicit zone, so it is derived from error_code +
    # phase. Drives the "Mapa do casco" SVG on the Qualidade page.
    location_zone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    mold_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    material_lot_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    supplier_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    cost_estimate_eur: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    hours_lost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Extensible context (root-cause keywords, material batch hints, …).
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
