"""Sprint D.1 — channel mapping tests."""

from __future__ import annotations

import pytest

from src.shared.kafka_client import Topics
from src.shared.realtime.channels import (
    CHANNELS,
    all_topics,
    channel_for_topic,
    resolve_topics,
)


def test_channels_are_registered():
    # Sprint Q.14.B added `rule_firing` (Postgres NOTIFY-sourced).
    assert set(CHANNELS) == {
        "alerts", "dashboard", "governance", "rule_firing", "timeline",
    }


def test_resolve_single_channel_returns_its_topics():
    topics = resolve_topics(["alerts"])
    assert Topics.MOLD_MAINT_DUE in topics
    assert Topics.MATERIAL_SHORTAGE_DETECTED in topics
    # Alerts should NOT include governance topics.
    assert Topics.DECISION_EXECUTED not in topics


def test_resolve_multiple_channels_unions_topics():
    topics = resolve_topics(["alerts", "governance"])
    assert Topics.MOLD_MAINT_DUE in topics
    assert Topics.DECISION_EXECUTED in topics


def test_resolve_is_case_insensitive():
    assert resolve_topics(["ALERTS"]) == resolve_topics(["alerts"])


def test_resolve_raises_on_unknown_channel():
    with pytest.raises(ValueError, match="unknown channel"):
        resolve_topics(["alerts", "made_up"])


def test_channel_for_topic_reverse_lookup():
    # MOLD_MAINT_DUE belongs only to alerts.
    assert channel_for_topic(Topics.MOLD_MAINT_DUE) == ["alerts"]
    # DECISION_EXECUTED belongs to both governance and timeline.
    channels = set(channel_for_topic(Topics.DECISION_EXECUTED))
    assert channels == {"governance", "timeline"}


def test_channel_for_unknown_topic_returns_empty():
    assert channel_for_topic("some.unregistered.topic") == []


def test_all_topics_is_union_of_channels_minus_synthetic():
    # Sprint Q.14.B — synthetic topics (e.g. RULE_FIRING_PROPOSED) come
    # from pg_notify, not Kafka. They live in the channel map (so SSE
    # subscribers can ask for them) but are excluded from `all_topics()`
    # so the Kafka consumer doesn't try to subscribe to a non-existent
    # broker topic.
    from src.shared.realtime.channels import _SYNTHETIC_TOPICS

    union = set()
    for topics in CHANNELS.values():
        union |= topics
    assert all_topics() == union - _SYNTHETIC_TOPICS
