"""Q.115.A.09 — WorkerPhaseAssignment: atribuicao operador/fase OF.

Alta cardinalidade. BIGINT PK autoincrement. Regista planeado vs real.
RLS em q115_a09_worker_phase_assignment.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class WorkerPhaseAssignment(Base):
    """Atribuicao de operador a fase de OF (planeada ou real)."""

    __tablename__ = "worker_phase_assignment"
    __table_args__ = (
        CheckConstraint(
            "assignment_type IN ('planned','actual')",
            name="assignment_type",
        ),
        Index(
            "ix_hr_worker_phase_assignment_tenant_worker_assigned",
            "tenant_id", "worker_id", "assigned_at",
        ),
        Index(
            "ix_hr_worker_phase_assignment_tenant_of",
            "tenant_id", "of_id",
        ),
        {"schema": "hr"},
    )

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    worker_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    of_id: Mapped[str] = mapped_column(String(80), nullable=False)
    phase_id: Mapped[str] = mapped_column(String(80), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
