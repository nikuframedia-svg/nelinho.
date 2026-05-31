"""
ProdPlan ONE — Modelos de aprendizagem plan-vs-actual (Q.113.A/B)
=================================================================

PlanExecutionObserved  — registo par planeado/real por (commit, of, phase).
PhaseDurationCalibration — p50/p95 calibrados por (tenant, modelo, phase).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Float, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase, Base


class PlanExecutionObserved(TenantBase):
    """Par planeado/observado por (commit, of_id, phase_id).

    Preenchido pelo job `capture_plan_execution` que corre às 04:00 UTC,
    após o sync ERP incremental. Idempotente: UPSERT via UNIQUE.
    """

    __tablename__ = "plan_execution_observed"
    __table_args__ = (
        # Idempotência do writer (Q.134.A3a): UPSERT por (tenant, commit, of,
        # fase). UNIQUE parcial — só linhas com schedule_commit_id NOT NULL.
        Index(
            "uq_plan_exec_commit_of_phase",
            "tenant_id",
            "schedule_commit_id",
            "of_id",
            "phase_id",
            unique=True,
            postgresql_where="schedule_commit_id IS NOT NULL",
        ),
        Index("ix_plan_exec_tenant_captured", "tenant_id", "captured_at"),
        Index(
            "ix_plan_exec_modelo_phase_obs",
            "modelo",
            "phase_id",
            postgresql_where="observed_duration_min IS NOT NULL",
        ),
        {"schema": "plan"},
    )

    schedule_commit_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    of_id: Mapped[str] = mapped_column(Text, nullable=False)
    phase_id: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    planned_start_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    planned_end_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    planned_duration_min: Mapped[float] = mapped_column(Float, nullable=False)

    observed_start_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    observed_end_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    observed_duration_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deviation_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    captured_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<PlanExecutionObserved of={self.of_id} phase={self.phase_id} "
            f"dev_pct={self.deviation_pct}>"
        )


class PhaseDurationCalibration(Base):
    """p50/p95 calibrados de duração por (tenant, modelo, phase_id).

    PK composta (tenant_id, modelo, phase_id) — UPSERT actualiza no lugar.
    Sem tenant_id como FK porque TenantBase assume UUID PK; aqui o PK é composto.
    """

    __tablename__ = "phase_duration_calibration"
    __table_args__ = {"schema": "plan"}

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, primary_key=True
    )
    modelo: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    phase_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)

    p50_min: Mapped[float] = mapped_column(Float, nullable=False)
    p95_min: Mapped[float] = mapped_column(Float, nullable=False)
    n_obs: Mapped[int] = mapped_column(Integer, nullable=False)

    calibrated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    prior_p50_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Q.134.A3b — desvio sistemático aplicado (AVG plan-vs-real), clamp ±_DEV_CAP.
    # NULL = sem dados de execução suficientes → p50/p95 = só a mediana (como antes).
    systematic_deviation_pct: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<PhaseDurationCalibration modelo={self.modelo} "
            f"phase={self.phase_id} p50={self.p50_min:.1f}min n={self.n_obs}>"
        )
