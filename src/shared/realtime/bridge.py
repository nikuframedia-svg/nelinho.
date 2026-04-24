"""
ProdPlan ONE — RealtimeBridge (Sprint D.1)
=============================================

Pulls Kafka envelopes off every topic registered in `channels.py` and
fans them out to connected SSE subscribers, filtered by
(tenant_id, channel). One singleton instance per process.

Design notes:

* **Own AIOKafkaConsumer** instead of reusing `KafkaConsumerClient`.
  The stock client dispatches by `event_type` string and requires
  per-type registration; we want "every message on these topics" with
  zero ceremony. Cleaner to run our own consume loop.

* **Per-subscriber bounded queue** (`maxsize=100`). If a slow browser
  piles up we drop the oldest event (log once, keep streaming) rather
  than ballooning memory.

* **Tenant isolation** — every subscriber declares its tenant_id and
  the fan-out only pushes envelopes where `envelope["tenant_id"]`
  matches. Cross-tenant leakage is the biggest risk in a multi-tenant
  realtime layer; test 1 covers it explicitly.

* **Graceful degradation** — if Kafka is unreachable (dev without
  docker, or prod outage), `start()` logs a warning and leaves
  `healthy=False`. The SSE endpoint answers 503 in that state. Caller
  fallback: polling via TanStack Query.

Usage:

    bridge = RealtimeBridge.instance()
    await bridge.start()

    sub_id, queue = bridge.subscribe(tenant_id, channels=["alerts"])
    try:
        async for envelope in _consume_queue(queue):
            yield envelope
    finally:
        bridge.unsubscribe(sub_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

try:  # pragma: no cover — optional in dev
    from aiokafka import AIOKafkaConsumer

    AIOKAFKA_AVAILABLE = True
except ImportError:  # pragma: no cover
    AIOKafkaConsumer = None  # type: ignore[assignment]
    AIOKAFKA_AVAILABLE = False

from src.shared.config import settings
from src.shared.realtime.channels import all_topics, channel_for_topic

logger = logging.getLogger(__name__)


# Per-subscriber queue size. SSE clients that can't keep up see the
# oldest events dropped (logged once per subscriber) rather than the
# bridge ballooning memory.
SUBSCRIBER_QUEUE_MAX = 100

# Consumer group id — intentionally NOT per-instance. In a single-
# worker deploy (the NELO target) every bridge gets every message and
# distributes to its own subscribers; that's what we want.
CONSUMER_GROUP_ID = "prodplan-realtime-bridge"


@dataclass
class Subscription:
    """One SSE client's worth of state."""

    sub_id: str
    tenant_id: UUID
    channels: Set[str]
    queue: asyncio.Queue
    connected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    dropped_events: int = 0


