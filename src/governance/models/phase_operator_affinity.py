"""Q.115.A.04 — PhaseOperatorAffinity: afinidade operador/fase.

Score ML de quao bem um operador executa uma fase especifica.
PK composta (tenant_id, operator_id, phase_id).
RLS em q115_a04_phase_operator_affinity.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class PhaseOperatorAffinity(Base):
    """Score de afinidade entre operador e fase. Calculado pelo ML world model."""

    __tablename__ = "phase_operator_affinity"
    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 0 AND 1",
            name="score",
        ),
        CheckConstraint(
            "sample_count >= 0",
            name="sample_count",
        ),
        PrimaryKeyConstraint(
            "tenant_id", "operator_id", "phase_id",
            name="pk_phase_operator_affinity",
        ),
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    operator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    # phase_id e String para compatibilidade com routing_template_phase
    phase_id: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[float] = mapped_column(Float(), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
