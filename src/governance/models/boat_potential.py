"""Q.115.X6.B — BoatPotential: score de potencialidade por barco.

Combina 4 componentes históricas (margem, throughput, low_defect, lead_time)
num score [0,1] que indica quão "potente" é um modelo de barco para planning.
PK composta (tenant_id, boat_id).
RLS em q115_x6b_boat_potential.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class BoatPotential(Base):
    """Score de potencialidade de um modelo de barco para a fábrica."""

    __tablename__ = "boat_potential"
    __table_args__ = (
        CheckConstraint(
            "potential_score BETWEEN 0 AND 1",
            name="ck_boat_potential_score",
        ),
        PrimaryKeyConstraint(
            "tenant_id", "boat_id",
            name="pk_boat_potential",
        ),
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    # boat_id é String para compatibilidade com códigos de produto ERP
    boat_id: Mapped[str] = mapped_column(String(80), nullable=False)
    # score combinado: mean(margem_norm, throughput_norm, 1-defect_rate, 1-lead_time_norm)
    potential_score: Mapped[float] = mapped_column(Float(), nullable=False)
    # somatório de vendas históricas (EUR) — alimentado pela tabela de pricing/orders
    revenue_eur_lifetime: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2), nullable=False, server_default="0"
    )
    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
