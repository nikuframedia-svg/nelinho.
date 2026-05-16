"""Tests for Q.17.D — condition_evaluator + engine + dispatchers.

Coverage:
- 8 condition operators (eq/ne/gt/lt/gte/lte/in/matches) + missing field + type mismatch.
- AND-joined evaluation; empty conditions = unconditional True.
- Dispatch all 9 action types end-to-end (with stub callbacks).
- Engine on_event: registry lookup, condition match, dispatch, rate limit, dedupe.
- Tenant scoping: another tenant's rule never fires here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.governance.yaml_policy.condition_evaluator import (
    evaluate_all,
    evaluate_condition,
)
from src.governance.yaml_policy.dispatchers import (
    DispatchContext,
    dispatch,
)
from src.governance.yaml_policy.engine import RuleEngine, _payload_fingerprint
from src.governance.yaml_policy.models import RuleLifecycleStatus, TenantRule
from src.governance.yaml_policy.rule_schema import (
    ActionType,
    Condition,
    ConditionOp,
    EventType,
    Rule,
)


# ---------------------------------------------------------------------------
# Condition evaluator
# ---------------------------------------------------------------------------


def _cond(field: str, op: ConditionOp, value: Any) -> Condition:
    return Condition(field=field, op=op, value=value)


def test_eval_eq_match():
    assert evaluate_condition(_cond("x", ConditionOp.EQ, 5), {"x": 5}) is True


def test_eval_eq_mismatch():
    assert evaluate_condition(_cond("x", ConditionOp.EQ, 5), {"x": 6}) is False


def test_eval_eq_strict_no_coercion():
    """42 != '42' — types matter for safety."""
    assert evaluate_condition(_cond("x", ConditionOp.EQ, 42), {"x": "42"}) is False


def test_eval_ne():
    assert evaluate_condition(_cond("x", ConditionOp.NE, 5), {"x": 6}) is True
    assert evaluate_condition(_cond("x", ConditionOp.NE, 5), {"x": 5}) is False


@pytest.mark.parametrize("op,actual,expected,result", [
    (ConditionOp.GT, 10, 5, True),
    (ConditionOp.GT, 5, 10, False),
    (ConditionOp.LT, 5, 10, True),
    (ConditionOp.GTE, 10, 10, True),
    (ConditionOp.GTE, 9, 10, False),
    (ConditionOp.LTE, 10, 10, True),
    (ConditionOp.LTE, 11, 10, False),
])
def test_eval_ordering(op, actual, expected, result):
    assert evaluate_condition(_cond("x", op, expected), {"x": actual}) is result


def test_eval_in_match():
    assert evaluate_condition(_cond("x", ConditionOp.IN, [1, 2, 3]), {"x": 2}) is True


def test_eval_in_no_match():
    assert evaluate_condition(_cond("x", ConditionOp.IN, [1, 2, 3]), {"x": 99}) is False


def test_eval_in_value_not_a_sequence():
    """value=42 is not a list/tuple/set — return False, don't crash."""
    assert evaluate_condition(_cond("x", ConditionOp.IN, 42), {"x": 1}) is False


def test_eval_matches_regex():
    cond = _cond("name", ConditionOp.MATCHES, r"^K1\s")
    assert evaluate_condition(cond, {"name": "K1 Vanquish L"}) is True
    assert evaluate_condition(cond, {"name": "K2 Hybrid"}) is False


def test_eval_matches_invalid_regex_returns_false():
    cond = _cond("name", ConditionOp.MATCHES, r"[invalid")
    assert evaluate_condition(cond, {"name": "K1"}) is False


def test_eval_matches_non_string_actual():
    cond = _cond("x", ConditionOp.MATCHES, r"\d+")
    assert evaluate_condition(cond, {"x": 42}) is False


def test_eval_missing_field_returns_false():
    assert evaluate_condition(_cond("absent", ConditionOp.EQ, 5), {"x": 5}) is False


def test_eval_type_mismatch_on_ordering_returns_false():
    """5 > 'abc' raises TypeError — should silently return False, not crash."""
    assert evaluate_condition(_cond("x", ConditionOp.GT, "abc"), {"x": 5}) is False