class RealtimeBridge:
    """Kafka → per-subscriber queue fan-out. Singleton per process."""

    _instance: Optional["RealtimeBridge"] = None

    @classmethod
    def instance(cls) -> "RealtimeBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        """Drop the singleton so test fixtures can swap in a fresh one."""
        cls._instance = None

    # ─── Construction ─────────────────────────────────────────────────

    def __init__(self) -> None:
        self._consumer: Any = None
        self._consume_task: Optional[asyncio.Task] = None
        self._subs: Dict[str, Subscription] = {}
        self._healthy: bool = False
        self._started: bool = False
        self._lock = asyncio.Lock()

    # ─── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the consumer + fan-out loop.

        Idempotent. Safe to call from the FastAPI lifespan on every
        reload / autoreload. On Kafka failure, logs + stays unhealthy.
        """
        async with self._lock:
            if self._started:
                return
            self._started = True

            if not AIOKAFKA_AVAILABLE:
                logger.warning(
                    "RealtimeBridge: aiokafka not installed — bridge stays "
                    "unhealthy, SSE endpoints will 503."
                )
                return

            topics = sorted(all_topics())
            try:
                self._consumer = AIOKafkaConsumer(
                    *topics,
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    group_id=CONSUMER_GROUP_ID,
                    # "latest" — we care about live events, not the backlog
                    # that might exist from historical runs.
                    auto_offset_reset="latest",
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    enable_auto_commit=True,
                )
                await self._consumer.start()
                self._consume_task = asyncio.create_task(self._consume_loop())
                self._healthy = True
                logger.info(
                    "RealtimeBridge: started, subscribed to %d topics (%s)",
                    len(topics), CONSUMER_GROUP_ID,
                )
            except Exception as exc:
                logger.warning(
                    "RealtimeBridge: Kafka unreachable (%s); "
                    "bridge stays unhealthy, endpoints will 503", exc,
                )
                self._consumer = None
                self._healthy = False

    async def stop(self) -> None:
        """Stop the consumer + cancel fan-out. Called from lifespan
        shutdown. Idempotent.
        """
        async with self._lock:
            if not self._started:
                return
            self._started = False
            self._healthy = False

            if self._consume_task is not None:
                self._consume_task.cancel()
                try:
                    await self._consume_task
                except asyncio.CancelledError:
                    pass
                except Exception:  # pragma: no cover — defensive
                    logger.exception("RealtimeBridge: consume task failed")
                self._consume_task = None

            if self._consumer is not None:
                try:
                    await self._consumer.stop()
                except Exception:  # pragma: no cover — defensive
                    logger.exception("RealtimeBridge: consumer.stop failed")
                self._consumer = None

            # Wake every subscriber so their endpoint coroutines unwind.
            for sub in list(self._subs.values()):
                await sub.queue.put(None)  # sentinel
            self._subs.clear()

            logger.info("RealtimeBridge: stopped")

    # ─── Subscription API ─────────────────────────────────────────────

    def subscribe(
        self,
        tenant_id: UUID,
        channels: List[str],
    ) -> Tuple[str, asyncio.Queue]:
        """Register a new SSE subscriber. Returns `(sub_id, queue)`.

        The caller awaits `queue.get()` to receive envelopes. When the
        envelope is `None` the bridge is shutting down and the client
        should close the stream cleanly.
        """
        sub_id = str(uuid4())
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
        sub = Subscription(
            sub_id=sub_id,
            tenant_id=tenant_id,
            channels=set(channels),
            queue=queue,
        )
        self._subs[sub_id] = sub
        logger.info(
            "RealtimeBridge: subscribe sub=%s tenant=%s channels=%s "
            "(total_subs=%d)",
            sub_id, tenant_id, sorted(sub.channels), len(self._subs),
        )
        return sub_id, queue

    def unsubscribe(self, sub_id: str) -> None:
        sub = self._subs.pop(sub_id, None)
        if sub is None:
            return
        logger.info(
            "RealtimeBridge: unsubscribe sub=%s tenant=%s dropped=%d "
            "(total_subs=%d)",
            sub_id, sub.tenant_id, sub.dropped_events, len(self._subs),
        )

    # ─── Fan-out ─────────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        """Read every Kafka message and fan it out. Cancelled by stop()."""
        assert self._consumer is not None
        try:
            async for message in self._consumer:
                try:
                    envelope = message.value
                    topic = message.topic
                    await self._fanout(envelope, topic)
                except Exception:  # pragma: no cover — defensive
                    logger.exception(
                        "RealtimeBridge: fan-out failed for topic=%s",
                        getattr(message, "topic", "?"),
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("RealtimeBridge: consume loop crashed")
            self._healthy = False

    async def _fanout(self, envelope: Dict[str, Any], topic: str) -> None:
        """Push envelope to every subscriber whose tenant + channels match."""
        # Envelope was produced by `publish_event` as an EventBase dict.
        # Safe to read .get() — if malformed we skip and log once.
        env_tenant = envelope.get("tenant_id")
        if env_tenant is None:
            logger.debug("RealtimeBridge: envelope missing tenant_id (topic=%s)", topic)
            return

        # Reverse-lookup which channels should receive this topic. Cached
        # list is tiny so recomputing per message is fine.
        receiving_channels = set(channel_for_topic(topic))
        if not receiving_channels:
            # Topic isn't in our channel map — we shouldn't even be
            # subscribed to it. Log once then ignore.
            logger.debug("RealtimeBridge: topic %s not mapped to any channel", topic)
            return

        enriched = dict(envelope)
        enriched["_topic"] = topic

        # Iterate a snapshot so unsubscribe during fan-out doesn't break.
        for sub in list(self._subs.values()):
            if str(sub.tenant_id) != str(env_tenant):
                continue  # tenant isolation
            if sub.channels.isdisjoint(receiving_channels):
                continue  # subscriber didn't ask for this channel
            try:
                sub.queue.put_nowait(enriched)
            except asyncio.QueueFull:
                # Drop oldest to make room, log first drop per subscriber.
                try:
                    _ = sub.queue.get_nowait()
                except asyncio.QueueEmpty:  # pragma: no cover
                    pass
                sub.dropped_events += 1
                if sub.dropped_events == 1:
                    logger.warning(
                        "RealtimeBridge: sub=%s queue full, dropping oldest",
                        sub.sub_id,
                    )
                try:
                    sub.queue.put_nowait(enriched)
                except asyncio.QueueFull:  # pragma: no cover
                    pass

    # ─── Diagnostics ─────────────────────────────────────────────────

    @property
    def healthy(self) -> bool:
        return self._healthy

    def snapshot(self) -> Dict[str, Any]:
        """Observability snapshot — used by /health and tests."""
        return {
            "healthy": self._healthy,
            "started": self._started,
            "subscribers": len(self._subs),
            "total_topics": len(all_topics()),
        }

    # ─── Test helpers ────────────────────────────────────────────────

    async def emit_for_tests(
        self,
        envelope: Dict[str, Any],
        topic: str,
    ) -> None:
        """Directly inject an envelope into the fan-out without Kafka.
        Useful in unit tests where running a real broker is overkill.
        """
        await self._fanout(envelope, topic)
