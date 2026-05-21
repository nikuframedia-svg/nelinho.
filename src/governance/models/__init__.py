"""
Governance Models — Decision Ledger and Approvals
==================================================

Implements C5 contract requirements:
- DecisionRun immutable ledger
- Approval workflow with SoD
- Policy versioning
- Audit trail with hash chain

Q.67.6.B5 — this used to be a single 936L module. It is now a package split
into three files by concern:

* :mod:`.enums`     — pure-value enums (AutonomyLevel, DecisionStatus, …).
* :mod:`.decisions` — decision-ledger tables + Pydantic schemas + DEFAULT_POLICIES.
* :mod:`.safety`    — kill-switch state, rule firings, preference rules,
  causal discovery reports.

This ``__init__`` re-exports every symbol the legacy ``src.governance.models``
module exposed, so 30+ callers (``from src.governance.models import
DecisionRun, …``) keep working without edits.
"""

from .decisions import (
    Approval,
    ApprovalRequest,
    DecisionPolicy,
    DecisionProposal,
    DecisionRun,
    DecisionRunResponse,
)
from .enums import (
    ApprovalAction,
    AutonomyLevel,
    CausalDiscoveryStatus,
    DecisionStatus,
    PreferenceRuleStatus,
    PreferenceRuleType,
    RejectionCategory,
    RuleFiringOutcome,
)
from .policies import DEFAULT_POLICIES
from .safety import (
    CausalDiscoveryReport,
    KillSwitchActive,
    PreferenceRule,
    RuleFiring,
)

__all__ = [
    # Enums
    "ApprovalAction",
    "AutonomyLevel",
    "CausalDiscoveryStatus",
    "DecisionStatus",
    "PreferenceRuleStatus",
    "PreferenceRuleType",
    "RejectionCategory",
    "RuleFiringOutcome",
    # Decision ledger (SQLA + Pydantic)
    "Approval",
    "ApprovalRequest",
    "DecisionPolicy",
    "DecisionProposal",
    "DecisionRun",
    "DecisionRunResponse",
    "DEFAULT_POLICIES",
    # Safety / learning
    "CausalDiscoveryReport",
    "KillSwitchActive",
    "PreferenceRule",
    "RuleFiring",
]