def test_evaluate_all_empty_is_true():
    assert evaluate_all([], {"x": 1}) is True


def test_evaluate_all_and_joined():
    conds = [
        _cond("x", ConditionOp.GT, 0),
        _cond("y", ConditionOp.EQ, "z"),
    ]
    assert evaluate_all(conds, {"x": 5, "y": "z"}) is True
    assert evaluate_all(conds, {"x": 5, "y": "w"}) is False
    assert evaluate_all(conds, {"x": 0, "y": "z"}) is False


# ---------------------------------------------------------------------------
# Dispatchers
# ---------------------------------------------------------------------------


def _build_rule(*, action: ActionType, params: dict[str, Any]) -> Rule:
    """Helper to build a Rule with a single arbitrary action."""
    # Pick an event_type compatible with most actions; ALERT works everywhere.
    return Rule.model_validate({
        "id": f"test-{action.value.replace('_', '-')}",
        "description": "Test",
        "when": {
            "event": EventType.MOLD_USAGE_THRESHOLD.value,
            "conditions": [{"field": "uses_count", "op": "gte", "value": 800}],
        },
        "then": [{"action": action.value, "params": params}],
    })


@pytest.mark.asyncio
async def test_dispatch_alert_no_callback():
    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )
    ctx = DispatchContext(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 850},
    )
    results = await dispatch(rule, ctx)
    assert len(results) == 1
    assert results[0].action == "alert"
    # Q.17.F.1: alert is "stubbed" without an emit_alert callback
    # AND because the wiring matrix marks alert as not-yet-wired (Q.17.F.4
    # will flip the matrix once the alerts.service callback is in place).
    assert results[0].status == "stubbed"
    assert results[0].payload["severity"] == "high"


@pytest.mark.asyncio
async def test_dispatch_alert_with_callback():
    captured: list[dict[str, Any]] = []

    async def cb(p: dict[str, Any]) -> None:
        captured.append(p)

    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "Alert!", "message_pt": "x", "entity_refs": ["mold:K1"]},
    )
    ctx = DispatchContext(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 900},
        emit_alert=cb,
    )
    await dispatch(rule, ctx)
    assert len(captured) == 1
    assert captured[0]["title"] == "Alert!"


@pytest.mark.asyncio
async def test_dispatch_block_returns_payload():
    rule = _build_rule(
        action=ActionType.BLOCK,
        params={"reason_pt": "Throughput baixo", "scope": "schedule"},
    )
    ctx = DispatchContext(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        event_type=EventType.KPI_THRESHOLD_CROSSED.value,
        event_payload={},
    )
    results = await dispatch(rule, ctx)
    assert results[0].action == "block"
    assert results[0].payload["scope"] == "schedule"


@pytest.mark.asyncio
async def test_dispatch_modify_fitness_calls_set_config():
    captured: list[tuple[str, str, Any, str | None]] = []

    async def set_cfg(cat: str, key: str, val: Any, reason: str | None) -> None:
        captured.append((cat, key, val, reason))

    rule = _build_rule(
        action=ActionType.MODIFY_FITNESS,
        params={"weight_key": "makespan", "multiplier": 1.2},
    )
    ctx = DispatchContext(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        event_type=EventType.SCHEDULE_PROPOSE.value,
        event_payload={},
        set_config=set_cfg,
    )
    await dispatch(rule, ctx)
    assert captured == [("planning", "fitness.weight.makespan", 1.2, "yaml_policy rule test-modify-fitness")]


