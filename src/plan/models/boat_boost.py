"""Q.116.D — BoatBoost: boost manual (0-100) por barco.

PK composta (tenant_id, boat_id). boat_id e a string usada no
MOVIMENTO/OF_FP da NELO ERP — Varchar(80) e suficiente.

Sem ForeignKey declarado: mantemos paridade com OrderBoost (Q.116.C) e
nao bloqueamos barcos historicos que possam nao estar em tabelas
master_data do nelinho.

Tenant-scoped por filtro explicito no endpoint via require_tenant_header.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class BoatBoost(Base):
    """Boost manual de 0-100 sobre um barco. PK = (tenant_id, boat_id)."""

    __tablename__ = "boat_boost"
    __table_args__ = (
        CheckConstraint(
            "boost BETWEEN 0 AND 100",
            name="ck_boat_boost_range",
        ),
        {"schema": "plan"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, nullable=False, index=True
    )
    boat_id: Mapped[str] = mapped_column(
        String(80), primary_key=True, nullable=False
    )
    boost: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(80), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
