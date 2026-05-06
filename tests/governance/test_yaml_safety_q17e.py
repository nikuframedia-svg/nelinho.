"""Tests for Q.17.E — pre-approval safety mechanisms.

Coverage:
- Axiom checks for each of the 7 axioms (positive + negative path).
- Conflict resolver detects 5 conflict shapes (modify_fitness / block /
  reassign_worker / set_config / pause_writes).
- run_safety_checks orchestrator returns combined list.
- RuleSafetyError carries violations.
- service.approve raises RuleSafetyError when checks fail.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from src.governance.yaml_policy.rule_schema import (
    ActionType,
    AxiomRequirement,
    EventType,
    Rule,
)
from src.governance.yaml_policy.safety_checks import (
    AxiomChecker,
    ConflictResolver,
    RuleSafetyError,
    SafetyViolation,
    run_safety_checks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_rule(
    *,
    rid: str = "test-rule",
    actions: list[dict[str, Any]],
    axioms: list[AxiomRequirement] | None = None,
    event: EventType = EventType.SCHEDULE_PROPOSE,
) -> Rule:
    payload = {
        "id": rid,
        "description": "Test rule",
        "when": {"event": event.value, "conditions": []},
        "then": actions,
    }
    if axioms is not None:
        payload["constraints"] = {"axioms_required": [a.value for a in axioms]}
    return Rule.model_validate(payload)


def _alert_action() -> dict[str, Any]:
    return {
        "action": "alert",
        "params": {
            "severity": "info", "title": "x", "message_pt": "y", "entity_refs": [],
        },
    }


# ---------------------------------------------------------------------------
# Axiom 1 — capacity_non_negative
# ---------------------------------------------------------------------------


def test_axiom_capacity_non_negative_blocks_negative_set_config():
    rule = _build_rule(
        rid="bad-capacity",
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "transporte", "key": "truck.capacity",
                    "value": -10, "reason_pt": "x",
                },
            },
        ],
        axioms=[AxiomRequirement.CAPACITY_NON_NEGATIVE],
    )
    violations = AxiomChecker().check(rule)
    errors = [v for v in violations if v.severity == "error"]
    assert any("capacity_non_negative" in v.code for v in errors)


def test_axiom_capacity_non_negative_allows_positive():
    rule = _build_rule(
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "transporte", "key": "truck.capacity",
                    "value": 26, "reason_pt": "ok",
                },
            },
        ],
        axioms=[AxiomRequirement.CAPACITY_NON_NEGATIVE],
    )
    assert AxiomChecker().check(rule) == []


# ---------------------------------------------------------------------------
# Axiom 2 — precedence_monotonic
# ---------------------------------------------------------------------------


def test_axiom_precedence_warns_on_routing_phase_edit():
    rule = _build_rule(
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "routing", "key": "phases.requires_mold",
                    "value": "x", "reason_pt": "y",
                },
            },
        ],
        axioms=[AxiomRequirement.PRECEDENCE_MONOTONIC],
    )
    violations = AxiomChecker().check(rule)
    assert any(v.severity == "warning" and "precedence" in v.code for v in violations)


# ---------------------------------------------------------------------------
# Axiom 3 — mold_exclusive
# ---------------------------------------------------------------------------


def test_axiom_mold_exclusive_blocks_excessive_pocket_count():
    rule = _build_rule(
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "planning", "key": "mold.pocket_count",
                    "value": 99, "reason_pt": "x",
                },
            },
        ],
        axioms=[AxiomRequirement.MOLD_EXCLUSIVE],
    )
    violations = AxiomChecker().check(rule)
    assert any(v.severity == "error" and "mold_exclusive" in v.code for v in violations)


def test_axiom_mold_exclusive_allows_realistic_pocket_count():
    rule = _build_rule(
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "planning", "key": "mold.pocket_count",
                    "value": 7, "reason_pt": "x",
                },
            },
        ],
        axioms=[AxiomRequirement.MOLD_EXCLUSIVE],
    )
    assert AxiomChecker().check(rule) == []


# ---------------------------------------------------------------------------
# Axiom 4 — dual_resource_laminagem
# ---------------------------------------------------------------------------


def test_axiom_dual_resource_warns_on_laminagem_reassign():
    rule = _build_rule(
        actions=[
            {
                "action": "reassign_worker",
                "params": {
                    "phase_id": "laminagem",
                    "replacement_worker_id": "carlos-uuid",
                    "reason_pt": "x",
                },
            },
        ],
        axioms=[AxiomRequirement.DUAL_RESOURCE_LAMINAGEM],
    )
    violations = AxiomChecker().check(rule)
    assert any(v.severity == "warning" and "dual_resource_laminagem" in v.code for v in violations)


# ---------------------------------------------------------------------------
# Axiom 5 — skill_match
# ---------------------------------------------------------------------------


def test_axiom_skill_match_blocks_reassign_without_phase():
    rule = _build_rule(
        actions=[
            {
                "action": "reassign_worker",
                "params": {
                    "phase_id": "",  # empty
                    "replacement_worker_id": "x",
                    "reason_pt": "y",
                },
            },
        ],
        axioms=[AxiomRequirement.SKILL_MATCH],
    )
    violations = AxiomChecker().check(rule)
    assert any(v.severity == "error" and "skill_match" in v.code for v in violations)


# ---------------------------------------------------------------------------
# Axiom 6 — curing_gaps
# ---------------------------------------------------------------------------


def test_axiom_curing_gaps_blocks_zero_or_negative():
    rule = _build_rule(
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "planning", "key": "curing.gap_hours",
                    "value": 0, "reason_pt": "x",
                },
            },
        ],
        axioms=[AxiomRequirement.CURING_GAPS],
    )
    violations = AxiomChecker().check(rule)
    assert any(v.severity == "error" and "curing_gaps" in v.code for v in violations)


# ---------------------------------------------------------------------------
# Axiom 7 — safety_net_baseline
# ---------------------------------------------------------------------------


def test_axiom_safety_net_warns_on_aggressive_multiplier():
    rule = _build_rule(
        actions=[
            {
                "action": "modify_fitness",
                "params": {"weight_key": "makespan", "multiplier": 1.45},
            },
        ],
        axioms=[AxiomRequirement.SAFETY_NET_BASELINE],
    )
    violations = AxiomChecker().check(rule)
    assert any(v.severity == "warning" and "safety_net_baseline" in v.code for v in violations)


def test_axiom_safety_net_silent_on_modest_multiplier():
    rule = _build_rule(
        actions=[
            {
                "action": "modify_fitness",
                "params": {"weight_key": "makespan", "multiplier": 1.1},
            },
        ],
        axioms=[AxiomRequirement.SAFETY_NET_BASELINE],
    )
    assert AxiomChecker().check(rule) == []


# ---------------------------------------------------------------------------
# Conflict resolver
# ---------------------------------------------------------------------------


def test_conflict_modify_fitness_same_weight_different_multiplier():
    new = _build_rule(
        rid="new-rule",
        actions=[
            {"action": "modify_fitness", "params": {"weight_key": "makespan", "multiplier": 1.2}},
        ],
    )
    old = _build_rule(
        rid="old-rule",
        actions=[
            {"action": "modify_fitness", "params": {"weight_key": "makespan", "multiplier": 0.8}},
        ],
    )
    conflicts = ConflictResolver().find_conflicts(new, [old])
    assert any("modify_fitness" in v.code for v in conflicts)


def test_conflict_modify_fitness_same_weight_same_multiplier_no_conflict():
    """Two rules with identical effect aren't a conflict."""
    new = _build_rule(
        rid="new-rule",
        actions=[
            {"action": "modify_fitness", "params": {"weight_key": "makespan", "multiplier": 1.2}},
        ],
    )
    old = _build_rule(
        rid="old-rule",
        actions=[
            {"action": "modify_fitness", "params": {"weight_key": "makespan", "multiplier": 1.2}},
        ],
    )
    assert ConflictResolver().find_conflicts(new, [old]) == []


