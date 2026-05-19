"""Q.48.B (F10) — factory capacity calendar in FactoryState + decoder.

Covers:
* `FactoryState.is_working_day` — empty calendar means "every day works";
  a populated calendar gates on the set.
* `FactoryState.next_working_day` — walks forward to the first open day.
* `_load_factory_calendar` — best-effort, empty set on a missing table.
* Decoder — an op whose start lands on a closed day is pushed to the next
  working day; the schedule reports `non_working_shifts`.
* Decoder — with an empty calendar (unknown), behaviour is unchanged.

A non-working day is a *capacity* constraint (Spelke axiom 1): the
factory is closed, its capacity is zero, exactly like an operator with
no matching skill is unavailable for a slot (axiom 5).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState, _load_factory_calendar
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation


# ---------------------------------------------------------------------------
# FactoryState.is_working_day / next_working_day
# ---------------------------------------------------------------------------


def test_is_working_day_true_for_any_date_when_calendar_empty():
    """An unknown calendar must NOT block scheduling — every day works."""
    s = FactoryState(tenant_id=uuid4())
    assert s.working_days == set()
    assert s.is_working_day(date(2026, 5, 18)) is True
    assert s.is_working_day(date(2026, 12, 25)) is True


def test_is_working_day_gates_on_populated_calendar():
    s = FactoryState(tenant_id=uuid4())
    s.working_days = {date(2026, 5, 18), date(2026, 5, 19)}
    assert s.is_working_day(date(2026, 5, 18)) is True
    assert s.is_working_day(date(2026, 5, 20)) is False  # not registered


def test_next_working_day_skips_closed_days():
    s = FactoryState(tenant_id=uuid4())
    # Friday open, weekend closed, Monday open.
    s.working_days = {date(2026, 5, 15), date(2026, 5, 18)}
    # Saturday → next working day is Monday.
    assert s.next_working_day(date(2026, 5, 16)) == date(2026, 5, 18)
    # An already-open day is returned unchanged.
    assert s.next_working_day(date(2026, 5, 15)) == date(2026, 5, 15)


def test_next_working_day_noop_when_calendar_empty():
    s = FactoryState(tenant_id=uuid4())
    d = date(2026, 5, 16)
    assert s.next_working_day(d) == d


def test_next_working_day_returns_input_when_no_open_day_in_window():
    """A pathological calendar (only past dates) must not loop forever."""
    s = FactoryState(tenant_id=uuid4())
    s.working_days = {date(2020, 1, 1)}
    d = date(2026, 5, 16)
    # No working day within max_skip → original date returned.
    assert s.next_working_day(d) == d


# ---------------------------------------------------------------------------
# _load_factory_calendar fallback
# ---------------------------------------------------------------------------


def test_load_factory_calendar_without_session_returns_empty():
    assert _load_factory_calendar_sync(None) == set()


def test_load_factory_calendar_with_failing_session_returns_empty():
    class _BoomSession:
        async def execute(self, *_a, **_kw):  # pragma: no cover — exercised
            raise RuntimeError("table does not exist")

    assert _load_factory_calendar_sync(_BoomSession()) == set()


def _load_factory_calendar_sync(session) -> set:
    return asyncio.run(_load_factory_calendar(session, uuid4()))


# ---------------------------------------------------------------------------
# Decoder — closed-day constraint
# ---------------------------------------------------------------------------


def _machine(machine_id: str = "M1") -> SchedulingMachine:
    return SchedulingMachine(machine_id=machine_id, name=machine_id)


def _op(op_id: str, sequence: int, *, duration_minutes: float = 60.0) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=op_id,
        order_id="OF1",
        product_id="P1",
        sequence=sequence,
        operation_code=op_id,
        duration_minutes=duration_minutes,
        machine_id="M1",
        phase_id="MONTAGEM",
    )


def test_decoder_pushes_op_off_closed_day_onto_next_working_day():
    """horizon_start is a Saturday (closed); the op must start on the
    next working day (Monday), not on the closed Saturday."""
    state = FactoryState(tenant_id=uuid4())
    # 2026-05-16 is a Saturday. Mark only the Monday as a working day.
    state.working_days = {date(2026, 5, 18), date(2026, 5, 19)}

    horizon_start = datetime(2026, 5, 16, 8, 0)  # Saturday
    horizon_end = horizon_start + timedelta(days=7)

    op = _op("A", 1)
    result = decode(
        Chromosome(permutation=[0]), [op], [_machine()], state,
        horizon_start, horizon_end,
    )

    scheduled = result["operations"][0]
    start = datetime.fromisoformat(scheduled["start_time"])
    assert start.date() == date(2026, 5, 18), (
        f"op started on a non-working day: {start}"
    )
    assert result["non_working_shifts"] == 1


def test_decoder_keeps_op_on_an_open_horizon_start():
    """When horizon_start is already a working day, nothing shifts."""
    state = FactoryState(tenant_id=uuid4())
    state.working_days = {date(2026, 5, 18), date(2026, 5, 19)}

    horizon_start = datetime(2026, 5, 18, 8, 0)  # Monday — open
    horizon_end = horizon_start + timedelta(days=7)

    op = _op("A", 1)
    result = decode(
        Chromosome(permutation=[0]), [op], [_machine()], state,
        horizon_start, horizon_end,
    )
    start = datetime.fromisoformat(result["operations"][0]["start_time"])
    assert start.date() == date(2026, 5, 18)
    assert result["non_working_shifts"] == 0


def test_decoder_unchanged_when_calendar_empty():
    """No calendar → pre-Q.48 behaviour: the op starts at horizon_start
    even though that date is a Saturday."""
    state = FactoryState(tenant_id=uuid4())
    assert state.working_days == set()

    horizon_start = datetime(2026, 5, 16, 8, 0)  # Saturday
    horizon_end = horizon_start + timedelta(days=7)

    op = _op("A", 1)
    result = decode(
        Chromosome(permutation=[0]), [op], [_machine()], state,
        horizon_start, horizon_end,
    )
    start = datetime.fromisoformat(result["operations"][0]["start_time"])
    assert start.date() == date(2026, 5, 16)  # not shifted
    assert result["non_working_shifts"] == 0
