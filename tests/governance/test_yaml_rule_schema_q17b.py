"""Tests for Q.17.B — tenant_rules.yaml DSL + LLM function-calling specs.

Coverage:
- Closed whitelists (event/action/operator) reject unknown values.
- Per-event field whitelist refuses fields foreign to the event.
- Per-action params whitelist refuses unknown params.
- Action-specific sanity: modify_fitness multiplier bounded ±50%, notify channel restricted.
- Rule.id pattern + double-separator rejection.
- Top-level duplicate-id detection.
- LLM tool spec is a valid JSON-schema with the expected enum sizes.
- rule_to_yaml_dict round-trips a tool-call back through validation.
- load_tenant_rules returns empty when file missing; raises on schema invalid.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml as pyyaml
from pydantic import ValidationError

from src.governance.yaml_policy import (
    ACTION_PARAMS,
    EVENT_FIELDS,
    ActionStep,
    ActionType,
    AxiomRequirement,
    Condition,
    ConditionOp,
    EventType,
    Rule,
    RuleStatus,
    TenantRulesYaml,
    TriggerSpec,
    YamlPolicyError,
    load_tenant_rules,
    propose_rule_tool,
    rule_to_yaml_dict,
)


# ---------------------------------------------------------------------------
# Whitelists
# ---------------------------------------------------------------------------


def test_event_type_has_exactly_12_members():
    assert len(EventType) == 12


def test_action_type_has_exactly_9_members():
    assert len(ActionType) == 9


def test_condition_op_has_exactly_8_members():
    assert len(ConditionOp) == 8


def test_axiom_requirement_has_exactly_7_members():
    assert len(AxiomRequirement) == 7


def test_event_fields_keys_match_event_type_members():
    assert set(EVENT_FIELDS.keys()) == set(EventType)


def test_action_params_keys_match_action_type_members():
    assert set(ACTION_PARAMS.keys()) == set(ActionType)


# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------


def test_condition_minimal():
    c = Condition(field="worker_id", op=ConditionOp.EQ, value="abc")
    assert c.op is ConditionOp.EQ


def test_condition_rejects_unknown_op():
    with pytest.raises(ValidationError):
        Condition(field="x", op="like", value="y")  # type: ignore[arg-type]


def test_condition_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Condition(field="x", op=ConditionOp.EQ, value=1, foo="bar")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# TriggerSpec
# ---------------------------------------------------------------------------


def test_trigger_accepts_known_field():
    TriggerSpec(
        event=EventType.WORKER_ABSENT,
        conditions=[Condition(field="worker_id", op=ConditionOp.EQ, value="x")],
    )


def test_trigger_rejects_field_not_in_event_whitelist():
    with pytest.raises(ValidationError, match="does not expose fields"):
        TriggerSpec(
            event=EventType.WORKER_ABSENT,
            conditions=[Condition(field="not_a_real_field", op=ConditionOp.EQ, value="x")],
        )


def test_trigger_unconditional_ok():
    """Empty conditions = fire on every event of that type."""
    TriggerSpec(event=EventType.SCHEDULE_PROPOSE, conditions=[])


# ---------------------------------------------------------------------------
# ActionStep
# ---------------------------------------------------------------------------


def test_action_alert_minimal():
    ActionStep(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )


def test_action_rejects_unknown_param():
    with pytest.raises(ValidationError, match="does not accept params"):
        ActionStep(action=ActionType.ALERT, params={"nope": "x"})


def test_modify_fitness_requires_multiplier():
    with pytest.raises(ValidationError, match="modify_fitness requires numeric"):
        ActionStep(action=ActionType.MODIFY_FITNESS, params={"weight_key": "makespan"})


def test_modify_fitness_multiplier_bounded():
    ActionStep(
        action=ActionType.MODIFY_FITNESS,
        params={"weight_key": "makespan", "multiplier": 1.2},
    )
    with pytest.raises(ValidationError, match="out of bounds"):
        ActionStep(
            action=ActionType.MODIFY_FITNESS,
            params={"weight_key": "makespan", "multiplier": 2.0},
        )
    with pytest.raises(ValidationError, match="out of bounds"):
        ActionStep(
            action=ActionType.MODIFY_FITNESS,
            params={"weight_key": "makespan", "multiplier": 0.4},
        )


def test_notify_channel_whitelist():
    ActionStep(
        action=ActionType.NOTIFY,
        params={"channel": "alerts", "topic": "x", "payload": {}},
    )
    with pytest.raises(ValidationError, match="channel="):
        ActionStep(
            action=ActionType.NOTIFY,
            params={"channel": "discord", "topic": "x", "payload": {}},
        )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


def _minimal_rule_kwargs() -> dict:
    return {
        "id": "test-rule-001",
        "description": "Test rule for unit testing.",
        "when": {
            "event": EventType.MOLD_USAGE_THRESHOLD.value,
            "conditions": [
                {"field": "uses_count", "op": "gte", "value": 800},
            ],
        },
        "then": [
            {
                "action": ActionType.ALERT.value,
                "params": {
                    "severity": "high",
                    "title": "Mold near cycle limit",
                    "message_pt": "Atingiu 800 usos",
                    "entity_refs": [],
                },
            },
        ],
    }


def test_rule_minimal_validates():
    r = Rule.model_validate(_minimal_rule_kwargs())
    assert r.status is RuleStatus.PROPOSED
    assert r.safety.requires_human_approval is True
    assert r.safety.kill_switch == "admin_only"


def test_rule_id_pattern():
    bad = _minimal_rule_kwargs()
    bad["id"] = "Bad ID With Spaces"
    with pytest.raises(ValidationError):
        Rule.model_validate(bad)


def test_rule_id_no_double_separators():
    bad = _minimal_rule_kwargs()
    bad["id"] = "test--rule"
    with pytest.raises(ValidationError, match="double separators"):
        Rule.model_validate(bad)


def test_rule_then_must_have_at_least_one_action():
    bad = _minimal_rule_kwargs()
    bad["then"] = []
    with pytest.raises(ValidationError):
        Rule.model_validate(bad)


def test_rule_safety_human_approval_cannot_be_disabled():
    """Always-human-approval is a Literal[True]; client cannot opt out."""
    kwargs = _minimal_rule_kwargs()
    kwargs["safety"] = {"requires_human_approval": False}
    with pytest.raises(ValidationError):
        Rule.model_validate(kwargs)


def test_rule_kill_switch_cannot_be_overridden():
    """Kill switch is admin-SQL-only; the schema only allows the literal."""
    kwargs = _minimal_rule_kwargs()
    kwargs["safety"] = {"kill_switch": "anyone"}
    with pytest.raises(ValidationError):
        Rule.model_validate(kwargs)


# ---------------------------------------------------------------------------
# TenantRulesYaml
# ---------------------------------------------------------------------------


def test_tenant_rules_yaml_empty_ok():
    doc = TenantRulesYaml(version=1, rules=[])
    assert doc.schema_name == "tenant_rules.v1"


def test_tenant_rules_yaml_rejects_duplicate_ids():
    rule1 = _minimal_rule_kwargs()
    rule2 = _minimal_rule_kwargs()  # same id
    with pytest.raises(ValidationError, match="duplicate rule ids"):
        TenantRulesYaml(version=1, rules=[rule1, rule2])  # type: ignore[arg-type]


def test_tenant_rules_yaml_version_bounded():
    with pytest.raises(ValidationError):
        TenantRulesYaml(version=99, rules=[])


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_load_tenant_rules_missing_file_returns_empty(tmp_path: Path):
    """Fresh tenant — no rules authored yet — returns empty doc, doesn't raise."""
    yaml_dir = tmp_path / "config" / "yaml"
    yaml_dir.mkdir(parents=True)
    doc = load_tenant_rules(yaml_dir)
    assert doc.version == 1
    assert doc.rules == []


