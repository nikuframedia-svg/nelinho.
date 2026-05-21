"""Q.61.03 — property tests for the write-gate wiring invariant.

The Q.17.F.1 bug class (CLAUDE.md, "risk #5 — o mais trust-breaking que
tivemos"): a dispatcher reports ``status="ok"`` even though
``ACTION_WIRING[action]["wired"]`` is False — i.e. it logs but nothing
actually happens downstream. Operators see a green tick and trust a
rule that's a no-op.

The ``_stubbed_or_ok`` helper in ``src/governance/yaml_policy/
dispatchers.py`` is the single chokepoint that prevents this. These
property tests pin its behaviour for every action in ``ACTION_WIRING``
+ every (wired, callback) combination, plus a full integration test
that goes through the real dispatcher path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.governance.yaml_policy.dispatchers import (
    ACTION_WIRING,
    DispatchContext,
    _stubbed_or_ok,
    dispatch,
)
from src.governance.yaml_policy.rule_schema import (
    ActionType,
    EventType,
    Rule,
)

ACTIONS = sorted(ACTION_WIRING.keys())


# ─── helper invariant ─────────────────────────────────────────────────────

@given(action=st.sampled_from(ACTIONS),
       wired=st.booleans(),
       has_callback=st.booleans())
def test_stubbed_or_ok_returns_ok_iff_wired_and_callback(action, wired, has_callback):
    """Invariant: status='ok' if and only if (wired AND has_callback).

    Every other combination must return 'stubbed'. The helper is the only
    place that decides — if it lies, the whole engine lies.
    """
    original = ACTION_WIRING[action].get("wired", False)
    ACTION_WIRING[action]["wired"] = wired
    try:
        status = _stubbed_or_ok(action, has_callback=has_callback)
        if wired and has_callback:
            assert status == "ok", (
                f"action={action!r} wired=True callback=True "
                f"must report 'ok', got {status!r}"
            )
        else:
            assert status == "stubbed", (
                f"action={action!r} wired={wired} has_callback={has_callback} "
                f"must report 'stubbed' (not fully wired), got {status!r}"
            )
    finally:
        ACTION_WIRING[action]["wired"] = original


@given(action=st.text(min_size=1, max_size=40).filter(lambda a: a not in ACTION_WIRING),
       has_callback=st.booleans())
def test_unknown_action_defaults_to_stubbed(action, has_callback):
    """Action name not in ACTION_WIRING must never default to 'ok'.

    A typo in a future dispatcher (calling ``_stubbed_or_ok("alrt", ...)``
    instead of ``"alert"``) must surface as stubbed, not silently green.
    """
    status = _stubbed_or_ok(action, has_callback=has_callback)
    assert status == "stubbed", (
        f"unknown action {action!r} returned {status!r}; "
        "must default to 'stubbed' (closed wiring matrix)"
    )


# ─── end-to-end via real dispatch path ────────────────────────────────────


def _notify_rule() -> Rule:
    """A minimal valid rule that fires a single notify action.

    notify is the right pick because its dispatcher pattern matches the
    other 8 — has_callback + wired drive _stubbed_or_ok, with no
    pause_registry side-effects that would interfere with the test.
    """
    return Rule.model_validate({
        "id": "q61-03-pin-wired-invariant",
        "description": "Pin: wired=False must surface as stubbed in dispatch results",
        "when": {
            "event": EventType.SCHEDULE_PROPOSE.value,
            "conditions": [],
        },
        "then": [{
            "action": ActionType.NOTIFY.value,
            "params": {"channel": "alerts", "payload": {"ping": True}},
        }],
        "constraints": {"axioms_required": []},
        "safety": {"requires_human_approval": True, "kill_switch": "admin_only"},
    })


@pytest.mark.asyncio
async def test_dispatch_reports_stubbed_when_wiring_says_false():
    """End-to-end: flipping ACTION_WIRING[notify].wired to False must make
    the real dispatcher return status='stubbed', even with a callback wired.
    """
    rule = _notify_rule()
    notify_callback = AsyncMock()
    ctx = DispatchContext(
        tenant_id=uuid4(),
        event_type="schedule_propose",
        event_payload={},
        notify=notify_callback,
    )

    # Sanity baseline: today wired=True + callback present → status='ok'.
    results = await dispatch(rule, ctx)
    assert len(results) == 1
    assert results[0].status == "ok"
    assert notify_callback.await_count == 1

    # Flip the wiring to False (simulate "we know this isn't connected yet").
    original = ACTION_WIRING["notify"]["wired"]
    ACTION_WIRING["notify"]["wired"] = False
    try:
        results = await dispatch(rule, ctx)
        assert results[0].status == "stubbed", (
            "REGRESSION: dispatcher reported 'ok' when ACTION_WIRING said "
            "wired=False. This is exactly the Q.17.F.1 bug class."
        )
    finally:
        ACTION_WIRING["notify"]["wired"] = original


@pytest.mark.asyncio
async def test_dispatch_reports_stubbed_when_callback_missing():
    """End-to-end: wired=True but no callback in context → 'stubbed'.

    Operators must see "this rule logs but doesn't actually fire" — the
    second leg of the _stubbed_or_ok contract.
    """
    rule = _notify_rule()
    ctx = DispatchContext(
        tenant_id=uuid4(),
        event_type="schedule_propose",
        event_payload={},
        notify=None,  # no callback wired in this context
    )
    results = await dispatch(rule, ctx)
    assert results[0].status == "stubbed"
    assert "no notify callback" in (results[0].detail or "").lower()