@pytest.mark.asyncio
async def test_dispatch_all_9_actions_work_without_callbacks():
    """No-callback dispatch should not crash for any action type.

    Q.17.F.1: result.status is ``stubbed`` for actions whose optional
    context callback is missing. ``block`` and ``pause_writes`` are
    structurally always ``ok`` because they need no external callback —
    ``block`` has no destination and ``pause_writes`` writes straight to
    the in-process pause registry.
    """
    from src.governance.yaml_policy import pause_registry
    pause_registry.reset_for_tests()
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    matrix: dict[ActionType, dict[str, Any]] = {
        ActionType.ALERT: {"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
        ActionType.BLOCK: {"reason_pt": "x", "scope": "operation"},
        ActionType.MODIFY_FITNESS: {"weight_key": "makespan", "multiplier": 1.1},
        ActionType.REASSIGN_WORKER: {"phase_id": "x", "replacement_worker_id": "y", "reason_pt": "z"},
        ActionType.PROPOSE_MAINTENANCE: {"mold_id": "M-K1", "maintenance_type": "preventive", "scheduled_date": "2026-06-01", "reason_pt": "x"},
        ActionType.NOTIFY: {"channel": "alerts", "topic": "x", "payload": {}},
        ActionType.SET_CONFIG: {"category": "x", "key": "y", "value": 1, "reason_pt": "z"},
        ActionType.CREATE_DECISION: {"decision_type": "x", "title": "y", "risk_level": "low", "action_data": {}},
        ActionType.PAUSE_WRITES: {"route_prefix": "/v1/x", "duration_minutes": 5, "reason_pt": "y"},
    }
    for action, params in matrix.items():
        rule = _build_rule(action=action, params=params)
        ctx = DispatchContext(
            tenant_id=tenant_id,
            event_type=rule.when.event.value,
            event_payload={"uses_count": 999},
        )
        results = await dispatch(rule, ctx)
        assert results[0].action == action.value
        # All dispatchers run without crashing. ``block`` and
        # ``pause_writes`` are "ok" without callbacks; the rest report
        # ``stubbed``.
        if action in (ActionType.BLOCK, ActionType.PAUSE_WRITES):
            assert results[0].status == "ok"
        else:
            assert results[0].status == "stubbed"


@pytest.mark.asyncio
async def test_dispatch_modify_fitness_with_callback_reports_ok():
    """When the wiring matrix says ``wired=True`` AND the callback is
    provided, status flips to ``ok``."""
    captured: list[Any] = []

    async def set_cfg(cat: str, key: str, val: Any, reason: str | None) -> None:
        captured.append((cat, key, val, reason))

    rule = _build_rule(
        action=ActionType.MODIFY_FITNESS,
        params={"weight_key": "makespan", "multiplier": 1.2},
    )
    ctx = DispatchContext(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        event_type=EventType.SCHEDULE_PROPOSE.value,
        event_payload={},
        set_config=set_cfg,
    )
    results = await dispatch(rule, ctx)
    assert results[0].status == "ok"
    assert len(captured) == 1


def test_action_wiring_matrix_has_entry_per_action_type():
    """Q.17.F.1 — every ActionType has a wiring matrix entry."""
    from src.governance.yaml_policy.dispatchers import ACTION_WIRING
    for action in ActionType:
        assert action.value in ACTION_WIRING, f"ACTION_WIRING missing entry for {action.value}"
        entry = ACTION_WIRING[action.value]
        assert "wired" in entry
        assert "destination" in entry


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _make_db_row(rule: Rule, *, tenant_id: UUID) -> TenantRule:
    """Build a TenantRule row matching a Rule, status=active."""
    row = TenantRule(
        id=uuid4(),
        tenant_id=tenant_id,
        rule_id=rule.id,
        description=rule.description,
        status=RuleLifecycleStatus.ACTIVE,
        event_type=rule.when.event.value,
        payload=rule.model_dump(mode="json", exclude_none=True),
    )
    return row


def test_payload_fingerprint_stable_for_key_order():
    a = _payload_fingerprint({"x": 1, "y": 2})
    b = _payload_fingerprint({"y": 2, "x": 1})
    assert a == b


def test_payload_fingerprint_differs_for_different_payloads():
    assert _payload_fingerprint({"x": 1}) != _payload_fingerprint({"x": 2})


@pytest.mark.asyncio
async def test_engine_install_and_fire():
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )
    row = _make_db_row(rule, tenant_id=tenant_id)
    engine = RuleEngine()
    engine.install_rule(row, rule)
    assert engine.rule_count == 1

    fired = await engine.on_event(
        EventType.MOLD_USAGE_THRESHOLD,
        {"uses_count": 850},
        tenant_id=tenant_id,
    )
    assert len(fired) == 1
    assert fired[0][0].id == rule.id
    assert fired[0][1][0].action == "alert"


