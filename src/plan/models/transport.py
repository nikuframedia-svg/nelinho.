"""
ProdPlan ONE - Transport Batch Models (Sprint P.2 / PL14)
==========================================================

A `TransportBatch` groups `ProductionOrder`s destined for the same truck
trip so the backwards-scheduler can anchor operations to `transport_date`
and the fitness function can penalise spread-out batch completions.

Blueprint v2.0 §2.5 — 82 boats/transport_date median; 50 barcos/truck per
the CEO. `default_batch_size=50` is seeded via TenantConfig.planning.transport.

`TransportBatchAssignment` is the many-to-many link (one ProductionOrder
can belong to only one active batch — enforced via unique constraint).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class TransportBatch(TenantBase):
    """A truck's worth of boats heading to the same destination on the same date.

    `priority` is a scheduler hint: lower = served first (same as 1-indexed
    queue position). `status` is the lifecycle marker:
      OPEN      — still accumulating assignments
      FROZEN    — locked against further changes
      DISPATCHED — already left (scheduler ignores it)
    """

    __tablename__ = "transport_batch"
    __table_args__ = (
        Index("ix_transport_batch_date", "transport_date"),
        Index("ix_transport_batch_tenant_date_status", "tenant_id", "transport_date", "status"),
        {"schema": "plan"},
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_date: Mapped[date] = mapped_column(Date, nullable=False)
    truck_capacity_units: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")


class TransportBatchAssignment(TenantBase):
    """Order → batch link. Enforces one-batch-per-order via unique index."""

    __tablename__ = "transport_batch_assignment"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "order_id",
            name="uq_transport_batch_assignment_order",
        ),
        {"schema": "plan"},
    )

    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan.transport_batch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
