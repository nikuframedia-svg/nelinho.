"""Q.153.C1 — PlanExclusion: excluir/adiar um barco do plano automático.

"Tirar um barco" do planeamento = excluí-lo do CPO de forma REVERSÍVEL.
A presença da linha significa "excluído/adiado"; o DELETE repõe-o. O barco
continua no ERP — nunca tocamos em `factory_raw`.

PK composta (tenant_id, order_id). `order_id` é o OF_ID da NELO ERP (a mesma
string usada em `open_orders[].order_id`) — Varchar(80) chega. Sem
ForeignKey, em paridade com BoatBoost (Q.116.D): não bloqueamos OFs
históricas que possam não estar em master_data do nelinho.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class PlanExclusion(Base):
    """Barco excluído/adiado do plano. PK = (tenant_id, order_id)."""

    __tablename__ = "plan_exclusion"
    __table_args__ = ({"schema": "plan"},)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(
        String(80), primary_key=True, nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    excluded_by: Mapped[str] = mapped_column(String(80), nullable=False)
    excluded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
