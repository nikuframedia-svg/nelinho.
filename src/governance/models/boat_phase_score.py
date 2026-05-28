"""Q.115.X6.A — BoatPhaseScore: afinidade barco/fase.

Score ML de quão bem um modelo de barco passa por uma fase específica.
PK composta (tenant_id, boat_id, phase_id).
RLS em q115_x6a_boat_phase_score.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class BoatPhaseScore(Base):
    """Score de afinidade entre modelo de barco e fase de produção."""

    __tablename__ = "boat_phase_score"
    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 0 AND 1",
            name="ck_boat_phase_score_score",
        ),
        CheckConstraint(
            "sample_count >= 0",
            name="ck_boat_phase_score_sample_count",
        ),
        PrimaryKeyConstraint(
            "tenant_id", "boat_id", "phase_id",
            name="pk_boat_phase_score",
        ),
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    # boat_id é String para compatibilidade com códigos de produto ERP
    boat_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    phase_id: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[float] = mapped_column(Float(), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