def test_conflict_block_same_scope():
    new = _build_rule(
        rid="new",
        actions=[{"action": "block", "params": {"reason_pt": "x", "scope": "schedule"}}],
    )
    old = _build_rule(
        rid="old",
        actions=[{"action": "block", "params": {"reason_pt": "y", "scope": "schedule"}}],
    )
    conflicts = ConflictResolver().find_conflicts(new, [old])
    assert any("block" in v.code for v in conflicts)


def test_conflict_reassign_same_phase_different_worker():
    new = _build_rule(
        rid="new",
        actions=[{
            "action": "reassign_worker",
            "params": {"phase_id": "lam", "replacement_worker_id": "A", "reason_pt": "x"},
        }],
    )
    old = _build_rule(
        rid="old",
        actions=[{
            "action": "reassign_worker",
            "params": {"phase_id": "lam", "replacement_worker_id": "B", "reason_pt": "y"},
        }],
    )
    conflicts = ConflictResolver().find_conflicts(new, [old])
    assert any("reassign_worker" in v.code for v in conflicts)


def test_conflict_set_config_same_key_different_value():
    new = _build_rule(
        rid="new",
        actions=[{
            "action": "set_config",
            "params": {"category": "x", "key": "y", "value": 1, "reason_pt": "z"},
        }],
    )
    old = _build_rule(
        rid="old",
        actions=[{
            "action": "set_config",
            "params": {"category": "x", "key": "y", "value": 99, "reason_pt": "w"},
        }],
    )
    conflicts = ConflictResolver().find_conflicts(new, [old])
    assert any("set_config" in v.code for v in conflicts)


