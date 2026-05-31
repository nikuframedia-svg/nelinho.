"""Q.115.A.02 — DailyRevenueTarget: meta de receita diaria.

Append-only por data. Tenant-scoped. RLS em q115_a02_daily_revenue_target.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Date, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class DailyRevenueTarget(Base):
    """Meta de receita diaria. Append-only — uma linha por (tenant, data)."""

    __tablename__ = "daily_revenue_target"
    __table_args__ = (
        CheckConstraint("target_eur > 0", name="ck_daily_revenue_target_positive"),
        UniqueConstraint(
            "tenant_id", "effective_from",
            name="uq_daily_revenue_target_tenant_date",
        ),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    effective_from: Mapped[date] = mapped_column(Date(), nullable=False)
    target_eur: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    audit_trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
