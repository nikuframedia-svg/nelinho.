"""Q.53.B — property tests for the calendar-aware CPO decoder.

New invariant (Q.53.B): when `FactoryState.calendar` is populated, the
decoder must NOT place a scheduled operation that runs on a non-working
day. Resin cure and weekends are physical — a plan that laminates on a
Sunday cannot exist.

These complement the 7 Spelke axioms; the decoder still honours every
one of them. We also assert the legacy (no-calendar) path is unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from hypothesis import HealthCheck, given, settings, strategies as st

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation
from src.plan.services.factory_calendar import FactoryCalendar

# Monday — a clean working-week start.
HORIZON_START = datetime(2026, 5, 11, 8, 0, 0)
HORIZON_END = HORIZON_START + timedelta(days=60)


def _machines(n=2):
    return [SchedulingMachine(machine_id=f"M{i+1}", name=f"M{i+1}") for i in range(n)]


def _op(op_id, order_id, sequence, duration_min, machine):
    return SchedulingOperation(
        operation_id=op_id,
        order_id=order_id,
        product_id="P1",
        sequence=sequence,
        operation_code="OP",
        duration_minutes=duration_min,
        machine_id=machine,
    )


def _calendar_state() -> FactoryState:
    s = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    s.calendar = FactoryCalendar(default_shift_hours=8.0)
    return s


# ─── Property: no op runs on a non-working day ───────────────────────────


@settings(deadline=None, max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(
    n_ops=st.integers(min_value=1, max_value=6),
    durations=st.lists(
        st.integers(min_value=30, max_value=20 * 60),
        min_size=1, max_size=6,
    ),
)
def test_calendar_decoder_never_schedules_on_weekend(n_ops, durations):
    """For any random op set, with a Mon-Fri calendar attached, every
    scheduled op starts AND ends on a working day."""
    state = _calendar_state()
    ops = [
        _op(f"op{i}", f"O{i}", sequence=1, duration_min=durations[i % len(durations)],
            machine="M1")
        for i in range(n_ops)
    ]
    chromo = Chromosome(permutation=list(range(n_ops)))
    result = decode(chromo, ops, _machines(2), state, HORIZON_START, HORIZON_END)

    cal = state.calendar
    for op in result["operations"]:
        start = datetime.fromisoformat(op["start_time"])
        end = datetime.fromisoformat(op["end_time"])
        assert cal.is_working_day(start.date()), (
            f"op {op['operation_id']} starts on non-working day {start.date()}"
        )
        # The end instant may be exactly the shift end; step back 1s so a
        # boundary end-of-shift doesn't read as the next (off) day.
        end_probe = (end - timedelta(seconds=1)).date()
        assert cal.is_working_day(end_probe), (
            f"op {op['operation_id']} ends on non-working day {end_probe}"
        )


# ─── Property: precedence still holds with the calendar ──────────────────


@settings(deadline=None, max_examples=120)
@given(
    n_phases=st.integers(min_value=2, max_value=5),
    durations=st.lists(
        st.integers(min_value=30, max_value=10 * 60),
        min_size=2, max_size=5,
    ),
)
def test_calendar_decoder_preserves_precedence(n_phases, durations):
    """Spelke axiom 2 — precedence monotonic — must survive the calendar
    walk: phase k+1 starts on/after phase k ends."""
    state = _calendar_state()
    ops = [
        _op(f"o1-s{i}", "O1", sequence=i, duration_min=durations[i % len(durations)],
            machine="M1")
        for i in range(1, n_phases + 1)
    ]
    chromo = Chromosome(permutation=list(range(n_phases)))
    result = decode(chromo, ops, _machines(1), state, HORIZON_START, HORIZON_END)

    by_seq = sorted(result["operations"], key=lambda o: o["operation_id"])
    for prev, nxt in zip(by_seq, by_seq[1:]):
        prev_end = datetime.fromisoformat(prev["end_time"])
        nxt_start = datetime.fromisoformat(nxt["start_time"])
        assert nxt_start >= prev_end, (
            f"precedence broken: {nxt['operation_id']} starts before "
            f"{prev['operation_id']} ends"
        )


# ─── Legacy path unchanged: no calendar → 24/7 behaviour ─────────────────


def test_no_calendar_keeps_legacy_24_7_behaviour():
    """With `calendar=None` the decoder must behave exactly as before —
    a long op can span a weekend without skipping it."""
    state = FactoryState(tenant_id=UUID("11111111-1111-1111-1111-111111111111"))
    assert state.calendar is None
    # Friday start, 48h op — legacy decoder packs it straight through.
    ops = [_op("big", "O1", sequence=1, duration_min=48 * 60, machine="M1")]
    fri_start = datetime(2026, 5, 8, 8, 0)
    result = decode(
        Chromosome(permutation=[0]), ops, _machines(1), state,
        fri_start, fri_start + timedelta(days=10),
    )
    end = datetime.fromisoformat(result["operations"][0]["end_time"])
    # 48h straight from Fri 08:00 → Sun 08:00 (legacy, no skip).
    assert end == fri_start + timedelta(hours=48)
