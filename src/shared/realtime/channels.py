"""
ProdPlan ONE — Realtime channel map (Sprint D.1)
==================================================

Frontend subscribers talk in *channels* (`alerts`, `timeline`,
`dashboard`, `governance`). This module maps each channel to the
concrete Kafka topics the `RealtimeBridge` forwards onto that channel.

Channels intentionally overlap — `timeline` and `governance` both
include the DECISION_* family — so the Gestor's Timeline view and the
audit stream on the admin dashboard can share one Kafka consumer.

Adding a new channel: just extend `CHANNELS`. No DB migration.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Set

from src.shared.kafka_client import Topics


# The canonical channel → topics map. Keep alphabetical by channel name
# so new additions sort deterministically in tests.
CHANNELS: Dict[str, FrozenSet[str]] = {
    "alerts": frozenset({
        Topics.MOLD_MAINT_DUE,
        Topics.MOLD_HEALTH_DEGRADED,
        Topics.MATERIAL_SHORTAGE_DETECTED,
        Topics.CAPACITY_CONSTRAINT_DETECTED,
        Topics.QUALITY_RISK_SCORED,
    }),
    "dashboard": frozenset({
        Topics.SCHEDULE_CREATED,
        Topics.SCHEDULE_UPDATED,
        Topics.COGS_CALCULATED,
        Topics.PRICING_RECOMMENDED,
        Topics.STOCK_ADJUSTED,
        Topics.PRODUCTIVITY_RECORDED,
    }),
    "governance": frozenset({
        Topics.DECISION_PROPOSED,
        Topics.DECISION_APPROVED,
        Topics.DECISION_REJECTED,
        Topics.DECISION_EXECUTED,
        Topics.DECISION_ROLLED_BACK,
    }),
    # Sprint Q.14.B — push reactivo for rule firings the SQL allowlist
    # marked as "spike-detectable". Source is Postgres NOTIFY, not Kafka,
    # but the channel map shape stays uniform so SSE clients subscribe
    # the same way: `?channels=rule_firing`.
    "rule_firing": frozenset({
        Topics.RULE_FIRING_PROPOSED,
    }),
    "timeline": frozenset({
        Topics.DECISION_PROPOSED,
        Topics.DECISION_APPROVED,
        Topics.DECISION_REJECTED,
        Topics.DECISION_EXECUTED,
        Topics.DECISION_ROLLED_BACK,
        Topics.SCHEDULE_CREATED,
        Topics.SCHEDULE_UPDATED,
        Topics.MRP_CALCULATED,
    }),
}


def resolve_topics(channels: List[str]) -> Set[str]:
    """Union of all topics subscribed to by these channels.

    Raises `ValueError` on an unknown channel so callers (the SSE
    endpoint) can answer 400 rather than silently dropping events.
    """
    out: Set[str] = set()
    for name in channels:
        canonical = name.strip().lower()
        if canonical not in CHANNELS:
            raise ValueError(
                f"unknown channel '{name}'. "
                f"available: {sorted(CHANNELS.keys())}"
            )
        out |= CHANNELS[canonical]
    return out


def channel_for_topic(topic: str) -> List[str]:
    """Reverse lookup: given a Kafka topic, which channels would receive
    it? Used by the dispatcher when fanning out an envelope.
    """
    return [name for name, topics in CHANNELS.items() if topic in topics]


# Sprint Q.14.B — synthetic topics aren't Kafka-backed; the
# RealtimeBridge fan-out routes them via the listener path
# (pg_notify → asyncpg listener → bridge.emit_for_tests-style call).
# Excluded from `all_topics()` so the Kafka consumer doesn't try
# to subscribe to a non-existent broker topic.
_SYNTHETIC_TOPICS: FrozenSet[str] = frozenset({
    Topics.RULE_FIRING_PROPOSED,
})


def all_topics() -> Set[str]:
    """Every Kafka topic the bridge needs to subscribe to on startup —
    union across every channel, MINUS synthetic (non-Kafka) topics."""
    out: Set[str] = set()
    for topics in CHANNELS.values():
        out |= topics
    return out - _SYNTHETIC_TOPICS


def is_synthetic_topic(topic: str) -> bool:
    """True if ``topic`` is delivered via a non-Kafka source (e.g. pg_notify).
    Callers that bypass the Kafka consumer use this to guard their feed."""
    return topic in _SYNTHETIC_TOPICS
