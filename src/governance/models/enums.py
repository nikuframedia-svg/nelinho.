"""Governance enums — value pins for decision lifecycle, autonomy, rejection,
preference rule lifecycle, causal discovery, rule firing.

Q.67.6.B5 — split out of legacy 936L ``src/governance/models.py``. Pure value
enums live here so the SQLA models / Pydantic schemas can import them without
pulling in the whole module surface.

Member names + values are pinned by ``tests/governance/test_api_models_
characterization_q67.py`` — do not rename without updating the characterization
snapshots.
"""

from __future__ import annotations

from enum import Enum


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


class CausalDiscoveryStatus(str, Enum):
    """Lifecycle of a discovery run row — same review pattern as PreferenceRule."""

    PENDING = "pending"      # PCMCI+ produced candidates, awaiting human review
    APPROVED = "approved"    # operator accepted at least one edge into NELO_DAG
    REJECTED = "rejected"    # operator dismissed all candidates


class RuleFiringOutcome(str, Enum):
    """Lifecycle of a rule firing — operator decisions update this in place."""

    PROPOSED = "proposed"          # detector fired; awaiting operator review
    ACCEPTED = "accepted"          # operator approved the suggestion
    REJECTED = "rejected"          # operator dismissed it
    EXPIRED = "expired"            # window passed without action
    SUPERSEDED = "superseded"      # newer firing replaced this one


__all__ = [
    "AutonomyLevel",
    "DecisionStatus",
    "ApprovalAction",
    "RejectionCategory",
    "PreferenceRuleType",
    "PreferenceRuleStatus",
    "CausalDiscoveryStatus",
    "RuleFiringOutcome",
]