@pytest.mark.asyncio
async def test_engine_skips_when_conditions_dont_match():
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )
    row = _make_db_row(rule, tenant_id=tenant_id)
    engine = RuleEngine()
    engine.install_rule(row, rule)

    fired = await engine.on_event(
        EventType.MOLD_USAGE_THRESHOLD,
        {"uses_count": 100},  # below 800 threshold
        tenant_id=tenant_id,
    )
    assert fired == []


@pytest.mark.asyncio
async def test_engine_tenant_scoping():
    """A rule for tenant A never fires for tenant B."""
    tenant_a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )
    row = _make_db_row(rule, tenant_id=tenant_a)
    engine = RuleEngine()
    engine.install_rule(row, rule)

    fired = await engine.on_event(
        EventType.MOLD_USAGE_THRESHOLD,
        {"uses_count": 900},
        tenant_id=tenant_b,
    )
    assert fired == []


@pytest.mark.asyncio
async def test_engine_rate_limit():
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    rule = Rule.model_validate({
        "id": "test-rate-limited",
        "description": "Limited to 2 fires/day.",
        "when": {
            "event": EventType.MOLD_USAGE_THRESHOLD.value,
            "conditions": [{"field": "uses_count", "op": "gte", "value": 800}],
        },
        "then": [{"action": "alert", "params": {"severity": "info", "title": "x", "message_pt": "y", "entity_refs": []}}],
        "safety": {"max_fires_per_day": 2},
    })
    row = _make_db_row(rule, tenant_id=tenant_id)
    engine = RuleEngine()
    engine.install_rule(row, rule)

    # Different fingerprints to bypass dedupe
    for n in range(5):
        await engine.on_event(
            EventType.MOLD_USAGE_THRESHOLD,
            {"uses_count": 800 + n},
            tenant_id=tenant_id,
        )
    rec = engine._fire_records[rule.id]
    assert rec.fires_today == 2  # capped


@pytest.mark.asyncio
async def test_engine_dedupe():
    """Same payload twice in a row → second skipped."""
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )
    row = _make_db_row(rule, tenant_id=tenant_id)
    engine = RuleEngine()
    engine.install_rule(row, rule)

    payload = {"uses_count": 850}
    f1 = await engine.on_event(EventType.MOLD_USAGE_THRESHOLD, payload, tenant_id=tenant_id)
    f2 = await engine.on_event(EventType.MOLD_USAGE_THRESHOLD, payload, tenant_id=tenant_id)
    assert len(f1) == 1
    assert len(f2) == 0  # deduped


@pytest.mark.asyncio
async def test_engine_block_results_helper():
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    rule = Rule.model_validate({
        "id": "test-block-rule",
        "description": "Bloqueia tudo abaixo de €25K.",
        "when": {
            "event": EventType.KPI_THRESHOLD_CROSSED.value,
            "conditions": [
                {"field": "kpi_name", "op": "eq", "value": "throughput_eur_day"},
                {"field": "kpi_value", "op": "lt", "value": 25000},
            ],
        },
        "then": [
            {"action": "block", "params": {"reason_pt": "throughput baixo", "scope": "schedule"}},
            {"action": "alert", "params": {"severity": "critical", "title": "x", "message_pt": "y", "entity_refs": []}},
        ],
    })
    row = _make_db_row(rule, tenant_id=tenant_id)
    engine = RuleEngine()
    engine.install_rule(row, rule)

    fired = await engine.on_event(
        EventType.KPI_THRESHOLD_CROSSED,
        {"kpi_name": "throughput_eur_day", "kpi_value": 22000},
        tenant_id=tenant_id,
    )
    blocks = RuleEngine.block_results(fired)
    assert len(blocks) == 1
    assert blocks[0].payload["scope"] == "schedule"


@pytest.mark.asyncio
async def test_engine_remove_rule():
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    rule = _build_rule(
        action=ActionType.ALERT,
        params={"severity": "high", "title": "x", "message_pt": "y", "entity_refs": []},
    )
    row = _make_db_row(rule, tenant_id=tenant_id)
    engine = RuleEngine()
    engine.install_rule(row, rule)
    assert engine.rule_count == 1

    assert engine.remove_rule(row.id) is True
    assert engine.rule_count == 0
    assert engine.remove_rule(row.id) is False  # second remove no-op
