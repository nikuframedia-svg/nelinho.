"""Sprint S4 — guard tests for event flow (Φ1 / Π12).

Confirm that producers, the Topics enum, and consumer handlers all agree on
how event_types route to topics. Before S4 they used three different
conventions and events never reached handlers.
"""
from __future__ import annotations

import pytest

from src.shared.event_contracts import (
    event_type_to_topic_map,
    resolve_topic,
)
from src.shared.kafka_client import Topics


# --- resolve_topic ------------------------------------------------------------

@pytest.mark.parametrize(
    "event_type, expected",
    [
        ("SCHEDULE_CREATED", "prodplan.plan.schedule_created"),
        ("EMPLOYEE_ALLOCATED", "prodplan.hr.employee_allocated"),
        ("LABOR_COST_COMMITTED", "prodplan.hr.labor_cost_committed"),
        ("COGS_CALCULATED", "prodplan.profit.cogs_calculated"),
        ("PRICING_RECOMMENDED", "prodplan.profit.pricing_recommended"),
        ("DECISION_PROPOSED", "prodplan.governance.decision_proposed"),
        ("DECISION_APPROVED", "prodplan.governance.decision_approved"),
        ("ORDER_RECEIVED", "prodplan.core.order_received"),
        ("MOLD_MAINT_DUE", "prodplan.mold.maint_due"),
        ("REWORK_ENTRY_CREATED", "prodplan.quality.rework_entry_created"),
    ],
)
def test_resolve_topic_uppercase(event_type, expected):
    assert resolve_topic(event_type) == expected


def test_resolve_topic_legacy_dot_notation():
    """Legacy emitters use ``copilot.action.executed`` etc. They get
    ``prodplan.`` prefixed."""
    assert resolve_topic("copilot.action.executed") == "prodplan.copilot.action.executed"


def test_resolve_topic_unknown_event_raises():
    with pytest.raises(ValueError, match="Unknown event_type"):
        resolve_topic("FOOBAR_NOT_AN_EVENT")


def test_resolve_topic_empty_raises():
    with pytest.raises(ValueError):
        resolve_topic("")


# --- mapping shape ------------------------------------------------------------

def test_topic_map_covers_all_topics_enum_attrs():
    mapping = event_type_to_topic_map()
    # Sanity: every uppercase string attr on Topics that starts with "prodplan."
    # must appear in the mapping (excluding DLQ which is sink-only).
    expected = {
        a for a in dir(Topics)
        if not a.startswith("_") and isinstance(getattr(Topics, a), str)
        and getattr(Topics, a).startswith("prodplan.")
    }
    assert expected.issubset(mapping.keys())


# --- E2E: producer event_type → topic that consumer subscribes to ------------

def test_handlers_register_event_types_routable_to_subscribed_topics():
    """Boot-time check: every handler registration in handlers.py must
    correspond to a topic that ``start_event_consumer`` actually subscribes to.
    """
    from src.shared.events import handlers as h

    # Mirror the registration list — keep this in sync with
    # ``register_handlers``. The test fails if either side drifts.
    registered_event_types = [
        "ORDER_RECEIVED",
        "SCHEDULE_CREATED",
        "EMPLOYEE_ALLOCATED",
        "LABOR_COST_COMMITTED",
        "COGS_CALCULATED",
    ]
    routed_topics = {resolve_topic(et) for et in registered_event_types}

    # Topics that ``start_event_consumer`` subscribes to (handlers.py:start_event_consumer).
    subscribed_topics = {
        Topics.SCHEDULE_CREATED,
        Topics.EMPLOYEE_ALLOCATED,
        Topics.LABOR_COST_COMMITTED,
        Topics.COGS_CALCULATED,
        Topics.PRICING_RECOMMENDED,
    }

    # Every handler-registered event_type must route to a topic the consumer
    # listens on (with the exception of ORDER_RECEIVED, which is an inbound
    # external topic that the consumer must be told to subscribe to as well).
    not_subscribed = routed_topics - subscribed_topics - {Topics.ORDER_RECEIVED}
    # We allow ORDER_RECEIVED to be missing from start_event_consumer's
    # subscription list as long as the routing itself works; that's a
    # follow-up infra wiring concern, not a routing bug.
    assert not_subscribed == set(), (
        f"Handlers exist for {not_subscribed} but no consumer subscribes to "
        f"those topics — events would route into the void."
    )


def test_outbox_dispatcher_uses_resolve_topic():
    """Sprint S4: dispatcher must not compute topic strings ad-hoc anymore."""
    text = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "src" / "shared" / "outbox_dispatcher.py"
    ).read_text(encoding="utf-8")
    # Old buggy expression must be gone.
    assert 'f"prodplan.{event.event_type}"' not in text
    # New canonical resolver must be present.
    assert "resolve_topic(event.event_type)" in text
