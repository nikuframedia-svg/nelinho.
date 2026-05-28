"""Q.116.E — ``work_order_id`` derivation on ``DecisionResponse``.

The frontend ``DecisoesPage`` wraps decision rows with
``<Clickable kind="encomenda">`` and needs ``work_order_id`` in the payload.
``DecisionRun.action_data`` is JSONB without strict schema, so the router
derives the int from ``action_data.work_order_id`` (or returns ``None``).

These are plain unit tests — no FastAPI, no DB. The router is wired through
``_decision_to_response(decision_dict) -> DecisionResponse`` precisely so
the derivation can be exercised in isolation.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.governance.routers.decisions import (
    DecisionResponse,
    _decision_to_response,
    _extract_wo_id,
)


# ---------------------------------------------------------------------------
# Direct helper tests — _extract_wo_id
# ---------------------------------------------------------------------------

def test_extract_wo_id_present_int_q116e():
    """Common case — int already in action_data."""
    assert _extract_wo_id({"work_order_id": 42}) == 42


def test_extract_wo_id_present_stringified_int_q116e():
    """JSON over the wire occasionally stringifies ids; coerce when safe."""
    assert _extract_wo_id({"work_order_id": "42"}) == 42


def test_extract_wo_id_absent_returns_none_q116e():
    assert _extract_wo_id({}) is None
    assert _extract_wo_id({"foo": "bar"}) is None


def test_extract_wo_id_none_action_data_q116e():
    assert _extract_wo_id(None) is None


def test_extract_wo_id_explicit_null_q116e():
    assert _extract_wo_id({"work_order_id": None}) is None


def test_extract_wo_id_bad_value_returns_none_q116e():
    """Non-coercible values must not blow up the response."""
    assert _extract_wo_id({"work_order_id": "not_an_int"}) is None
    assert _extract_wo_id({"work_order_id": ["nope"]}) is None
    assert _extract_wo_id({"work_order_id": {"nested": 1}}) is None


# ---------------------------------------------------------------------------
# End-to-end through _decision_to_response — what the router actually calls
# ---------------------------------------------------------------------------

def _base_decision(**overrides: Any) -> Dict[str, Any]:
    """Minimal decision dict shaped like ``DecisionQuery._run_to_dict``."""
    base: Dict[str, Any] = {
        "id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "decision_type": "schedule_change",
        "title": "Reagendar encomenda",
        "description": None,
        "status": "proposed",
        "policy_version": "v1",
        "autonomy_level": "approval",
        "action_data": {},
        "expected_impact": None,
        "risk_level": "medium",
        "scenario_id": None,
        "evidence_refs": [],
        "input_snapshot_hash": "deadbeef",
        "prev_hash": None,
        "audit_hash": "cafebabe",
        "proposed_at": "2026-05-28T10:00:00+00:00",
        "proposed_by": "alice",
        "approved_at": None,
        "executed_at": None,
        "executed_by": None,
        "rolled_back_at": None,
        "rolled_back_by": None,
        "rollback_reason": None,
        "approvals": [],
    }
    base.update(overrides)
    return base


def test_decision_to_response_populates_wo_id_q116e():
    decision = _base_decision(action_data={"work_order_id": 7})
    resp = _decision_to_response(decision)
    assert isinstance(resp, DecisionResponse)
    assert resp.work_order_id == 7
    # Core fields still pass through.
    assert resp.id == "11111111-1111-1111-1111-111111111111"
    assert resp.decision_type == "schedule_change"


def test_decision_to_response_no_wo_id_q116e():
    decision = _base_decision(action_data={})
    resp = _decision_to_response(decision)
    assert resp.work_order_id is None


def test_decision_to_response_none_action_data_q116e():
    """A None ``action_data`` shouldn't crash — ``DecisionRun.action_data``
    can be NULL in the DB even though it defaults to ``{}`` on propose."""
    decision = _base_decision(action_data=None)
    resp = _decision_to_response(decision)
    assert resp.work_order_id is None


def test_decision_to_response_bad_wo_id_silenced_q116e():
    decision = _base_decision(action_data={"work_order_id": "not_an_int"})
    resp = _decision_to_response(decision)
    assert resp.work_order_id is None


def test_decision_response_serializes_wo_id_q116e():
    """FastAPI serializes via ``model_dump()`` — the field must be visible
    so the frontend sees ``work_order_id`` in the JSON payload."""
    decision = _base_decision(action_data={"work_order_id": 99})
    resp = _decision_to_response(decision)
    dumped = resp.model_dump()
    assert "work_order_id" in dumped
    assert dumped["work_order_id"] == 99
