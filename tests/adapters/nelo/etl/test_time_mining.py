"""Q.20.F — historical time-mining tests.

The cleaning maths (``mine_durations`` / ``_percentile`` /
``_mode_or_median`` / ``operation_duration_h``) is pure. The end-to-end
``mirror_time_mining`` runs against the recording fake session (conftest)
with the adapter mocked and routing rows pre-loaded.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from src.adapters.nelo.etl import time_mining as tm_mod
from src.adapters.nelo.etl.time_mining import (
    _mode_or_median,
    _month_windows,
    _percentile,
    mine_durations,
    mirror_time_mining,
    operation_duration_h,
)
from src.adapters.nelo.schemas import OperationRow
from src.plan.models.routing_template import ModelRoutingAssignment, RoutingTemplatePhase

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _op(**kw) -> OperationRow:
    base = dict(
        operation_id=1, work_order_id=5000, phase_id=10, phase_name="Laminagem",
        start_at=datetime(2025, 1, 1, 8, 0), end_at=datetime(2025, 1, 1, 12, 0),
        expected_at=None, standard_time_hours=4.0, temperature=21.0,
        humidity=55.0, problem_neck=None, problem_interior_id=None,
        problem_paint_id=None, problem_mold_id=None, problem_lamination_id=None,
        problem_logged_at=None, is_return=False, severe_return=False,
        product_id=900, shift_id=None, mold_work_order_id=None,
        product_type_name="K1", phase_is_automatic=False,
    )
    base.update(kw)
    return OperationRow(**base)


# ── pure: cleaning maths ──────────────────────────────────────────────────


def test_percentile_basic():
    assert _percentile([1, 2, 3, 4, 5], 50) == 3
    assert _percentile([], 50) == 0.0
    assert _percentile([7], 90) == 7


def test_mode_or_median_prefers_mode():
    assert _mode_or_median([2.0, 2.0, 2.0, 3.0, 9.0]) == 2.0


def test_mode_or_median_falls_back_to_median_when_mode_zero():
    # mode is 0 → fall back to median of the non-zero values.
    assert _mode_or_median([0.0, 0.0, 4.0, 6.0]) == 5.0


def test_mine_durations_removes_zeros_and_outliers():
    # zeros dropped; 100 is above P95 and dropped; mode of {2,2,2,3} = 2.
    result = mine_durations([0, 2, 2, 2, 3, 100])
    assert result is not None
    p50, p90 = result
    assert p50 == 2.0
    assert p90 >= p50            # invariant: p90 never below p50


def test_mine_durations_none_when_no_usable_data():
    assert mine_durations([]) is None
    assert mine_durations([0, 0, 0]) is None


def test_mine_durations_p90_ge_p50_property():
    """Property: p90 >= p50 >= 0 for any random duration sample."""
    rng = random.Random(42)
    for _ in range(80):
        sample = [rng.random() * 20 for _ in range(rng.randint(1, 40))]
        result = mine_durations(sample)
        if result is not None:
            p50, p90 = result
            assert p90 >= p50 >= 0


# ── pure: operation duration ──────────────────────────────────────────────


def test_operation_duration_from_timestamps():
    op = _op(start_at=datetime(2025, 1, 1, 8, 0), end_at=datetime(2025, 1, 1, 11, 30))
    assert operation_duration_h(op) == 3.5


def test_operation_duration_none_when_timestamp_missing():
    assert operation_duration_h(_op(end_at=None)) is None
    assert operation_duration_h(_op(start_at=None)) is None


def test_operation_duration_none_for_nonpositive_span():
    """end before start (bad ERP data) yields no duration, not negative."""
    op = _op(start_at=datetime(2025, 1, 2, 8, 0), end_at=datetime(2025, 1, 1, 8, 0))
    assert operation_duration_h(op) is None


# ── pure: month windows ───────────────────────────────────────────────────


def test_month_windows_cover_the_range_without_overlap():
    windows = _month_windows(date(2025, 1, 1), date(2025, 3, 15))
    assert windows[0][0] == date(2025, 1, 1)
    assert windows[-1][1] == date(2025, 3, 15)
    # contiguous, non-overlapping.
    for (_, end), (start, _) in zip(windows, windows[1:]):
        assert start == end + timedelta(days=1)


# ── end-to-end mirror ─────────────────────────────────────────────────────
# A 5-day window → exactly one month-window → the mocked adapter is
# called once, so read/skip counts are deterministic.

_RECENT = date.today() - timedelta(days=5)


async def test_mirror_time_mining_writes_p50_p90(monkeypatch, recording_session):
    """Pre-load a routing template + assignment, feed operation history,
    assert the mined p50/p90 land on the matching phase row."""
    session = recording_session
    template_id = uuid4()
    # The routing template phase the master mirror (Q.20.B) created — NULL
    # durations until mined.
    phase = RoutingTemplatePhase(
        tenant_id=TENANT, id=uuid4(), template_id=template_id, seq=1,
        phase_id="10", phase_name="Laminagem",
    )
    assignment = ModelRoutingAssignment(
        tenant_id=TENANT, id=uuid4(), model_id="900",
        primary_template_id=template_id,
    )
    session.added.extend([phase, assignment])
    assert phase.duration_p50_h is None

    # Product 900 → template; phase 10; three 4h ops.
    day = datetime.combine(_RECENT, datetime.min.time())
    monkeypatch.setattr(
        tm_mod.services, "list_operations",
        AsyncMock(return_value=[
            _op(operation_id=1, product_id=900, phase_id=10,
                start_at=day.replace(hour=8), end_at=day.replace(hour=12)),
            _op(operation_id=2, product_id=900, phase_id=10,
                start_at=day.replace(hour=8), end_at=day.replace(hour=12)),
            _op(operation_id=3, product_id=900, phase_id=10,
                start_at=day.replace(hour=8), end_at=day.replace(hour=12)),
        ]),
    )

    result = await mirror_time_mining(
        session=session, tenant_id=TENANT, since=_RECENT,
    )

    assert result.status == "ok"
    # mode of {4,4,4} = 4h.
    assert phase.duration_p50_h is not None
    assert float(phase.duration_p50_h) == 4.0
    assert float(phase.duration_p90_h) >= 4.0
    assert result.rows_updated == 1


async def test_mirror_time_mining_noop_without_templates(monkeypatch, recording_session):
    """No routing templates → nothing to mine into; mirror still ok."""
    monkeypatch.setattr(
        tm_mod.services, "list_operations", AsyncMock(return_value=[]),
    )
    result = await mirror_time_mining(
        session=recording_session, tenant_id=TENANT, since=_RECENT,
    )
    assert result.status == "ok"
    assert result.rows_updated == 0


async def test_mirror_time_mining_skips_unknown_product(monkeypatch, recording_session):
    """An operation whose product has no routing assignment is skipped —
    no bucket, no junk durations written."""
    session = recording_session
    template_id = uuid4()
    session.added.extend([
        RoutingTemplatePhase(
            tenant_id=TENANT, id=uuid4(), template_id=template_id, seq=1,
            phase_id="10", phase_name="Laminagem",
        ),
        ModelRoutingAssignment(
            tenant_id=TENANT, id=uuid4(), model_id="900",
            primary_template_id=template_id,
        ),
    ])
    monkeypatch.setattr(
        tm_mod.services, "list_operations",
        AsyncMock(return_value=[
            _op(operation_id=1, product_id=777, phase_id=10),   # 777 unknown
        ]),
    )
    result = await mirror_time_mining(
        session=session, tenant_id=TENANT, since=_RECENT,
    )
    assert result.status == "ok"
    assert result.rows_skipped == 1
    assert result.rows_updated == 0
