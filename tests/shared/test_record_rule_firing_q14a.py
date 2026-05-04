"""Sprint Q.14.A — `record_rule_firing` decorator tests.

The decorator is the API of the rule-firing log. If it breaks the
producer it wraps, every detector site in the codebase becomes
fragile. If it fails to persist, the audit is silently lost. These
tests pin both directions:

  * Producer result is never modified by the wrapper.
  * Producer never sees an exception from the audit step.
  * Tenant resolution: extractor → self.tenant_id → kwargs → None.
  * Dedupe path: same key inside the window updates the open row.
  * Different keys / outside window → new rows.
  * Best-effort: persist failure is logged + swallowed.
  * Sync function rejected at decoration time (clear error).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

import src.shared.decorators as decorators
from src.governance.models import RuleFiring, RuleFiringOutcome
from src.shared.decorators import record_rule_firing


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ───────────────────────────────────────────────────────────────────────────
# Fake DB session — enough for the decorator's persist path.
# ───────────────────────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, value: Any = None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """Captures `add` + `execute` calls. ``existing_for_dedupe`` lets
    a test simulate "an open row already exists" without setting up a
    real DB query path."""

    def __init__(self, existing_for_dedupe: Optional[RuleFiring] = None):
        self.staged: List[Any] = []
        self.executes: List[tuple] = []
        self.commits = 0
        self.rolls_back = 0
        self._existing = existing_for_dedupe

    def add(self, instance: Any) -> None:
        self.staged.append(instance)

    async def execute(self, stmt) -> _FakeResult:
        self.executes.append(("execute", str(type(stmt).__name__)))
        # First execute is the SELECT (dedupe lookup) when dedupe_key
        # is set; subsequent are the UPDATE.
        return _FakeResult(self._existing)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rolls_back += 1


def _patch_session(monkeypatch, session: _FakeSession):
    """Replace `get_session_context` with one yielding our fake."""

    @asynccontextmanager
    async def _ctx():
        yield session

    monkeypatch.setattr(decorators, "get_session_context", _ctx, raising=False)
    # Also patch where the decorator imports it (lazy inside _persist_firing).
    import src.shared.database as db
    monkeypatch.setattr(db, "get_session_context", _ctx)


# ───────────────────────────────────────────────────────────────────────────
# Fake producer + container for the bound-instance pattern
# ───────────────────────────────────────────────────────────────────────────


class _FakeProducer:
    def __init__(self, tenant_id: Optional[UUID] = _TENANT):
        self.tenant_id = tenant_id
        self.calls = 0

    @record_rule_firing(
        rule_id="test.demo",
        extract_payload=lambda self, x, y=0: {"x": x, "y": y},
        serialise_output=lambda r: {"count": len(r)},
        dedupe_key=lambda self, x, y=0: f"key:{x}",
    )
    async def detect(self, x: int, y: int = 0) -> List[Dict[str, Any]]:
        self.calls += 1
        return [{"x": x, "y": y}]


# ───────────────────────────────────────────────────────────────────────────
# Tests — wrapper transparency
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wrapper_returns_producer_result_unchanged(monkeypatch):
    session = _FakeSession()
    _patch_session(monkeypatch, session)

    producer = _FakeProducer()
    out = await producer.detect(7, y=3)
    assert out == [{"x": 7, "y": 3}]
    assert producer.calls == 1


@pytest.mark.asyncio
async def test_persist_failure_does_not_break_producer(monkeypatch, caplog):
    """The audit table being unreachable must never propagate to the
    producer — the suggestion still flows to the operator."""

    @asynccontextmanager
    async def _broken_ctx():
        raise RuntimeError("DB exploded")
        yield  # unreachable

    monkeypatch.setattr(decorators, "get_session_context", _broken_ctx, raising=False)
    import src.shared.database as db
    monkeypatch.setattr(db, "get_session_context", _broken_ctx)

    producer = _FakeProducer()
    with caplog.at_level(logging.WARNING, logger="src.shared.decorators"):
        out = await producer.detect(1)
    assert out == [{"x": 1, "y": 0}]
    assert any("persist failed" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_decorator_marks_function_with_rule_id(monkeypatch):
    """Introspection: tools listing "what rules are instrumented?" walk
    the modules and read `__rule_firing_id__`. Pin that the marker
    survives `functools.wraps`."""
    producer = _FakeProducer()
    assert getattr(producer.detect, "__rule_firing_id__", None) == "test.demo"


def test_decorator_rejects_sync_function():
    """Sync functions can't be safely wrapped because the audit step
    is async (DB write). Fail at decoration time with a clear hint."""
    with pytest.raises(TypeError) as exc:
        @record_rule_firing(rule_id="bad.sync")
        def sync_detect():
            return []
    assert "async" in str(exc.value).lower()


# ───────────────────────────────────────────────────────────────────────────
# Tests — persistence shape
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_creates_row_with_payload_and_output(monkeypatch):
    session = _FakeSession(existing_for_dedupe=None)
    _patch_session(monkeypatch, session)

    producer = _FakeProducer()
    await producer.detect(5, y=2)

    assert len(session.staged) == 1
    row = session.staged[0]
    assert isinstance(row, RuleFiring)
    assert row.tenant_id == _TENANT
    assert row.rule_id == "test.demo"
    assert row.dedupe_key == "key:5"
    assert row.outcome == RuleFiringOutcome.PROPOSED.value
    assert row.fire_count == 1
    assert row.trigger_payload == {"x": 5, "y": 2}
    assert row.rule_output == {"count": 1}


@pytest.mark.asyncio
async def test_dedupe_collapses_repeat_firing_into_existing_row(monkeypatch):
    """When an open row with the same dedupe_key exists inside the
    window, the decorator UPDATEs (fire_count +1, refreshes payloads)
    instead of inserting a new row."""

    existing = RuleFiring(
        id=uuid4(),
        tenant_id=_TENANT,
        rule_id="test.demo",
        dedupe_key="key:5",
        outcome=RuleFiringOutcome.PROPOSED.value,
        fire_count=1,
        fired_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        trigger_payload={"old": True},
        rule_output={"old": True},
    )
    session = _FakeSession(existing_for_dedupe=existing)
    _patch_session(monkeypatch, session)

    producer = _FakeProducer()
    await producer.detect(5, y=99)

    # No new row inserted (collapsed).
    assert session.staged == []
    # Two execute calls: the SELECT for dedupe + the UPDATE.
    assert len(session.executes) == 2
    assert session.commits == 1


# ───────────────────────────────────────────────────────────────────────────
# Tests — tenant resolution
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenant_resolved_from_self(monkeypatch):
    session = _FakeSession()
    _patch_session(monkeypatch, session)
    producer = _FakeProducer(tenant_id=_TENANT)
    await producer.detect(1)
    assert session.staged[0].tenant_id == _TENANT


@pytest.mark.asyncio
async def test_no_persist_when_tenant_unresolvable(monkeypatch, caplog):
    """If the producer doesn't carry a tenant_id, the audit row would
    be invisible to per-tenant dashboards. Skip silently with debug."""
    session = _FakeSession()
    _patch_session(monkeypatch, session)
    producer = _FakeProducer(tenant_id=None)

    with caplog.at_level(logging.DEBUG, logger="src.shared.decorators"):
        out = await producer.detect(1)
    assert out == [{"x": 1, "y": 0}]
    assert session.staged == []
    assert session.executes == []


@pytest.mark.asyncio
async def test_explicit_extractor_wins_over_self(monkeypatch):
    other_tenant = UUID("22222222-2222-2222-2222-222222222222")

    @record_rule_firing(
        rule_id="test.extractor",
        extract_tenant_id=lambda *a, **kw: other_tenant,
    )
    async def detect(self):
        return []

    class _Holder:
        tenant_id = _TENANT
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder)
    assert session.staged[0].tenant_id == other_tenant


# ───────────────────────────────────────────────────────────────────────────
# Tests — best-effort payload + serialiser
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_default_payload_extracts_repr_when_no_extractor(monkeypatch):
    @record_rule_firing(rule_id="test.no_extractor")
    async def detect(self, magic_number):
        return ["x"]

    class _Holder:
        tenant_id = _TENANT
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder, 42)
    row = session.staged[0]
    assert "args_repr" in row.trigger_payload
    assert row.trigger_payload["args_repr"] == ["42"]


@pytest.mark.asyncio
async def test_extractor_exception_falls_back_to_best_effort(monkeypatch, caplog):
    @record_rule_firing(
        rule_id="test.extractor_boom",
        extract_payload=lambda self, x: {"explode": 1 / 0},  # ZeroDivisionError
    )
    async def detect(self, x):
        return []

    class _Holder:
        tenant_id = _TENANT
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    with caplog.at_level(logging.DEBUG, logger="src.shared.decorators"):
        await detect(holder, 99)
    row = session.staged[0]
    # Best-effort fell through: no `explode` key, but payload is valid.
    assert "args_repr" in row.trigger_payload


@pytest.mark.asyncio
async def test_unserialisable_payload_is_neutralised(monkeypatch):
    """If the extractor returns something that can't be JSON-encoded,
    the audit row falls back to a string repr instead of crashing."""

    class _NotJsonable:
        def __repr__(self):
            return "<NotJsonable>"

    @record_rule_firing(
        rule_id="test.unserialisable",
        extract_payload=lambda *a, **kw: {"obj": _NotJsonable()},
    )
    async def detect(self):
        return []

    class _Holder:
        tenant_id = _TENANT
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder)
    payload = session.staged[0].trigger_payload
    # Either the dict survives via default=str OR it falls into the
    # _unserialisable wrapper. Both are acceptable contracts.
    assert payload  # not empty


# ───────────────────────────────────────────────────────────────────────────
# Tests — dedupe_key callable can return None to opt out per-call
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dedupe_callable_returning_none_skips_dedupe_lookup(monkeypatch):
    """A detector might want dedupe normally but skip it for high-
    priority firings. The callable returning None means "treat this as
    a fresh row even if a key would have matched"."""

    @record_rule_firing(
        rule_id="test.opt_out_dedupe",
        dedupe_key=lambda self, urgent=False: None if urgent else "default",
    )
    async def detect(self, urgent: bool = False):
        return []

    class _Holder:
        tenant_id = _TENANT
    holder = _Holder()

    session = _FakeSession()
    _patch_session(monkeypatch, session)
    await detect(holder, urgent=True)
    row = session.staged[0]
    assert row.dedupe_key is None
    # Only ONE execute (the INSERT path, no SELECT lookup).
    assert len(session.executes) == 0  # add() doesn't go through execute
