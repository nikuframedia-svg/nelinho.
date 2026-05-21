"""Q.68.3.2 — Tests for the canonical FakeSession extensions.

Fase A of the FakeSession-consolidation effort adds three opt-in helpers
to the canonical ``FakeSession`` in ``tests/conftest.py`` plus a module-
level ``extract_uuid_params`` utility:

  * ``get(model, pk)`` — AsyncSession.get equivalent backed by a private
    registry populated via ``register_entity``.
  * ``register_entity(model, pk, row)`` — registers a row under
    ``(Model.__name__, str(pk))``.
  * ``queue_batch(rows)`` — multi-batch queue consumed FIFO by
    ``execute()``.
  * ``extract_uuid_params(stmt)`` — extracts UUID strings from a query's
    text and compiled bindparams.

These tests enforce the contract and the back-compat invariant: the
~30 tests that already use the legacy queue API must keep passing.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import bindparam, text

from tests.conftest import FakeSession, extract_uuid_params


# ---------------------------------------------------------------------------
# Fixtures — local stand-in ORM classes (no need to import real models)
# ---------------------------------------------------------------------------


class _Mold:
    """Minimal stand-in for a SQLAlchemy ORM class — only the name matters."""


class _Order:
    pass


# ---------------------------------------------------------------------------
# get() / register_entity() — Q.68.3.2 core helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_registered_entity() -> None:
    """register_entity then get() should round-trip the same object."""
    session = FakeSession()
    mold = _Mold()
    mold_id = uuid4()
    session.register_entity(_Mold, mold_id, mold)

    fetched = await session.get(_Mold, mold_id)

    assert fetched is mold


@pytest.mark.asyncio
async def test_get_returns_none_when_unregistered() -> None:
    """Querying an entity that was never registered yields None."""
    session = FakeSession()

    fetched = await session.get(_Mold, uuid4())

    assert fetched is None


@pytest.mark.asyncio
async def test_register_entity_keys_by_class_name_and_str_pk() -> None:
    """Different pk types (UUID, int, str) collapse onto the same slot
    when their str() representation matches; and a different Model
    namespace is isolated."""
    session = FakeSession()
    pk_uuid = UUID("11111111-2222-3333-4444-555555555555")
    pk_str = str(pk_uuid)

    mold = _Mold()
    session.register_entity(_Mold, pk_uuid, mold)

    # Same string pk under the same model -> same row.
    assert await session.get(_Mold, pk_str) is mold

    # Same string pk under a different model -> miss.
    assert await session.get(_Order, pk_uuid) is None


# ---------------------------------------------------------------------------
# queue_batch() — multi-batch FIFO queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_batch_consumes_fifo() -> None:
    """Each execute() call drains one batch in FIFO order; legacy queue
    takes over once batches are exhausted."""
    session = FakeSession()
    first_batch = ["row-a1", "row-a2"]
    second_batch = ["row-b1"]
    session.queue_batch(first_batch)
    session.queue_batch(second_batch)

    r1 = await session.execute(text("SELECT 1"))
    r2 = await session.execute(text("SELECT 2"))

    assert r1.scalars().all() == first_batch
    assert r2.scalars().all() == second_batch
    # Third execute: both batches drained, fall back to empty legacy queue.
    r3 = await session.execute(text("SELECT 3"))
    assert r3.scalars().all() == []


@pytest.mark.asyncio
async def test_queue_batch_first_element_is_scalar() -> None:
    """A queued batch makes ``scalar_one_or_none()`` return the first row.
    This mirrors how SQLAlchemy materialises a SELECT-with-one-row."""
    session = FakeSession()
    sentinel = object()
    session.queue_batch([sentinel])

    result = await session.execute(text("SELECT x"))

    assert result.scalar_one_or_none() is sentinel
    assert result.scalars().all() == [sentinel]


# ---------------------------------------------------------------------------
# extract_uuid_params — query introspection helper
# ---------------------------------------------------------------------------


def test_extract_uuid_params_finds_uuids_in_bindparams() -> None:
    """A compiled statement with UUID bindparams exposes them via
    extract_uuid_params."""
    u1 = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    u2 = UUID("11111111-2222-3333-4444-555555555555")
    stmt = text("SELECT * FROM t WHERE a = :a AND b = :b").bindparams(
        bindparam("a", str(u1)),
        bindparam("b", str(u2)),
    )

    found = extract_uuid_params(stmt)

    assert str(u1) in found
    assert str(u2) in found


def test_extract_uuid_params_on_plain_string_returns_empty() -> None:
    """Non-compilable inputs (raw strings, ints) just walk the text path;
    a UUID-free string yields []."""
    assert extract_uuid_params("SELECT 1") == []
    assert extract_uuid_params(42) == []


def test_extract_uuid_params_finds_uuid_in_rendered_text() -> None:
    """A UUID-looking string baked into the SQL text is also detected."""
    raw = "SELECT * FROM t WHERE id = 'deadbeef-1111-2222-3333-444455556666'"

    found = extract_uuid_params(raw)

    assert "deadbeef-1111-2222-3333-444455556666" in found


# ---------------------------------------------------------------------------
# Back-compat — legacy queue API must keep working
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_queue_scalars_still_works() -> None:
    """Tests written against Q.61.02 (queue_scalar + queue_scalars) keep
    their semantics unchanged when no batches/entities are populated.

    Note: the legacy queues are independent — each execute() pops one
    from ``_scalar_queue`` AND one from ``_scalars_queue``. So a single
    execute() consumes both."""
    session = FakeSession()
    session.queue_scalar("only-row")
    session.queue_scalars([1, 2, 3])

    result = await session.execute(text("SELECT 1"))

    assert result.scalar_one_or_none() == "only-row"
    assert result.scalars().all() == [1, 2, 3]


@pytest.mark.asyncio
async def test_legacy_add_flush_commit_counters() -> None:
    """Counters tracked since Q.12 (added, flush_calls, commit_calls)
    keep tracking after Q.68.3.2 additions."""
    session = FakeSession()
    obj = object()
    session.add(obj)
    await session.flush()
    await session.commit()

    assert session.added == [obj]
    assert session.flush_calls == 1
    assert session.commit_calls == 1


# ---------------------------------------------------------------------------
# Behavioural flags — raise_on_execute / add_should_raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raise_on_execute_flag() -> None:
    """raise_on_execute=True causes execute() to raise — useful for
    testing error-path branches without spinning up a real DB."""
    session = FakeSession()
    session.raise_on_execute = True

    with pytest.raises(RuntimeError, match="raise_on_execute"):
        await session.execute(text("SELECT 1"))


def test_add_should_raise_flag() -> None:
    """add_should_raise=True causes add() to raise — used by
    tests/copilot/test_causal_runtime_q13d.py."""
    session = FakeSession()
    session.add_should_raise = True

    with pytest.raises(RuntimeError, match="add_should_raise"):
        session.add(object())
