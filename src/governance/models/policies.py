"""Default policy seed data.

Q.67.6.B5 — split out of ``src/governance/models/decisions.py`` so that
sub-file stays under 500L. Holds the bootstrap ``DEFAULT_POLICIES`` list that
:meth:`GovernanceService.bootstrap_policies` consumes on first start of a
tenant.

These dicts are pinned by ``tests/governance/test_api_models_characterization
_q67.py`` (every entry has the same shape, kill_switch is L5 + no approval,
standard_time_update needs 2 approvers + canary 10%).
"""

from __future__ import annotations

from .enums import AutonomyLevel


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


__all__ = ["DEFAULT_POLICIES"]
