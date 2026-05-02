"""
ProdPlan ONE - Improve Models
==============================

SQLAlchemy models for persisting improvement suggestions.

Sprint Q.10 Fase C — replaces the in-memory ``suggestions_store``
dict + ``PREDEFINED_SUGGESTIONS`` list. Suggestions live in
``improve.improvement_suggestions`` (migration 031). The 5
PREDEFINED entries become a per-tenant seed inserted on first
list when the table is empty.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class SuggestionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


class SuggestionSource(str, enum.Enum):
    SEED = "seed"  # imported from PREDEFINED_SUGGESTIONS on first use
    LLM_GENERATED = "llm_generated"  # built by ImproveService.generate_via_llm
    MANUAL = "manual"  # operator-entered (future)


class ImprovementSuggestion(TenantBase):
    """One improvement suggestion the operator can approve/reject and
    test in the sandbox."""

    __tablename__ = "improvement_suggestions"
    __table_args__ = (
        Index("ix_improve_suggestions_tenant_status", "tenant_id", "status"),
        Index("ix_improve_suggestions_domain", "tenant_id", "domain"),
        {"schema": "improve"},
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Domain bucket: oee | quality | supply | hr | other
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SuggestionStatus.PENDING.value,
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SuggestionSource.SEED.value,
    )

    estimated_impact: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
    )

    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImprovementSuggestion id={self.id} status={self.status}>"
