"""Sprint D.1 — RealtimeBridge fan-out tests.

These tests use `bridge.emit_for_tests()` to inject envelopes directly
into the fan-out without standing up a real Kafka broker. The lifecycle
(`start`/`stop`) is exercised separately with aiokafka mocked out.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from src.shared.kafka_client import Topics
from src.shared.realtime.bridge import RealtimeBridge


@pytest.fixture(autouse=True)
def _reset_bridge():
    RealtimeBridge.reset_for_tests()
    yield
    RealtimeBridge.reset_for_tests()


@pytest.mark.asyncio
async def test_subscribe_returns_sub_id_and_queue():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    assert isinstance(sub_id, str)
    assert queue.qsize() == 0
    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_fanout_delivers_to_matching_tenant_and_channel():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    envelope = {
        "event_id": str(uuid4()),
        "event_type": "MOLD_MAINT_DUE",
        "tenant_id": str(tenant),
        "source_module": "mold",
        "payload": {"mold_code": "M-K1-06"},
    }
    await bridge.emit_for_tests(envelope, Topics.MOLD_MAINT_DUE)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received["event_type"] == "MOLD_MAINT_DUE"
    assert received["_topic"] == Topics.MOLD_MAINT_DUE
    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_fanout_isolates_tenants():
    """Cross-tenant leakage would be the worst-possible bug in a
    multi-tenant realtime layer. This is the explicit guard test.
    """
    bridge = RealtimeBridge.instance()
    tenant_a = uuid4()
    tenant_b = uuid4()

    sub_a, queue_a = bridge.subscribe(tenant_a, ["alerts"])
    sub_b, queue_b = bridge.subscribe(tenant_b, ["alerts"])

    # Publish for tenant A only.
    envelope = {
        "event_type": "MOLD_MAINT_DUE",
        "tenant_id": str(tenant_a),
        "payload": {},
    }
    await bridge.emit_for_tests(envelope, Topics.MOLD_MAINT_DUE)

    # A receives it.
    received = await asyncio.wait_for(queue_a.get(), timeout=1.0)
    assert received["tenant_id"] == str(tenant_a)

    # B's queue stays empty.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue_b.get(), timeout=0.1)

    bridge.unsubscribe(sub_a)
    bridge.unsubscribe(sub_b)


@pytest.mark.asyncio
async def test_fanout_respects_channel_filter():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    # Subscribe only to alerts, not governance.
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    # A governance event goes out — subscriber should NOT see it.
    envelope = {
        "event_type": "DECISION_EXECUTED",
        "tenant_id": str(tenant),
        "payload": {},
    }
    await bridge.emit_for_tests(envelope, Topics.DECISION_EXECUTED)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.1)

    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_fanout_drops_envelopes_without_tenant_id():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    bad_envelope = {
        "event_type": "MOLD_MAINT_DUE",
        "payload": {},  # no tenant_id
    }
    await bridge.emit_for_tests(bad_envelope, Topics.MOLD_MAINT_DUE)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.1)

    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_fanout_drops_topic_not_in_channel_map():
    """A Kafka message on a topic we don't map to any channel should
    never reach subscribers — defensive against config drift."""
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts", "timeline", "dashboard", "governance"])

    envelope = {
        "event_type": "WHATEVER",
        "tenant_id": str(tenant),
        "payload": {},
    }
    await bridge.emit_for_tests(envelope, "unregistered.topic.foo")

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.1)

    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_queue_full_drops_oldest_and_increments_counter():
    """Slow clients must not balloon bridge memory. When a queue hits
    its cap we drop the oldest envelope and keep streaming."""
    from src.shared.realtime.bridge import SUBSCRIBER_QUEUE_MAX

    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    # Fire maxsize + 5 envelopes without draining the queue.
    for i in range(SUBSCRIBER_QUEUE_MAX + 5):
        await bridge.emit_for_tests(
            {
                "event_type": "MOLD_MAINT_DUE",
                "tenant_id": str(tenant),
                "payload": {"seq": i},
            },
            Topics.MOLD_MAINT_DUE,
        )

    # Queue should cap at maxsize (drop_oldest behaviour).
    assert queue.qsize() == SUBSCRIBER_QUEUE_MAX
    # And the subscription counter reflects the drops.
    sub = bridge._subs[sub_id]
    assert sub.dropped_events > 0

    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_subscribe_unsubscribe_is_idempotent():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, _ = bridge.subscribe(tenant, ["alerts"])

    bridge.unsubscribe(sub_id)
    # Second call is a no-op (shouldn't raise).
    bridge.unsubscribe(sub_id)
    bridge.unsubscribe("some-other-id")


@pytest.mark.asyncio
async def test_snapshot_reports_subscriber_count():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()

    snap = bridge.snapshot()
    assert snap["subscribers"] == 0
    assert snap["started"] is False
    assert snap["healthy"] is False

    sub_id, _ = bridge.subscribe(tenant, ["alerts"])
    assert bridge.snapshot()["subscribers"] == 1
    bridge.unsubscribe(sub_id)
    assert bridge.snapshot()["subscribers"] == 0


@pytest.mark.asyncio
async def test_start_without_aiokafka_logs_and_stays_unhealthy(monkeypatch):
    """If the broker is unreachable `start()` should NOT raise. The
    bridge stays unhealthy; the SSE endpoint then serves a degraded
    heartbeat-only stream (Q.59.A — no longer a 503)."""
    import src.shared.realtime.bridge as bridge_module

    # Force the "aiokafka absent" branch for a deterministic path.
    monkeypatch.setattr(bridge_module, "AIOKAFKA_AVAILABLE", False)

    bridge = RealtimeBridge.instance()
    await bridge.start()

    assert bridge.healthy is False
    # Repeat call is idempotent.
    await bridge.start()
    assert bridge.snapshot()["started"] is True


@pytest.mark.asyncio
async def test_stop_sends_sentinel_to_subscribers(monkeypatch):
    """After shutdown every live subscriber must see a `None` sentinel
    so their endpoint coroutine can close the stream cleanly."""
    import src.shared.realtime.bridge as bridge_module

    monkeypatch.setattr(bridge_module, "AIOKAFKA_AVAILABLE", False)

    bridge = RealtimeBridge.instance()
    await bridge.start()

    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    await bridge.stop()

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received is None


# ---------------------------------------------------------------------------
# Q.17.F.8 — notify_channel: in-process fan-out for the yaml_policy notify
# dispatcher (no Kafka, no topic reverse-lookup).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_channel_delivers_to_matching_subscriber():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["alerts"])

    delivered = await bridge.notify_channel(
        tenant, "alerts", {"rule_id": "r1", "topic": "t", "payload": {"x": 1}},
    )

    assert delivered == 1
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received["rule_id"] == "r1"
    assert received["_channel"] == "alerts"
    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_notify_channel_isolates_tenants():
    bridge = RealtimeBridge.instance()
    tenant_a, tenant_b = uuid4(), uuid4()
    sub_id, queue = bridge.subscribe(tenant_b, ["alerts"])

    delivered = await bridge.notify_channel(tenant_a, "alerts", {"rule_id": "r1"})

    assert delivered == 0
    assert queue.qsize() == 0
    bridge.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_notify_channel_skips_unsubscribed_channel():
    bridge = RealtimeBridge.instance()
    tenant = uuid4()
    sub_id, queue = bridge.subscribe(tenant, ["timeline"])

    delivered = await bridge.notify_channel(tenant, "alerts", {"rule_id": "r1"})

    assert delivered == 0
    assert queue.qsize() == 0
    bridge.unsubscribe(sub_id)