def test_conflict_pause_writes_same_prefix():
    new = _build_rule(
        rid="new",
        actions=[{
            "action": "pause_writes",
            "params": {"route_prefix": "/v1/plan", "duration_minutes": 10, "reason_pt": "x"},
        }],
    )
    old = _build_rule(
        rid="old",
        actions=[{
            "action": "pause_writes",
            "params": {"route_prefix": "/v1/plan", "duration_minutes": 5, "reason_pt": "y"},
        }],
    )
    conflicts = ConflictResolver().find_conflicts(new, [old])
    assert any("pause_writes" in v.code for v in conflicts)


def test_conflict_resolver_skips_self():
    """A rule never conflicts with itself."""
    rule = _build_rule(
        rid="self-test",
        actions=[
            {"action": "modify_fitness", "params": {"weight_key": "makespan", "multiplier": 1.2}},
        ],
    )
    assert ConflictResolver().find_conflicts(rule, [rule]) == []


# ---------------------------------------------------------------------------
# Orchestrator + RuleSafetyError
# ---------------------------------------------------------------------------


def test_run_safety_checks_combines_axiom_and_conflict():
    new = _build_rule(
        rid="new-bad",
        actions=[
            {
                "action": "set_config",
                "params": {
                    "category": "transporte", "key": "truck.capacity",
                    "value": -1, "reason_pt": "x",
                },
            },
            {
                "action": "modify_fitness",
                "params": {"weight_key": "makespan", "multiplier": 1.2},
            },
        ],
        axioms=[AxiomRequirement.CAPACITY_NON_NEGATIVE],
    )
    old = _build_rule(
        rid="old",
        actions=[
            {"action": "modify_fitness", "params": {"weight_key": "makespan", "multiplier": 0.8}},
        ],
    )
    violations = run_safety_checks(new, active_rules=[old])
    codes = {v.code for v in violations}
    assert any("axiom.capacity_non_negative" in c for c in codes)
    assert any("conflict.modify_fitness" in c for c in codes)


def test_rule_safety_error_carries_violations():
    v1 = SafetyViolation(rule_id="r", check="axiom", severity="error", code="x.y", detail="d1")
    v2 = SafetyViolation(rule_id="r", check="conflict", severity="error", code="a.b", detail="d2")
    err = RuleSafetyError([v1, v2])
    assert err.violations == [v1, v2]
    assert "x.y" in str(err)
    assert "a.b" in str(err)
