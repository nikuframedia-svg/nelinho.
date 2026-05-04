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
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Numeric,
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
    # Sprint Q.12 Onda 2.1 — distinguishes "audit row written, domain
    # mutation skipped" from a fully-applied EXECUTED. The previous
    # advisory-mode fallback (handler returning ``no_session`` /
    # ``missing_id``) was silently treated as success; auditors saw
    # EXECUTED with no domain change and no warning. Reviewers can now
    # filter for this status to find decisions that need a real apply.
    EXECUTED_PARTIAL = "executed_partial"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalAction(str, Enum):
    """Approval actions."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


class RejectionCategory(str, Enum):
    """Sprint Q.2 — categorical signal that must accompany every rejection.

    The free-text `reason` keeps the operator's prose; this enum gives the
    Camada 1 learner a machine-readable feature so it can detect "user
    rejects on cost grounds 70% of the time" patterns automatically.
    """

    COST = "COST"
    QUALITY = "QUALITY"
    CUSTOMER = "CUSTOMER"
    CAPACITY = "CAPACITY"
    MOLD = "MOLD"
    WORKFORCE = "WORKFORCE"
    OTHER = "OTHER"


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


class KillSwitchActive(Base):
    """Sprint Q.12 Onda 2.2 — durable kill-switch state.

    One row per (tenant_id, scope) — activating an already-active scope
    is idempotent (the existing row is updated, not duplicated). When
    revoked we stamp ``deactivated_at`` instead of deleting so the
    audit trail survives. Handlers in :mod:`src.governance.action_executor`
    consult :func:`is_kill_switch_active` before mutating domain state.

    Lives on :class:`Base` (not :class:`TenantBase`) because the table
    is scoped per row (composite PK already includes tenant_id) and we
    want explicit composite-key joins rather than the implicit tenant
    filter ``TenantBase`` adds elsewhere.
    """

    __tablename__ = "kill_switch_active"
    __table_args__ = (
        {"schema": "governance"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        nullable=False,
        doc="Free-form scope identifier (e.g. 'all', 'decision_type:reschedule_order').",
    )
    decision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        doc="DecisionRun.id that activated this scope (audit anchor).",
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    activated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deactivated_by: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )


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
    {
        "decision_type": "model_promotion",
        "autonomy_level": AutonomyLevel.L3.value,
        "requires_approval": True,
        "required_approvers": 1,
        "requires_different_approver": True,
        "auto_approve_if_low_risk": True,   # risk_level="low" -> auto
        "max_impact_threshold": 5.0,
        "requires_sandbox": False,
        "requires_canary": False,
        "description": "Promote a trained ML model to active (Sprint G)",
    },
]


# ============================================================================
# Sprint C 2.1 — PreferenceRule (Camada 1 aprendizagem)
# ============================================================================


class PreferenceRuleType(str, Enum):
    """Categories of patterns the PreferenceRuleDetector emits.

    Each type has a distinct `predicate` shape so the scheduler can
    decide at plan-time whether to respect the rule.
    """

    TEMPORAL_BLOCK = "temporal_block"          # "don't touch X on Fridays"
    TRADEOFF_PREFERENCE = "tradeoff_preference"  # "prefer less setup over +€/day"
    OPERATOR_AFFINITY = "operator_affinity"    # "Paulo always on K4 laminagem"
    PHASE_THRESHOLD = "phase_threshold"        # "never < 18 pintores"
    # Sprint Q.3 — operator override on quality_score / skill toggle in the
    # EmployeesPage UI. Predicate carries `{employee_id, field, ...}` so
    # the adaptive-weights trainer can treat the human override as a hard
    # signal next pass.
    WORKFORCE_OVERRIDE = "workforce_override"


class PreferenceRuleStatus(str, Enum):
    """Lifecycle of a detected rule — needs human confirmation before
    the scheduler applies it (avoids learning noise / false positives).
    """

    DETECTED = "detected"    # just mined; awaiting operator review
    CONFIRMED = "confirmed"  # operator approved — scheduler honours it
    REJECTED = "rejected"    # operator dismissed — detector must stop re-raising


class PreferenceRule(TenantBase):
    """A pattern learned from `ScheduleCommit.rejected_alternatives`.

    The table is the first tangible moat (§50 of the blueprint): every
    time the manager rejects 5+ plans that share a structural signal
    (e.g. "Laminagem on Fridays"), the detector inserts a DETECTED row
    and the frontend asks the manager to confirm, reject or edit it.

    `predicate` is JSONB so each rule type can carry its own shape — the
    detector + the scheduler are the only consumers and they know the
    schema per type. Keep the column generic so we don't migrate the
    DB every time a new detector is added.
    """

    __tablename__ = "preference_rule"
    __table_args__ = (
        Index(
            "ix_preference_rule_tenant_status",
            "tenant_id", "status",
        ),
        Index(
            "ix_preference_rule_tenant_type",
            "tenant_id", "type",
        ),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )

    type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    predicate: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False,
        default=PreferenceRuleStatus.DETECTED.value,
    )
    detected_from_commits: Mapped[List[str]] = mapped_column(
        JSONB, nullable=False, default=list,
    )

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    confirmed_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True,
    )
    # Sprint E.3 — free-text operator feedback captured at confirm OR
    # reject time. Always optional on confirm; the API requires it on
    # reject so the audit trail has a human reason ("detector overfit on
    # a 2-week vacation gap", "rule is real but belongs to phase X").
    review_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
    )


# ============================================================================
# CAUSAL DISCOVERY (Sprint Q.13.D D.2)
# ============================================================================


class CausalDiscoveryStatus(str, Enum):
    """Lifecycle of a discovery run row — same review pattern as PreferenceRule."""

    PENDING = "pending"      # PCMCI+ produced candidates, awaiting human review
    APPROVED = "approved"    # operator accepted at least one edge into NELO_DAG
    REJECTED = "rejected"    # operator dismissed all candidates


class CausalDiscoveryReport(TenantBase):
    """One PCMCI+ run's output, persisted for human review.

    Sprint Q.13.D D.2 — closes the discovery side of Camada 4. The job
    that creates these rows is the weekly causal-discovery cron in
    :mod:`src.shared.scheduler`. Each row carries the candidate edges
    plus the metadata an operator needs to decide whether to fold them
    into :data:`src.copilot.causal.nelo_dag.ALL_NODES` (the SCM is an
    engineering artefact, not a stats lottery — see discovery module
    docstring).
    """

    __tablename__ = "causal_discovery_report"
    __table_args__ = (
        Index(
            "ix_causal_discovery_tenant_status",
            "tenant_id", "review_status",
        ),
        Index(
            "ix_causal_discovery_discovered_at",
            "discovered_at",
        ),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    engine: Mapped[str] = mapped_column(
        String(64), nullable=False, default="tigramite-pcmci+",
    )

    # "ok" / "degraded" / "unavailable" — mirrors DiscoveryReport.status.
    run_status: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tau_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nodes_examined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # List of DiscoveredEdge.to_json() dicts.
    candidate_edges: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list,
    )

    # Review state.
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False,
        default=CausalDiscoveryStatus.PENDING.value,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================================
# RULE FIRING LOG (Sprint Q.14.A)
# ============================================================================


class RuleFiringOutcome(str, Enum):
    """Lifecycle of a rule firing — operator decisions update this in place."""

    PROPOSED = "proposed"          # detector fired; awaiting operator review
    ACCEPTED = "accepted"          # operator approved the suggestion
    REJECTED = "rejected"          # operator dismissed it
    EXPIRED = "expired"            # window passed without action
    SUPERSEDED = "superseded"      # newer firing replaced this one


class RuleFiring(TenantBase):
    """One row per rule trigger — the audit substrate for *why* a
    suggestion / alert appeared.

    Sprint Q.14.A — closes the *"why did the system suggest moving
    the batch 3 weeks ago?"* gap. The 16 deterministic + LLM detectors
    today fire silently; this table captures the trigger payload that
    caused the fire and the rule output that was produced, so
    forensics is a SQL query instead of `git blame` + reading detector
    source.

    ``dedupe_key`` collapses repeated firings of the same underlying
    problem (e.g. "batch B-1 has 3 unassigned boats" reported every
    15 min by the alerts engine) into a single row whose
    ``fire_count`` + ``last_fired_at`` track recurrence. A new row is
    only created when the dedupe lookup misses or the previous row's
    ``outcome`` is terminal.

    ``variant_id`` is forward-look for the A/B framework (Q.14.C);
    today it stays NULL. ``correlation_id`` ties related decisions
    (e.g. one CPO solve → 5 transport suggestions all sharing the
    correlation_id of the parent commit).
    """

    __tablename__ = "rule_firing"
    __table_args__ = (
        Index(
            "ix_rule_firing_tenant_rule_fired",
            "tenant_id", "rule_id", "fired_at",
        ),
        Index(
            "ix_rule_firing_tenant_dedupe_fired",
            "tenant_id", "dedupe_key", "fired_at",
        ),
        Index(
            "ix_rule_firing_outcome_fired",
            "outcome", "fired_at",
        ),
        {"schema": "governance"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )

    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    variant_id: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True,
    )

    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    trigger_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    rule_output: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )

    correlation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True,
    )
    dedupe_key: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
    )

    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False,
        default=RuleFiringOutcome.PROPOSED.value,
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    accepted_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    fire_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
    )
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
