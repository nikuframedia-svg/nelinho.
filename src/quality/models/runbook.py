"""Q.115.A.05 + A.06 — Runbook e ErrorTypeRunbookLink.

Runbook: passos em Markdown para resolver um tipo de erro de producao.
ErrorTypeRunbookLink: liga um error_code a um ou mais runbooks (por prioridade).

RLS em q115_a05_runbook e q115_a06_error_type_runbook_link.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.shared.database import Base


class Runbook(Base):
    """Runbook de resolucao de erros de producao."""

    __tablename__ = "runbook"
    __table_args__ = (
        CheckConstraint(
            "source IN ('learned','manual')",
            name="source",
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="confidence",
        ),
        {"schema": "quality"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    steps_md: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(
        Float(), nullable=False, server_default="0"
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    audit_trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class ErrorTypeRunbookLink(Base):
    """Ligacao N:M entre error_code e runbooks, com prioridade."""

    __tablename__ = "error_type_runbook_link"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id", "error_code", "runbook_id",
            name="pk_error_type_runbook_link",
        ),
        {"schema": "quality"},
    )

    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    runbook_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("quality.runbook.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(
        SmallInteger(), nullable=False, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
