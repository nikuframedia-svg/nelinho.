"""Q.155.B — PhasePreferredOperator: "melhores operadores" por fase (MANUAL).

Lista curada pelo gestor (página "Melhores por fase"): por cada fase, os
operadores preferidos (ordenados por `rank`), identificados por `employee_code`
(= E_ID do ERP — a MESMA identidade que o decoder do CPO usa em `workers_for`/
`_pick_workers`). É uma PREFERÊNCIA, não capacidade: não alarga o skill_matrix
(axioma 5). A afinidade histórica só serve de SUGESTÃO para semear esta lista.

PK composta (tenant_id, phase_id, employee_code). RLS por tenant.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class PhasePreferredOperator(Base):
    """Operador preferido (curado) para uma fase. rank 1 = mais preferido."""

    __tablename__ = "phase_preferred_operator"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id", "phase_id", "employee_code",
            name="pk_phase_preferred_operator",
        ),
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    # phase_id String p/ compatibilidade com routing_template_phase / FP_ID.
    phase_id: Mapped[str] = mapped_column(String(80), nullable=False)
    # employee_code = E_ID do ERP (a identidade do operador no decoder).
    employee_code: Mapped[str] = mapped_column(String(80), nullable=False)
    rank: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="1")
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    set_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