def test_load_tenant_rules_schema_invalid_raises(tmp_path: Path):
    yaml_dir = tmp_path / "config" / "yaml"
    yaml_dir.mkdir(parents=True)
    body = pyyaml.safe_dump(
        {
            "version": 1,
            "rules": [
                {
                    "id": "bad",
                    "description": "x",
                    "when": {"event": "not_a_real_event", "conditions": []},
                    "then": [{"action": "alert", "params": {}}],
                }
            ],
        }
    )
    (yaml_dir / "tenant_rules.yaml").write_text(body, encoding="utf-8")
    with pytest.raises(YamlPolicyError, match="schema invalid"):
        load_tenant_rules(yaml_dir)


def test_load_tenant_rules_round_trip_example_file():
    """The reference example file at config/yaml/tenant_rules.example.yaml validates."""
    real_dir = Path(__file__).resolve().parents[2] / "config" / "yaml"
    raw = pyyaml.safe_load((real_dir / "tenant_rules.example.yaml").read_text(encoding="utf-8"))
    doc = TenantRulesYaml.model_validate(raw)
    ids = [r.id for r in doc.rules]
    assert "mold-k1-7ml-03-near-cycle-cap" in ids
    assert "paulo-friday-replacement-2026" in ids
    assert "throughput-collapse-block-friday-changes" in ids


# ---------------------------------------------------------------------------
# LLM tool spec
# ---------------------------------------------------------------------------


def test_propose_rule_tool_shape():
    spec = propose_rule_tool()
    assert spec["type"] == "function"
    fn = spec["function"]
    assert fn["name"] == "propose_rule"
    params = fn["parameters"]
    assert params["type"] == "object"
    assert params["additionalProperties"] is False
    assert {"id", "description", "when", "then"} <= set(params["required"])


def test_propose_rule_tool_event_enum_matches_pydantic():
    spec = propose_rule_tool()
    enum = spec["function"]["parameters"]["properties"]["when"]["properties"]["event"]["enum"]
    assert set(enum) == {e.value for e in EventType}


def test_propose_rule_tool_action_enum_matches_pydantic():
    spec = propose_rule_tool()
    enum = spec["function"]["parameters"]["properties"]["then"]["items"]["properties"]["action"]["enum"]
    assert set(enum) == {a.value for a in ActionType}


def test_propose_rule_tool_op_enum_matches_pydantic():
    spec = propose_rule_tool()
    cond = spec["function"]["parameters"]["properties"]["when"]["properties"]["conditions"]["items"]
    assert set(cond["properties"]["op"]["enum"]) == {o.value for o in ConditionOp}


def test_rule_to_yaml_dict_round_trips_minimal():
    out = rule_to_yaml_dict(_minimal_rule_kwargs())
    assert out["id"] == "test-rule-001"
    assert out["when"]["event"] == EventType.MOLD_USAGE_THRESHOLD.value
    assert out["then"][0]["action"] == ActionType.ALERT.value


def test_rule_to_yaml_dict_rejects_invalid():
    bad = _minimal_rule_kwargs()
    bad["when"]["conditions"][0]["field"] = "not_in_event_whitelist"
    with pytest.raises(ValidationError):
        rule_to_yaml_dict(bad)
