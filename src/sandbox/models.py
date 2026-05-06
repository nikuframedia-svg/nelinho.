"""
ProdPlan ONE - Sandbox Models
==============================

SQLAlchemy models for persisting sandbox scenarios.

Sprint Q.10 Fase B — replaces the in-memory ``sandbox_store`` dict
in ``src/sandbox/api.py``. Storage moved to ``sandbox.sandbox_scenarios``
table (migration 030).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class SandboxScenarioStatus(str, enum.Enum):
    DRAFT = "draft"
    SIMULATING = "simulating"
    SIMULATED = "simulated"
    PUBLISHED = "published"


class SandboxScenario(TenantBase):
    """Sandbox scenario — a "what-if" simulation of a suggestion's
    impact, isolated per tenant. ``publish`` creates a real
    ``SharedDecisionRun`` for the approval workflow."""

    __tablename__ = "sandbox_scenarios"
    __table_args__ = (
        Index("ix_sandbox_scenarios_tenant_status", "tenant_id", "status"),
        Index("ix_sandbox_scenarios_suggestion", "suggestion_id"),
        {"schema": "sandbox"},
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SandboxScenarioStatus.DRAFT.value,
    )

    # Optional link to the improve.ImprovementSuggestion that seeded
    # the sandbox. String (not FK) because the improve module may live
    # in a different schema and we want loose coupling.
    suggestion_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
    )

    # State snapshots — JSONB so we can iterate the schema without
    # hitting alembic for every metric.
    before_state: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    after_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True,
    )
    impact: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True,
    )

    # Audit / publish
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    decision_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="SharedDecisionRun.id created on publish",
    )

    # Sprint Q.12 Onda 3.1 — optimistic-lock counter. The service's
    # state-machine writes (DRAFT→SIMULATING, SIMULATING→SIMULATED)
    # use this as a CAS so two concurrent ``simulate`` calls can't
    # both progress past the status check. Bumped on every state
    # transition.
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )

    def __repr__(self) -> str:  # pragma: no cover — repr aid
        return f"<SandboxScenario id={self.id} status={self.status} v={self.version}>"
