"""Sprint Q.14.B — Postgres NOTIFY listener tests.

Three layers tested:

  1. **Channel mapping** — `rule_firing` channel exists, points at the
     synthetic `RULE_FIRING_PROPOSED` topic, and the topic is excluded
     from `all_topics()` (Kafka consumer doesn't try to subscribe).

  2. **DSN normalisation** — SQLAlchemy's `postgresql+asyncpg://` URL
     prefix is stripped before passing to `asyncpg.connect()`.

  3. **NOTIFY → bridge routing** — `_route_to_bridge` builds an
     envelope in the right shape and calls `RealtimeBridge.emit_for_tests`
     so a subscriber on `?channels=rule_firing` receives it.

  4. **JSON parse failure** — invalid NOTIFY body is logged + dropped
     instead of crashing the listener.

  5. **Tenant isolation** — the bridge's existing tenant filter still
     applies for NOTIFY-sourced events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict
from uuid import UUID

import pytest

from src.shared.kafka_client import Topics
from src.shared.realtime import notify_listener
from src.shared.realtime.bridge import RealtimeBridge
from src.shared.realtime.channels import (
    CHANNELS,
    _SYNTHETIC_TOPICS,
    all_topics,
    is_synthetic_topic,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_OTHER = UUID("22222222-2222-2222-2222-222222222222")


# ───────────────────────────────────────────────────────────────────────────
# Channel mapping — pin the wiring shape
# ───────────────────────────────────────────────────────────────────────────


def test_rule_firing_channel_exists():
    assert "rule_firing" in CHANNELS
    assert Topics.RULE_FIRING_PROPOSED in CHANNELS["rule_firing"]


def test_synthetic_topic_excluded_from_kafka_subscribe():
    """The Kafka consumer must NOT subscribe to RULE_FIRING_PROPOSED —
    it's pushed via pg_notify, and Kafka has no producer for it."""
    assert Topics.RULE_FIRING_PROPOSED in _SYNTHETIC_TOPICS
    assert Topics.RULE_FIRING_PROPOSED not in all_topics()
    assert is_synthetic_topic(Topics.RULE_FIRING_PROPOSED)


def test_non_synthetic_topics_unaffected():
    """Existing channels (alerts, governance, etc.) still surface in
    `all_topics()` — the synthetic exclusion is narrowly scoped."""
    assert Topics.DECISION_PROPOSED in all_topics()
    assert not is_synthetic_topic(Topics.DECISION_PROPOSED)


# ───────────────────────────────────────────────────────────────────────────
# DSN normalisation
# ───────────────────────────────────────────────────────────────────────────


def test_normalise_dsn_strips_async_dialect():
    from src.shared.realtime.notify_listener import _normalise_dsn
    assert _normalise_dsn(
        "postgresql+asyncpg://u:p@h:5432/db"
    ) == "postgresql://u:p@h:5432/db"


def test_normalise_dsn_passes_plain_url_through():
    from src.shared.realtime.notify_listener import _normalise_dsn
    assert _normalise_dsn(
        "postgresql://u:p@h:5432/db"
    ) == "postgresql://u:p@h:5432/db"


def test_normalise_dsn_handles_other_dialect_prefix():
    """psycopg2 / pg8000 prefixes also stripped — the same DSN shape."""
    from src.shared.realtime.notify_listener import _normalise_dsn
    assert _normalise_dsn(
        "postgresql+psycopg2://u:p@h:5432/db"
    ) == "postgresql://u:p@h:5432/db"


# ───────────────────────────────────────────────────────────────────────────
# Routing — NOTIFY body → RealtimeBridge envelope
# ───────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_bridge():
    """Reset the bridge singleton + listener module state between tests."""
    RealtimeBridge.reset_for_tests()
    notify_listener.reset_for_tests()
    yield RealtimeBridge.instance()
    RealtimeBridge.reset_for_tests()
    notify_listener.reset_for_tests()


