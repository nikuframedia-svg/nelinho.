"""Q.115.X5 — Registo de encomendas canceladas (não escrevemos no ERP).

Quando uma encomenda de cliente é cancelada no nelinho, criamos uma row
aqui para rastreabilidade + trigger de replan. O ERP (MAR-KAYAKS) não é
alterado directamente — é responsabilidade de um operador humano.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


class EncomendaCancelled(Base):
    """Registo de cancelamento de encomenda de cliente."""

    __tablename__ = "encomendas_cancelled"
    __table_args__ = {"schema": "core"}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    encomenda_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    cancelled_by: Mapped[str] = mapped_column(String(255), nullable=False)
    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    audit_trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<EncomendaCancelled encomenda={self.encomenda_id} at={self.cancelled_at}>"
