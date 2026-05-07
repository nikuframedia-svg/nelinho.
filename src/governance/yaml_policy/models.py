"""DB models for Q.17.C — tenant_rule storage + revision audit.

Two tables:

- ``governance.yaml_policy_rule`` — current state of each rule.
  One row per ``rule.id`` per tenant. Status transitions (proposed →
  approved → active → suspended/rolled_back) update this row in-place.

- ``governance.yaml_policy_rule_revision`` — append-only audit trail.
  One row per state-changing event (proposed, approved, rejected,
  modified, suspended, rolled_back). Allows full forensic replay.

The runtime engine (Q.17.D) reads ``yaml_policy_rule`` filtered by
``status='active'`` and dispatches actions when triggers match.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class RuleLifecycleStatus(str, Enum):
    """Workflow states for a tenant rule.

    Mirrors :class:`src.governance.yaml_policy.rule_schema.RuleStatus`
    but persisted server-side. Transitions are enforced by the service
    layer; the DB enum is the canonical source of allowed values.
    """

    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class RuleRevisionAction(str, Enum):
    """The discrete state-changing event a revision row records."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    SUSPENDED = "suspended"
    ROLLED_BACK = "rolled_back"
    REACTIVATED = "reactivated"


class TenantRule(TenantBase):
    """Current state of a single declarative rule for a tenant.

    The ``payload`` JSONB column stores the full validated Rule shape
    (per :class:`src.governance.yaml_policy.rule_schema.Rule`). The
    runtime engine deserialises ``payload`` back through Pydantic on
    each load — so DB-level corruption surfaces as a validation error
    immediately rather than mid-dispatch.
    """

    __tablename__ = "yaml_policy_rule"
    __table_args__ = (
        # Two rules can share an id across tenants but never within one.
        Index(
            "uq_yaml_policy_rule_tenant_rule_id",
            "tenant_id", "rule_id",
            unique=True,
        ),
        Index("ix_yaml_policy_rule_status", "tenant_id", "status"),
        Index("ix_yaml_policy_rule_event_type", "tenant_id", "event_type"),
        {"schema": "governance"},
    )

    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RuleLifecycleStatus] = mapped_column(
        SQLEnum(RuleLifecycleStatus, name="yaml_policy_rule_status"),
        nullable=False,
        default=RuleLifecycleStatus.PROPOSED,
    )
    # Denormalised for fast filtering by event_type without parsing payload.
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    """Full Rule.model_dump() — validated on read via Pydantic."""

    proposed_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fire_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    nl_source: Mapped[str | None] = mapped_column(Text)
    """The original natural-language input from the user; kept for audit."""


class TenantRuleRevision(TenantBase):
    """Append-only audit row for every state-changing event on a rule.

    Whether a rule is approved, modified, suspended, or rolled back, a
    new row lands here. Forensic replay reconstructs the lifecycle.
    """

    __tablename__ = "yaml_policy_rule_revision"
    __table_args__ = (
        Index("ix_yaml_policy_rule_revision_rule", "tenant_id", "rule_db_id"),
        Index("ix_yaml_policy_rule_revision_at", "tenant_id", "created_at"),
        {"schema": "governance"},
    )

    rule_db_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("governance.yaml_policy_rule.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    """Denormalised business id — survives even if the parent row is deleted."""

    action: Mapped[RuleRevisionAction] = mapped_column(
        SQLEnum(RuleRevisionAction, name="yaml_policy_rule_revision_action"),
        nullable=False,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    payload_before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    payload_after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    nl_source: Mapped[str | None] = mapped_column(Text)


def utcnow() -> datetime:
    """Helper — DB columns are timezone-aware; never use naive ``datetime.utcnow()``."""
    return datetime.now(timezone.utc)
