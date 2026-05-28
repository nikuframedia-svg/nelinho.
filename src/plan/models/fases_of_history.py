"""Q.115.A.08 — FasesOfHistory: historico de fases de OF.

Alta cardinalidade (milions de linhas ERP historico). BIGINT PK autoincrement.
duration_min calculada pela app (nao GENERATED ALWAYS AS porque fase_fim
e nullable — Postgres nao aceita).

RLS em q115_a08_fases_of_history.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class FasesOfHistory(Base):
    """Historico de execucao de fases por OF. Feed do ML world model."""

    __tablename__ = "fases_of_history"
    __table_args__ = (
        Index(
            "ix_plan_fases_of_history_tenant_of_inicio",
            "tenant_id", "of_id", "fase_inicio",
        ),
        {"schema": "plan"},
    )

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    of_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    phase_id: Mapped[str] = mapped_column(String(80), nullable=False)
    fase_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fase_fim: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Calculado pela app: EXTRACT(EPOCH FROM (fase_fim - fase_inicio))/60
    duration_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    worker_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    mold_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source_run_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
