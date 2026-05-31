"""Q.115.A.10 — DriftEvent: deteccao de drift de modelos ML.

Quando o sistema detecta drift (KS, PSI, AUC delta, WMAPE delta), regista
aqui. Permite alertas automaticos e historico de saude dos modelos.

Schema: ml (criado em q115_a10_ml_drift_event).
RLS em q115_a10_ml_drift_event.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class DriftEvent(Base):
    """Evento de drift detectado num modelo ML."""

    __tablename__ = "drift_event"
    __table_args__ = (
        CheckConstraint(
            "metric IN ('ks_stat','psi','auc_delta','wmape_delta')",
            name="metric",
        ),
        CheckConstraint(
            "severity IN ('warn','critical')",
            name="severity",
        ),
        {"schema": "ml"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # NULL quando e score-level drift (nao especifico a uma feature)
    feature_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float(), nullable=False)
    threshold: Mapped[float] = mapped_column(Float(), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # FK soft para governance.decision_runs
    decision_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
