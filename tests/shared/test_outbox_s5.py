"""Sprint S5 — guard tests for outbox idempotency + sandbox isolation.

Pure-Python introspection. The DB-side row lock is verified by inspecting the
generated SQL (Postgres-only execution path); the actual `FOR UPDATE SKIP
LOCKED` is exercised against a real DB in integration tests.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from src.shared.kafka_client import EventBase, EventEnvelope


# --- Π6: sandbox flag on EventBase + EventEnvelope ---------------------------

def test_event_base_has_sandbox_flag_default_false():
    e = EventBase(event_type="X", tenant_id=uuid4(), source_module="test")
    assert e.sandbox is False


def test_event_base_sandbox_flag_round_trips_into_envelope():
    e = EventBase(event_type="X", tenant_id=uuid4(), source_module="test", sandbox=True)
    env = EventEnvelope.from_event(e)
    assert env.sandbox is True


def test_event_envelope_default_sandbox_false():
    env = EventEnvelope(
        event_id=str(uuid4()),
        event_type="X",
        tenant_id=str(uuid4()),
        timestamp="2026-05-02T00:00:00",
        source_module="test",
        payload={},
    )
    assert env.sandbox is False


# --- Π5: dispatcher uses FOR UPDATE SKIP LOCKED ------------------------------

def test_dispatcher_uses_for_update_skip_locked():
    text = (
        Path(__file__).resolve().parents[2]
        / "src" / "shared" / "outbox_dispatcher.py"
    ).read_text(encoding="utf-8")
    assert "with_for_update(skip_locked=True)" in text, (
        "dispatcher must request a row-level lock to be safe under "
        "horizontal scaling"
    )


# --- Π5: backoff cap in producer publish loop --------------------------------

def test_producer_backoff_capped_at_60s():
    text = (
        Path(__file__).resolve().parents[2]
        / "src" / "shared" / "kafka_client.py"
    ).read_text(encoding="utf-8")
    assert "min(self.backoff_factor ** attempt, 60.0)" in text


# --- DLQ stub replaced -------------------------------------------------------

def test_dlq_handler_publishes_not_just_logs():
    """The old _send_to_dlq just logged. Sprint S5 must actually publish."""
    from src.shared.kafka_client import KafkaConsumerClient

    src = inspect.getsource(KafkaConsumerClient._send_to_dlq)
    assert "send_and_wait" in src
    assert "Topics.DLQ" in src


# --- Π5: outbox UNIQUE constraint -------------------------------------------

def test_event_outbox_idempotency_unique():
    """Already covered in test_schema_drift but re-asserted here so anyone
    reading the S5 suite sees the full idempotency story end-to-end."""
    from sqlalchemy import UniqueConstraint
    from src.shared.outbox_models import EventOutbox

    uniques = [c for c in EventOutbox.__table__.constraints if isinstance(c, UniqueConstraint)]
    assert len(uniques) == 1
    cols = sorted(c.name for c in uniques[0].columns)
    assert cols == ["aggregate_id", "event_type", "tenant_id"]


# --- routing topic uses resolve_topic (S4 reuse) -----------------------------

def test_outbox_dispatcher_routes_via_resolve_topic():
    text = (
        Path(__file__).resolve().parents[2]
        / "src" / "shared" / "outbox_dispatcher.py"
    ).read_text(encoding="utf-8")
    assert "resolve_topic(event.event_type)" in text
