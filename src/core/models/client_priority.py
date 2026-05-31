"""Q.115.A.03 — ClientPriority: prioridade de cliente.

FK soft para core.customers — sem FK constraint declarada para nao bloquear
gestao de clientes ERP. Tenant-scoped. RLS em q115_a03_client_priority.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class ClientPriority(Base):
    """Prioridade 1-5 de um cliente. PK e o client_id (UUID do cliente)."""

    __tablename__ = "client_priority"
    __table_args__ = (
        CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="range",
        ),
        {"schema": "core"},
    )

    # FK soft para core.customers.id — sem ForeignKey declarado aqui
    # para nao bloquear gestao de clientes ERP.
    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(SmallInteger(), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[str] = mapped_column(String(80), nullable=False)
