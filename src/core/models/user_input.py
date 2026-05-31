"""Q.115.A.01 — UserInput: pedidos de evolucao do utilizador.

Tenant-scoped. RLS em q115_a01_user_input.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class UserInput(Base):
    """Pedido de evolucao do utilizador (nova feature, correcao, melhoria)."""

    __tablename__ = "user_input"
    __table_args__ = (
        CheckConstraint("char_length(what) >= 10", name="what_min"),
        CheckConstraint(
            "char_length(economic_reason) >= 30",
            name="economic_reason_min",
        ),
        CheckConstraint(
            "where_page IN ('decisoes','overall','llm','configuracoes')",
            name="where_page",
        ),
        CheckConstraint(
            "status IN ('pending','in_progress','done','rejected')",
            name="status",
        ),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    author: Mapped[str] = mapped_column(String(80), nullable=False)
    what: Mapped[str] = mapped_column(Text, nullable=False)
    where_page: Mapped[str] = mapped_column(String(20), nullable=False)
    economic_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    result_pr_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    claude_run_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    audit_trace_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
