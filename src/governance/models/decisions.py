"""Decision ledger SQLA models + Pydantic schemas + DEFAULT_POLICIES.

Q.67.6.B5 — split out of legacy 936L ``src/governance/models.py``. Holds:

* :class:`DecisionPolicy` — policy definitions (autonomy + approval rules).
* :class:`DecisionRun` — immutable ledger entry (the audit anchor).
* :class:`Approval` — per-approver vote on a DecisionRun.
* :class:`DecisionProposal` / :class:`ApprovalRequest` — Pydantic request bodies.
* :class:`DecisionRunResponse` — Pydantic response shape.
* :data:`DEFAULT_POLICIES` — bootstrap seed (kill_switch, scenario_publish, …).

All schema metadata (table names, indices, FKs, column flags) is pinned by
``tests/governance/test_api_models_characterization_q67.py``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import TenantBase

from .enums import (
    ApprovalAction,
    AutonomyLevel,
    DecisionStatus,
    RejectionCategory,
)
# DEFAULT_POLICIES re-exported from .policies so existing
# ``from src.governance.models.decisions import DEFAULT_POLICIES`` (if any)
# keeps working. The canonical location is now ``models/policies.py``.
from .policies import DEFAULT_POLICIES as DEFAULT_POLICIES  # re-export


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class DecisionProposal(BaseModel):
    """Request to propose a new decision."""
    decision_type: str
    title: str
    description: Optional[str] = None
    action_data: Dict[str, Any] = Field(default_factory=dict)
    expected_impact: Optional[Dict[str, Any]] = None
    risk_level: str = "medium"  # low, medium, high, critical
    scenario_id: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    """Request to approve/reject a decision.

    Sprint Q.2 — `rejection_category` is required when `action == REJECT`
    (validated in `src.governance.api.approve_decision`); ignored for
    APPROVE / REQUEST_CHANGES.
    """
    action: ApprovalAction
    reason: str = Field(..., min_length=10)
    conditions: Optional[List[str]] = None
    rejection_category: Optional[RejectionCategory] = None


class DecisionRunResponse(BaseModel):
    """Response for a decision run."""
    id: str
    decision_type: str
    title: str
    status: DecisionStatus
    autonomy_level: AutonomyLevel
    proposed_at: datetime
    proposed_by: str
    approvals: List[Dict[str, Any]] = Field(default_factory=list)
    audit_hash: str

    class Config:
        from_attributes = True


# ============================================================================
# DATABASE MODELS
# ============================================================================

class DecisionPolicy(TenantBase):
    """
    Policy definitions for decision types.

    Defines autonomy level, required approvals, and constraints.
    """

    __tablename__ = "decision_policy"
    __table_args__ = (
        Index("ix_decision_policy_type", "decision_type"),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    decision_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True
    )

    autonomy_level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=AutonomyLevel.L2.value
    )

    # Approval requirements
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    required_approvers: Mapped[int] = mapped_column(
        Integer,
        default=1,
        doc="Number of approvers required"
    )

    requires_different_approver: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        doc="SoD: Approver must be different from proposer"
    )

    # Risk thresholds
    auto_approve_if_low_risk: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    max_impact_threshold: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        doc="Max expected impact for auto-approval"
    )

    # Execution constraints
    requires_sandbox: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    requires_canary: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    canary_percentage: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Percentage for canary rollout"
    )

    # Policy metadata
    version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class DecisionRun(TenantBase):
    """
    Immutable ledger entry for a decision.

    This is the core audit record. Once created, it should
    never be modified (only status transitions via new records).
    """

    __tablename__ = "decision_run"
    __table_args__ = (
        Index("ix_decision_run_type", "decision_type"),
        Index("ix_decision_run_status", "status"),
        Index("ix_decision_run_proposed_at", "proposed_at"),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # Decision identification
    decision_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=DecisionStatus.PROPOSED.value
    )

    # Policy reference
    policy_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True
    )

    policy_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0"
    )

    autonomy_level: Mapped[str] = mapped_column(
        String(10),
        default=AutonomyLevel.L2.value
    )

    # Action data
    action_data: Mapped[Dict] = mapped_column(
        JSONB,
        default=dict
    )

    expected_impact: Mapped[Optional[Dict]] = mapped_column(
        JSONB,
        nullable=True
    )

    actual_impact: Mapped[Optional[Dict]] = mapped_column(
        JSONB,
        nullable=True
    )

    # Risk assessment
    risk_level: Mapped[str] = mapped_column(
        String(20),
        default="medium"
    )

    # Evidence and scenario reference
    scenario_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True
    )

    evidence_refs: Mapped[List] = mapped_column(
        JSONB,
        default=list
    )

    # Hashes for audit chain
    input_snapshot_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )

    outcome_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True
    )

    prev_decision_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        doc="Previous decision in chain (for related decisions)"
    )

    prev_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Hash of previous decision (for chain integrity)"
    )

    audit_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA256(decision_id || policy_version || input_hash || outcome_hash || prev_hash)"
    )

    # Sprint Q.12 Onda 1.5 — when ``modify_payload`` rewrites an
    # earlier decision's input_hash, every decision proposed AFTER it
    # is left holding a ``prev_hash`` that no longer points at a
    # source-of-truth row. We surface that explicitly here so audit
    # tooling can filter by it. Default false; set true by
    # :meth:`GovernanceService.modify_payload` for descendants.
    chain_invalidated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="True iff a later modify_payload broke this row's prev_hash link.",
    )

    chain_invalidated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    chain_invalidated_by_modify_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        doc="ID of the decision whose modify_payload broke this chain link.",
    )

    # Timestamps
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    proposed_by: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    executed_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    rolled_back_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    rollback_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    approvals: Mapped[List["Approval"]] = relationship(
        "Approval",
        back_populates="decision_run",
        cascade="all, delete-orphan"
    )

    @staticmethod
    def calculate_audit_hash(
        decision_id: UUID,
        policy_version: str,
        input_hash: Optional[str],
        outcome_hash: Optional[str],
        prev_hash: Optional[str],
    ) -> str:
        """Calculate audit hash for integrity verification."""
        data = f"{decision_id}|{policy_version}|{input_hash or ''}|{outcome_hash or ''}|{prev_hash or ''}"
        return hashlib.sha256(data.encode()).hexdigest()


class Approval(TenantBase):
    """
    Approval record for a decision.

    Tracks who approved/rejected and when.
    """

    __tablename__ = "approval"
    __table_args__ = (
        Index("ix_approval_decision", "decision_run_id"),
        Index("ix_approval_user", "approved_by"),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    decision_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("governance.decision_run.id"),
        nullable=False
    )

    # Approval details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    approved_by: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    conditions: Mapped[Optional[List]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Conditions for conditional approval"
    )

    # Sprint Q.2 — categorical rejection signal (Camada 1 learner feature).
    # Nullable: only populated when `action == REJECT`.
    rejection_category: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="Required when action=REJECT — see RejectionCategory enum",
    )

    # Role/authority
    approver_role: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    # Relationship
    decision_run: Mapped["DecisionRun"] = relationship(
        "DecisionRun",
        back_populates="approvals"
    )


__all__ = [
    "DecisionProposal",
    "ApprovalRequest",
    "DecisionRunResponse",
    "DecisionPolicy",
    "DecisionRun",
    "Approval",
    "DEFAULT_POLICIES",
]
