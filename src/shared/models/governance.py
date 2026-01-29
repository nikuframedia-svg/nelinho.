"""
ProdPlan ONE - Governance Models
==================================

Database models for decision management, approval workflows, and audit trail.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import String, ForeignKey, JSON, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import TenantBase, Base


class DecisionStatus(str, Enum):
    """Decision workflow status."""
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"


class ApprovalStatus(str, Enum):
    """Approval status for individual approvers."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SharedDecisionRun(TenantBase):
    """
    Shared Decision Run - Tracks a decision through its lifecycle.
    
    NOTE: Renamed from DecisionRun to avoid SQLAlchemy conflict with
    governance.models.DecisionRun
    
    Represents a decision proposal with:
    - Action to be taken (e.g., "INCREASE_SS", "ADJUST_PRICE")
    - Target entity (e.g., SKU ID, product ID)
    - Before/after state snapshots
    - Approval workflow
    - Execution and rollback tracking
    """
    
    __tablename__ = "shared_decision_runs"
    __table_args__ = {"schema": "shared"}
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "INCREASE_SS", "ADJUST_PRICE", etc.
    target: Mapped[str] = mapped_column(String(255), nullable=False)  # SKU ID, product ID, etc.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DecisionStatus.PROPOSED.value)
    
    # Sandbox preview results
    sandbox_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # State snapshots
    before_state: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    after_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Workflow tracking
    proposed_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    approvals: Mapped[list["DecisionApproval"]] = relationship(
        "DecisionApproval",
        back_populates="decision",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<SharedDecisionRun(id={self.id}, title={self.title}, status={self.status})>"


class DecisionApproval(Base):
    """
    Decision Approval - Individual approver record for a decision.
    
    Tracks approval workflow with:
    - Link to decision
    - Approver identity
    - Approval status and comments
    - Timestamps
    """
    
    __tablename__ = "decision_approvals"
    __table_args__ = {"schema": "shared"}
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    decision_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shared.shared_decision_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approver_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ApprovalStatus.PENDING.value,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    decision: Mapped["SharedDecisionRun"] = relationship(
        "SharedDecisionRun",
        back_populates="approvals",
    )
    
    def __repr__(self) -> str:
        return f"<DecisionApproval(id={self.id}, decision_id={self.decision_id}, status={self.status})>"


