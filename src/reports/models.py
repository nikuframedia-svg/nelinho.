"""ProdPlan ONE — Reports models (Sprint Q.22.D).

:class:`ReportSchedule` — a recurring report definition (type + cron +
recipients + retention policy).

:class:`ReportRun` — one execution of a report, ad-hoc or
schedule-driven. Carries the generated ``payload`` (JSONB) and the
delivery outcome. The retention job (Q.22.G) prunes old runs using the
owning schedule's ``retention_days``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase

# Closed whitelist — the report templates that have a real generator.
# Mirrors the ``TemplateId`` Pydantic ``Literal`` in api.py.
REPORT_TYPES = ("payroll", "cogs", "inventario")
REPORT_FORMATS = ("csv", "json")
RUN_STATUSES = ("pending", "generated", "delivered", "failed")


class ReportSchedule(TenantBase):
    """A recurring report definition.

    ``cron`` is a free-form cron expression (e.g. ``0 8 * * MON``).
    ``recipients`` is a JSONB list of email addresses. ``enabled``
    pauses the schedule without deleting it. ``retention_days`` drives
    the cleanup job for runs spawned by this schedule.
    """

    __tablename__ = "report_schedule"
    __table_args__ = (
        Index("ix_report_schedule_tenant_enabled", "tenant_id", "enabled"),
        {"schema": "reports"},
    )

    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    cron: Mapped[str] = mapped_column(String(120), nullable=False)
    recipients: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="csv")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ReportSchedule {self.report_type} cron={self.cron!r}>"


class ReportRun(TenantBase):
    """One execution of a report — ad-hoc or schedule-driven.

    ``schedule_id`` is null for ad-hoc runs (no owning schedule).
    ``payload`` is the verbatim generator output. ``delivered_to``
    records the addresses an email delivery actually reached.
    """

    __tablename__ = "report_run"
    __table_args__ = (
        Index("ix_report_run_tenant_generated", "tenant_id", "generated_at"),
        Index("ix_report_run_schedule", "schedule_id"),
        {"schema": "reports"},
    )

    # Nullable: ad-hoc runs have no owning schedule.
    schedule_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
    )
    delivered_to: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ReportRun {self.report_type} {self.status}>"