@pytest.mark.asyncio
async def test_route_to_bridge_pushes_envelope(fresh_bridge):
    """A valid NOTIFY body becomes an envelope on the rule_firing channel.
    Subscribe a fake SSE client and verify it receives the event."""
    sub_id, queue = fresh_bridge.subscribe(
        tenant_id=_TENANT,
        channels=["rule_firing"],
    )

    body = {
        "id": "11111111-2222-3333-4444-555555555555",
        "tenant_id": str(_TENANT),
        "rule_id": "alerts.bottleneck_formation",
        "fired_at": "2026-05-04T12:00:00+00:00",
        "rule_output": {"candidate_count": 3, "fase_ids": ["L1", "L2"]},
        "fire_count": 1,
    }
    await notify_listener._route_to_bridge(body)

    envelope = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert envelope["tenant_id"] == str(_TENANT)
    assert envelope["event_type"] == "rule_firing.proposed"
    assert envelope["payload"]["rule_id"] == "alerts.bottleneck_formation"
    assert envelope["payload"]["rule_output"]["candidate_count"] == 3
    assert envelope["payload"]["fire_count"] == 1
    assert envelope["payload"]["id"] == "11111111-2222-3333-4444-555555555555"

    fresh_bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_route_to_bridge_isolates_tenants(fresh_bridge):
    """Tenant A's NOTIFY must NOT reach tenant B's subscriber."""
    _other_sub, other_queue = fresh_bridge.subscribe(
        tenant_id=_OTHER,
        channels=["rule_firing"],
    )

    body = {
        "id": "...",
        "tenant_id": str(_TENANT),  # NOT _OTHER
        "rule_id": "alerts.bottleneck_formation",
        "fired_at": "2026-05-04T12:00:00+00:00",
        "rule_output": {},
        "fire_count": 1,
    }
    await notify_listener._route_to_bridge(body)

    # Other-tenant queue should remain empty.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(other_queue.get(), timeout=0.2)


@pytest.mark.asyncio
async def test_route_to_bridge_isolates_channels(fresh_bridge):
    """A subscriber on `?channels=alerts` must NOT receive a
    rule_firing envelope — channel scoping respected for NOTIFY-sourced
    events same as Kafka-sourced ones."""
    sub_id, queue = fresh_bridge.subscribe(
        tenant_id=_TENANT,
        channels=["alerts"],
    )

    body = {
        "id": "...",
        "tenant_id": str(_TENANT),
        "rule_id": "improve.generate_via_llm",
        "fired_at": "2026-05-04T12:00:00+00:00",
        "rule_output": {},
        "fire_count": 1,
    }
    await notify_listener._route_to_bridge(body)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.2)

    fresh_bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_route_to_bridge_drops_payload_without_tenant(fresh_bridge, caplog):
    """A malformed NOTIFY body (no tenant_id) is dropped silently —
    can't fan-out without it because the bridge enforces tenant scope."""
    sub_id, queue = fresh_bridge.subscribe(
        tenant_id=_TENANT,
        channels=["rule_firing"],
    )

    body = {
        "id": "...",
        "rule_id": "alerts.bottleneck_formation",
        # tenant_id intentionally missing
        "fired_at": "2026-05-04T12:00:00+00:00",
        "rule_output": {},
        "fire_count": 1,
    }
    with caplog.at_level(logging.DEBUG, logger="src.shared.realtime.notify_listener"):
        await notify_listener._route_to_bridge(body)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.2)

    fresh_bridge.unsubscribe(sub_id)


# ───────────────────────────────────────────────────────────────────────────
# JSON parse failure path
# ───────────────────────────────────────────────────────────────────────────


def test_on_notify_logs_and_drops_invalid_json(caplog):
    """asyncpg invokes _on_notify with a payload string. Bad JSON
    must be logged + dropped, never crash the listener."""
    with caplog.at_level(logging.WARNING, logger="src.shared.realtime.notify_listener"):
        notify_listener._on_notify(
            connection=None, pid=0, channel="rule_firing",
            payload="not valid json{",
        )
    assert any(
        "invalid JSON" in rec.message for rec in caplog.records
    )


def test_on_notify_ignores_other_channels():
    """The listener subscribes to one channel; if asyncpg ever fires
    the callback for a different channel (paranoid guard) we should
    drop silently."""
    notify_listener._on_notify(
        connection=None, pid=0, channel="some_other_channel",
        payload='{"tenant_id":"..."}',
    )
    # Asserting "no exception raised" — implicit pass.


# ───────────────────────────────────────────────────────────────────────────
# Lifecycle — start when asyncpg/PG unreachable should fail gracefully
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_returns_false_when_database_url_missing(monkeypatch):
    """No DATABASE_URL → listener returns False, no crash. Caller
    (lifespan) logs + continues."""
    notify_listener.reset_for_tests()

    from src.shared import config as cfg
    monkeypatch.setattr(cfg.settings, "database_url", "", raising=False)

    result = await notify_listener.start_notify_listener()
    assert result is False
    # Idempotent: second call should also stay false.
    assert await notify_listener.start_notify_listener() is False
