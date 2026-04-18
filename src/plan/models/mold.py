"""
ProdPlan ONE - Mold Maintenance Models (Sprint R.6)
====================================================

Blueprint v2.0 §2.3 INSIGHT: 35% of NELO's 89k quality errors are
"molde com deformações" + "molde baço" — both maintenance symptoms.
This module's five tables make mold health a first-class scheduler
citizen.

Tables (all in `plan` schema):
  * `Mold` — master record (code, pocket count, expected life cycles)
  * `MoldHealth` — most-recent score snapshot (0–100)
  * `MoldMaintenanceEvent` — scheduled / started / completed maintenance
  * `MoldDefectLog` — defect discoveries + optional rework link
  * `MoldUsageCounter` — rolling cycle counter reset at each maintenance

`Mold.mold_code` is the string business key shared with the curated
layer (`CuratedMold.molde_id`). Keeping it a String (not a FK) lets the
scheduler deal with ad-hoc molds the ingestion layer hasn't curated yet.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
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


class Mold(TenantBase):
    """The mold itself. Unique per (tenant, mold_code)."""

    __tablename__ = "mold"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mold_code", name="uq_mold_code"),
        Index("ix_mold_model", "model_id"),
        {"schema": "plan"},
    )

    mold_code: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Blueprint v2.0 §2.7 — up to 7 pockets (2 moulds have that).
    pocket_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mold_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acquired_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    purchase_cost_eur: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    expected_life_cycles: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    replacement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    depreciated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MoldHealth(TenantBase):
    """Most-recent health snapshot. Replace on every recompute.

    `risk_category`: green/yellow/red — thresholds from TenantConfig
    (`mold.health.red_threshold`, `.yellow_threshold` — Sprint L.4).
    """

    __tablename__ = "mold_health"
    __table_args__ = (
        Index("ix_mold_health_mold", "mold_id"),
        Index("ix_mold_health_tenant_score", "tenant_id", "score_0_100"),
        {"schema": "plan"},
    )

    mold_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.mold.id", ondelete="CASCADE"),
        nullable=False,
    )
    score_0_100: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    risk_category: Mapped[str] = mapped_column(String(16), nullable=False, default="green")
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_assessment_due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Breakdown of the weighted formula for observability.
    components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MoldMaintenanceEvent(TenantBase):
    """One maintenance intervention. Status transitions:
    PLANNED → IN_PROGRESS → COMPLETED (or CANCELLED).
    """

    __tablename__ = "mold_maintenance_event"
    __table_args__ = (
        Index("ix_mold_maint_event_mold", "mold_id"),
        Index("ix_mold_maint_event_date", "planned_date"),
        {"schema": "plan"},
    )

    mold_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.mold.id", ondelete="CASCADE"),
        nullable=False,
    )
    maintenance_type: Mapped[str] = mapped_column(String(32), nullable=False, default="preventive")
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_duration_h: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    technician_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.employees.id"),
        nullable=True,
    )
    parts_cost_eur: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    labor_cost_eur: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PLANNED")
    defects_fixed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MoldDefectLog(TenantBase):
    """A defect observation against a mold."""

    __tablename__ = "mold_defect_log"
    __table_args__ = (
        Index("ix_mold_defect_mold", "mold_id"),
        Index("ix_mold_defect_detected", "tenant_id", "detected_at"),
        {"schema": "plan"},
    )

    mold_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.mold.id", ondelete="CASCADE"),
        nullable=False,
    )
    defect_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_rework_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    corrected_by_event_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.mold_maintenance_event.id"),
        nullable=True,
    )


class MoldUsageCounter(TenantBase):
    """Rolling cycle counter. Reset on every completed maintenance."""

    __tablename__ = "mold_usage_counter"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mold_id", name="uq_mold_usage_counter"),
        {"schema": "plan"},
    )

    mold_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.mold.id", ondelete="CASCADE"),
        nullable=False,
    )
    shot_count_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycles_since_last_maint: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
