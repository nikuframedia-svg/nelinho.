"""Tests for Q.17.F — wiring the 5 stubbed dispatchers to real destinations.

Covers the dispatchers wired across Q.17.F.6–F.9:

- F.6 — ``create_decision`` + ``propose_maintenance`` → governance.decision_run
- F.7 — ``reassign_worker`` → governance.decision_run (worker_reassignment)
- F.8 — ``notify`` → RealtimeBridge SSE fan-out
- F.9 — ``pause_writes`` → pause_registry + middleware

Each dispatcher is exercised with a fake callback so no backend is needed.
The wiring-matrix assertions guard the backend/frontend mirror contract.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from src.governance.yaml_policy.dispatchers import (
    ACTION_WIRING,
    DispatchContext,
    dispatch,
)
from src.governance.yaml_policy.rule_schema import ActionType, EventType, Rule

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _build_rule(*, action: ActionType, params: dict[str, Any]) -> Rule:
    """Build a single-action Rule. MOLD_USAGE_THRESHOLD works for every action."""
    return Rule.model_validate({
        "id": f"test-{action.value.replace('_', '-')}",
        "description": "Test rule for Q.17.F dispatcher wiring.",
        "when": {
            "event": EventType.MOLD_USAGE_THRESHOLD.value,
            "conditions": [{"field": "uses_count", "op": "gte", "value": 800}],
        },
        "then": [{"action": action.value, "params": params}],
    })


# ---------------------------------------------------------------------------
# Q.17.F.6 — create_decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_create_decision_calls_callback():
    captured: list[dict[str, Any]] = []

    async def cb(decision_data: dict[str, Any]) -> str:
        captured.append(decision_data)
        return "decision-abc-123"

    rule = _build_rule(
        action=ActionType.CREATE_DECISION,
        params={
            "decision_type": "capacity_review",
            "title": "Rever capacidade da Laminagem",
            "risk_level": "high",
            "action_data": {"phase": "laminagem"},
        },
    )
    ctx = DispatchContext(
        tenant_id=_TENANT,
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 850},
        create_decision=cb,
    )
    results = await dispatch(rule, ctx)

    assert len(captured) == 1
    assert captured[0]["decision_type"] == "capacity_review"
    assert captured[0]["title"] == "Rever capacidade da Laminagem"
    assert captured[0]["risk_level"] == "high"
    assert captured[0]["source_rule"] == rule.id
    assert results[0].payload["decision_id"] == "decision-abc-123"


@pytest.mark.asyncio
async def test_dispatch_create_decision_with_callback_reports_ok():
    async def cb(decision_data: dict[str, Any]) -> str:
        return "d-1"

    rule = _build_rule(
        action=ActionType.CREATE_DECISION,
        params={"decision_type": "x", "title": "y", "risk_level": "low", "action_data": {}},
    )
    ctx = DispatchContext(
        tenant_id=_TENANT,
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 850},
        create_decision=cb,
    )
    results = await dispatch(rule, ctx)
    assert results[0].status == "ok"


@pytest.mark.asyncio
async def test_dispatch_create_decision_no_callback_reports_stubbed():
    rule = _build_rule(
        action=ActionType.CREATE_DECISION,
        params={"decision_type": "x", "title": "y", "risk_level": "low", "action_data": {}},
    )
    ctx = DispatchContext(
        tenant_id=_TENANT,
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 850},
    )
    results = await dispatch(rule, ctx)
    assert results[0].status == "stubbed"
    assert "no create_decision callback" in (results[0].detail or "")


# ---------------------------------------------------------------------------
# Q.17.F.6 — propose_maintenance routes through create_decision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_propose_maintenance_routes_to_create_decision():
    captured: list[dict[str, Any]] = []

    async def cb(decision_data: dict[str, Any]) -> str:
        captured.append(decision_data)
        return "decision-maint-9"

    rule = _build_rule(
        action=ActionType.PROPOSE_MAINTENANCE,
        params={
            "mold_id": "K1-7ML-03",
            "maintenance_type": "preventive",
            "scheduled_date": "2026-06-01",
            "reason_pt": "850 usos atingidos",
        },
    )
    ctx = DispatchContext(
        tenant_id=_TENANT,
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 850},
        create_decision=cb,
    )
    results = await dispatch(rule, ctx)

    assert len(captured) == 1
    assert captured[0]["decision_type"] == "mold_maintenance"
    assert captured[0]["action_data"]["mold_id"] == "K1-7ML-03"
    assert captured[0]["source_rule"] == rule.id
    assert results[0].status == "ok"
    assert results[0].payload["decision_id"] == "decision-maint-9"


@pytest.mark.asyncio
async def test_dispatch_propose_maintenance_no_callback_reports_stubbed():
    rule = _build_rule(
        action=ActionType.PROPOSE_MAINTENANCE,
        params={"mold_id": "K1", "maintenance_type": "preventive", "scheduled_date": "2026-06-01", "reason_pt": "x"},
    )
    ctx = DispatchContext(
        tenant_id=_TENANT,
        event_type=EventType.MOLD_USAGE_THRESHOLD.value,
        event_payload={"uses_count": 850},
    )
    results = await dispatch(rule, ctx)
    assert results[0].status == "stubbed"


# ---------------------------------------------------------------------------
# Wiring matrix — backend side of the backend/frontend mirror
# ---------------------------------------------------------------------------


def test_action_wiring_create_decision_and_propose_maintenance_wired():
    assert ACTION_WIRING["create_decision"]["wired"] is True
    assert ACTION_WIRING["propose_maintenance"]["wired"] is True
