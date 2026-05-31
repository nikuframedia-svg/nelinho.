"""Q.116.C — OrderBoost: boost manual (0-100) por encomenda.

PK e o work_order_id (INTEGER, legacy_id da ProductionOrder = ID ERP, NAO a
UUID interna). FK soft para plan.production_order — sem ForeignKey declarado
aqui para nao bloquear gestao de encomendas historicas.

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


class OrderBoost(Base):
    """Boost manual de 0-100 sobre uma encomenda. PK = work_order_id (INT)."""

    __tablename__ = "order_boost"
    __table_args__ = (
        CheckConstraint(
            "boost BETWEEN 0 AND 100",
            name="ck_order_boost_range",
        ),
        {"schema": "plan"},
    )

    # FK soft para plan.production_order.legacy_id (ID ERP, INTEGER).
    work_order_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    boost: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(80), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
