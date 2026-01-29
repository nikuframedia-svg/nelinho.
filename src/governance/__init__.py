"""
ProdPlan ONE - Governance Module
=================================

Decision governance with:
- DecisionRun ledger (immutable)
- Approval workflows (SoD)
- Autonomy levels (L1-L5)
- Canary rollout
- Kill switch
"""

from .models import (
    DecisionRun,
    Approval,
    DecisionPolicy,
    AutonomyLevel,
    DecisionStatus,
)
from .service import GovernanceService

__all__ = [
    "DecisionRun",
    "Approval",
    "DecisionPolicy",
    "AutonomyLevel",
    "DecisionStatus",
    "GovernanceService",
]





