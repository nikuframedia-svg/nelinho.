"""
ProdPlan ONE — Postgres NOTIFY listener (Sprint Q.14.B)
========================================================

Bridges Postgres ``LISTEN/NOTIFY`` events into the existing
:class:`RealtimeBridge` SSE fan-out. The trigger
``governance.rule_firing → notify_rule_firing()`` (alembic 044) fires
on every allowlisted rule firing; this listener picks up the NOTIFY,
parses the JSON body, builds a SSE-compatible envelope, and routes it
through the bridge with the synthetic topic
``Topics.RULE_FIRING_PROPOSED``.

Why Postgres NOTIFY (not Kafka)
-------------------------------

Three reasons:

1. **Latency** — pg_notify delivers in <5ms intra-DB. Kafka through
   the existing outbox dispatcher polls every 5 seconds.
2. **Operational simplicity** — a single-node NELO deploy already has
   Postgres; adding Kafka for time-sensitive push doubles the moving
   parts.
3. **No new infra** — the existing :class:`RealtimeBridge` already
   fans out to subscribers; this listener just feeds it.

The trade-off: NOTIFY is per-process. With multiple uvicorn workers
each one would consume its own NOTIFY stream, but each only feeds its
own subscribers — so a SSE client connected to worker 1 only gets
events fired against worker 1's DB session. In practice the NELO
deploy runs a single uvicorn worker; multi-worker setups need a Kafka
fanout or a Redis pub/sub bridge as a follow-up.

Lifecycle
---------

``start_notify_listener()`` is called once from
``main.py:lifespan`` startup. It opens a dedicated asyncpg connection
(NOTIFY listening blocks the connection — must NOT use the pooled
session). On shutdown the lifespan calls ``stop_notify_listener()``
which closes the connection cleanly.

Failure mode: if the listener crashes (connection lost, JSON parse
error), it logs and exits. The bridge stays healthy for Kafka events;
just the rule-firing push goes silent until the next process restart.
A reconnect loop is a follow-up if this becomes a real issue.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Strong references to in-flight fan-out tasks. Without this the event
# loop only holds a weak reference and may garbage-collect the task
# mid-flight, silently dropping the rule-firing push (ruff RUF006).
_PENDING_TASKS: "set[asyncio.Task[Any]]" = set()


_PG_NOTIFY_CHANNEL = "rule_firing"


# Module-level state — single listener task per process. The lifespan
# starts/stops it; tests reset via :func:`reset_for_tests`.
_listener_task: Optional[asyncio.Task] = None
_listener_conn: Any = None  # asyncpg.Connection when active
_started: bool = False


async def start_notify_listener() -> bool:
    """Open the dedicated asyncpg connection + register the LISTEN.

    Returns ``True`` when the listener came up cleanly, ``False``
    when asyncpg/Postgres is unreachable or the connection failed.
    Idempotent — calling twice is a no-op.

    The bridge keeps working for Kafka events even when this returns
    False; only the pg_notify push channel goes silent.
    """
    global _listener_task, _listener_conn, _started

    if _started:
        return _listener_task is not None

    _started = True
    try:
        import asyncpg
    except ImportError:
        logger.warning(
            "notify_listener: asyncpg not installed — push channel "
            "rule_firing stays silent. SSE clients on `?channels=rule_firing` "
            "still subscribe but receive nothing until pg_notify wires up.",
        )
        return False

    # Reach into config for the DB URL but normalise asyncio +
    # async dialect prefixes that asyncpg.connect() doesn't accept.
    from src.shared.config import settings

    raw_url = getattr(settings, "database_url", "")
    if not raw_url:
        logger.warning(
            "notify_listener: no database_url configured — skipping",
        )
        return False
    asyncpg_url = _normalise_dsn(raw_url)

    try:
        _listener_conn = await asyncpg.connect(asyncpg_url)
        await _listener_conn.add_listener(
            _PG_NOTIFY_CHANNEL, _on_notify,
        )
    except Exception as exc:
        logger.warning(
            "notify_listener: failed to LISTEN on '%s' (%s) — push "
            "channel stays silent. SSE Kafka events still flow.",
            _PG_NOTIFY_CHANNEL, exc,
        )
        if _listener_conn is not None:
            try:
                await _listener_conn.close()
            except Exception:  # noqa: S110  Q.61.06: close during error path; nothing to do
                pass
        _listener_conn = None
        return False

    # asyncpg's add_listener fires the callback on the connection's
    # internal task; we don't need our own polling task. The
    # _listener_task is just a sentinel for stop().
    _listener_task = asyncio.current_task()
    logger.info(
        "notify_listener: LISTEN '%s' active — rule firings push to SSE",
        _PG_NOTIFY_CHANNEL,
    )
    return True


async def stop_notify_listener() -> None:
    """Close the asyncpg connection. Idempotent."""
    global _listener_task, _listener_conn, _started
    if _listener_conn is not None:
        try:
            await _listener_conn.remove_listener(
                _PG_NOTIFY_CHANNEL, _on_notify,
            )
        except Exception:  # noqa: S110  Q.61.06: teardown best-effort
            pass
        try:
            await _listener_conn.close()
        except Exception:  # noqa: S110  Q.61.06: teardown best-effort
            pass
    _listener_conn = None
    _listener_task = None
    _started = False
    logger.info("notify_listener: stopped")


def _on_notify(connection, pid, channel: str, payload: str) -> None:
    """asyncpg notification callback — parse + route to the bridge.

    Synchronous-looking but asyncpg invokes it from inside its own
    event loop; spawning a task is the right way to do async work here.
    """
    if channel != _PG_NOTIFY_CHANNEL:
        return
    try:
        body = json.loads(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "notify_listener: invalid JSON on channel '%s' (%s); skipping",
            channel, exc,
        )
        return

    # Schedule the async fan-out — the callback itself can't await.
    try:
        task = asyncio.create_task(_route_to_bridge(body))
        _PENDING_TASKS.add(task)
        task.add_done_callback(_PENDING_TASKS.discard)
    except RuntimeError as exc:
        # No running loop in this thread — happens in some test
        # configurations. Log + drop.
        logger.debug("notify_listener: no running loop (%s) — dropping", exc)


async def _route_to_bridge(body: Dict[str, Any]) -> None:
    """Wrap the NOTIFY body in a RealtimeBridge envelope + emit."""
    from src.shared.kafka_client import Topics
    from src.shared.realtime.bridge import RealtimeBridge

    # The fan-out reads `tenant_id` to gate per-subscriber. Required.
    tenant_id = body.get("tenant_id")
    if not tenant_id:
        logger.debug("notify_listener: NOTIFY body missing tenant_id; dropping")
        return

    envelope = {
        "tenant_id": tenant_id,
        "event_type": "rule_firing.proposed",
        "occurred_at": body.get("fired_at") or datetime.now(timezone.utc).isoformat(),
        "payload": {
            "id": body.get("id"),
            "rule_id": body.get("rule_id"),
            "rule_output": body.get("rule_output") or {},
            "fire_count": body.get("fire_count", 1),
        },
    }

    bridge = RealtimeBridge.instance()
    # Reuse the test-helper that goes straight to fan-out — same
    # path Kafka events take after consume.
    await bridge.emit_for_tests(envelope, Topics.RULE_FIRING_PROPOSED)


def _normalise_dsn(url: str) -> str:
    """Strip SQLAlchemy async dialect prefixes so asyncpg.connect()
    accepts the URL.

    SQLAlchemy uses ``postgresql+asyncpg://`` to select the dialect;
    asyncpg's connect() expects plain ``postgresql://`` (or
    ``postgres://``). Same DSN, different schemes — strip the
    ``+asyncpg`` / ``+psycopg2`` etc fragment.
    """
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def reset_for_tests() -> None:
    """Drop module state so tests can re-arm without leaking listeners."""
    global _listener_task, _listener_conn, _started
    _listener_task = None
    _listener_conn = None
    _started = False


__all__ = [
    "reset_for_tests",
    "start_notify_listener",
    "stop_notify_listener",
]
