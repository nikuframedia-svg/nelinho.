"""
Governance Models — Decision Ledger and Approvals
==================================================

Implements C5 contract requirements:
- DecisionRun immutable ledger
- Approval workflow with SoD
- Policy versioning
- Audit trail with hash chain
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    Index,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import TenantBase, Base


# ============================================================================
# ENUMS
# ============================================================================

class AutonomyLevel(str, Enum):
    """
    Decision autonomy levels (L1-L5).
    
    Higher levels require more approval and governance.
    """
    L1 = "L1"  # Informational only, no action
    L2 = "L2"  # Suggest, user must approve
    L3 = "L3"  # Auto-execute low risk, user approves high risk
    L4 = "L4"  # Auto-execute most, user approves critical
    L5 = "L5"  # Full autonomy (requires extensive testing/validation)


class DecisionStatus(str, Enum):
    """Status of a decision run."""
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalAction(str, Enum):
    """Approval actions."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


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
    """Request to approve/reject a decision."""
    action: ApprovalAction
    reason: str = Field(..., min_length=10)
    conditions: Optional[List[str]] = None


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


# ============================================================================
# DEFAULT POLICIES
# ============================================================================

DEFAULT_POLICIES = [
    {
        "decision_type": "scenario_publish",
        "autonomy_level": AutonomyLevel.L2.value,
        "requires_approval": True,
        "required_approvers": 1,
        "requires_different_approver": True,
        "requires_sandbox": True,
        "requires_canary": False,
        "description": "Publishing a scenario to production",
    },
    {
        "decision_type": "capacity_adjustment",
        "autonomy_level": AutonomyLevel.L3.value,
        "requires_approval": True,
        "required_approvers": 1,
        "requires_different_approver": True,
        "auto_approve_if_low_risk": True,
        "max_impact_threshold": 5.0,
        "requires_sandbox": True,
        "requires_canary": False,
        "description": "Adjusting capacity parameters",
    },
    {
        "decision_type": "standard_time_update",
        "autonomy_level": AutonomyLevel.L2.value,
        "requires_approval": True,
        "required_approvers": 2,
        "requires_different_approver": True,
        "requires_sandbox": True,
        "requires_canary": True,
        "canary_percentage": 10,
        "description": "Updating standard times (affects cost calculations)",
    },
    {
        "decision_type": "data_repair",
        "autonomy_level": AutonomyLevel.L3.value,
        "requires_approval": True,
        "required_approvers": 1,
        "requires_different_approver": False,
        "requires_sandbox": False,
        "requires_canary": False,
        "description": "Repairing data quality issues",
    },
    {
        "decision_type": "kill_switch",
        "autonomy_level": AutonomyLevel.L5.value,
        "requires_approval": False,
        "required_approvers": 0,
        "requires_different_approver": False,
        "requires_sandbox": False,
        "requires_canary": False,
        "description": "Emergency kill switch (immediate effect)",
    },
]





