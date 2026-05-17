"""Unit tests for OEEService — synthetic fixtures, no live DB.

The OEEService takes a `fetcher` callable so tests can inject canned data.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.adapters.nelo.schemas import OperationRow
from src.profit.services.oee_service import (
    DEFAULT_SHIFT_HOURS,
    OEEService,
    _passes_first_time,
    _working_hours_in_period,
)


def _op(
    *,
    op_id: int = 1,
    start: datetime = datetime(2026, 5, 14, 9, 0),
    end: datetime = datetime(2026, 5, 14, 11, 0),
    standard: float = 2.0,
    is_return: bool = False,
    severe: bool = False,
    problem_at: datetime | None = None,
    problem_paint: int | None = None,
    phase_name: str = "Laminagem",
    product_type: str | None = "Canoe Sprint Ep.",
    shift_id: int | None = 1,
    mold_wo: int | None = None,
    automatic: bool = False,
) -> OperationRow:
    return OperationRow(
        operation_id=op_id,
        work_order_id=op_id * 10,
        phase_id=1,
        phase_name=phase_name,
        start_at=start,
        end_at=end,
        expected_at=None,
        standard_time_hours=standard,
        temperature=20.0,
        humidity=50.0,
        problem_neck=None,
        problem_interior_id=None,
        problem_paint_id=problem_paint,
        problem_mold_id=None,
        problem_lamination_id=None,
        problem_logged_at=problem_at,
        is_return=is_return,
        severe_return=severe,
        product_id=100,
        shift_id=shift_id,
        mold_work_order_id=mold_wo,
        product_type_name=product_type,
        phase_is_automatic=automatic,
    )


async def _make_fetcher(ops: list[OperationRow]):
    async def _fetch(date_from, date_to, limit):
        return ops
    return _fetch


# ─── Helpers ────────────────────────────────────────────────────────────


def test_working_hours_excludes_weekend() -> None:
    # 2026-05-11 (Mon) to 2026-05-15 (Fri) = 5 days × 8h
    assert _working_hours_in_period(date(2026, 5, 11), date(2026, 5, 15)) == 40.0
    # 2026-05-11 (Mon) to 2026-05-17 (Sun) = still 5 working days
    assert _working_hours_in_period(date(2026, 5, 11), date(2026, 5, 17)) == 40.0


def test_passes_first_time_strict() -> None:
    assert _passes_first_time(_op()) is True
    assert _passes_first_time(_op(is_return=True)) is False
    assert _passes_first_time(_op(severe=True)) is False
    assert _passes_first_time(_op(problem_at=datetime(2026, 5, 14))) is False
    assert _passes_first_time(_op(problem_paint=3)) is False


# ─── Component math ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_overall_perfect_factory() -> None:
    """Standard=Actual=2h, no problems → OEE = 1.0 × ? × 1.0.

    Availability won't be 1.0 because synthetic ops total 2h but planned
    is 40h (5 working days). We assert each component instead.
    """
    ops = [_op(op_id=i, standard=2.0) for i in range(1, 11)]  # 10 × 2h = 20h
    svc = OEEService(fetcher=await _make_fetcher(ops))
    result = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15))

    assert result.overall.sample_size == 10
    assert result.overall.quality == pytest.approx(1.0)
    assert result.overall.performance == pytest.approx(1.0)
    # 20 actual / 40 planned = 0.5
    assert result.overall.availability == pytest.approx(0.5)
    assert result.overall.oee == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_quality_drops_with_returns() -> None:
    ops = [_op(op_id=i) for i in range(1, 9)]  # 8 ok
    ops += [_op(op_id=9, is_return=True), _op(op_id=10, problem_paint=1)]
    svc = OEEService(fetcher=await _make_fetcher(ops))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15))
    assert r.overall.quality == pytest.approx(0.8)  # 8/10


@pytest.mark.asyncio
async def test_performance_excludes_outliers() -> None:
    # 5 normal (2h actual / 2h standard) + 1 outlier (50h actual / 2h standard)
    ops = [_op(op_id=i) for i in range(1, 6)]
    ops.append(
        _op(
            op_id=99,
            start=datetime(2026, 5, 14, 0, 0),
            end=datetime(2026, 5, 16, 2, 0),  # 50 hours
            standard=2.0,
        )
    )
    svc = OEEService(fetcher=await _make_fetcher(ops))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15))
    assert r.overall.sample_excluded == 1
    # Performance only sees 5 normal ops, perfect 1:1
    assert r.overall.performance == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_performance_skips_automatic_phases() -> None:
    # Cura (automatic) shouldn't drag Performance down even if "slow"
    ops = [
        _op(op_id=1, standard=2.0),
        _op(
            op_id=2,
            start=datetime(2026, 5, 14, 0, 0),
            end=datetime(2026, 5, 14, 16, 0),  # 16h actual vs 2h standard
            standard=2.0,
            automatic=True,
            phase_name="Cura",
        ),
    ]
    svc = OEEService(fetcher=await _make_fetcher(ops))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15))
    # Performance based only on op 1 (op 2 is automatic, skipped)
    assert r.overall.performance == pytest.approx(1.0)
    # But Availability includes both
    assert r.overall.sample_size == 2


@pytest.mark.asyncio
async def test_oee_composition() -> None:
    """OEE = Availability × Performance × Quality (within 1e-6)."""
    ops = [_op(op_id=i) for i in range(1, 11)]
    ops.append(_op(op_id=11, is_return=True))  # quality < 1
    svc = OEEService(fetcher=await _make_fetcher(ops))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15))
    expected = r.overall.availability * r.overall.performance * r.overall.quality
    assert r.overall.oee == pytest.approx(expected, abs=1e-9)


@pytest.mark.asyncio
async def test_group_by_phase_sorts_worst_first() -> None:
    ops = [
        _op(op_id=1, phase_name="A"),
        _op(op_id=2, phase_name="A"),
        _op(op_id=3, phase_name="B", is_return=True),  # B has lower Quality
        _op(op_id=4, phase_name="B"),
    ]
    svc = OEEService(fetcher=await _make_fetcher(ops))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15), group_by="phase")
    assert len(r.breakdown) == 2
    # B has worse OEE → sorted first
    assert r.breakdown[0].group_value == "B"
    assert r.breakdown[1].group_value == "A"
    assert r.breakdown[0].oee < r.breakdown[1].oee


@pytest.mark.asyncio
async def test_group_by_product_type_alphabetical() -> None:
    ops = [
        _op(op_id=1, product_type="Canoe Sprint Ep."),
        _op(op_id=2, product_type="Canoe Marathon"),
        _op(op_id=3, product_type=None),
    ]
    svc = OEEService(fetcher=await _make_fetcher(ops))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15), group_by="product_type")
    values = [b.group_value for b in r.breakdown]
    # alphabetical: Canoe Marathon, Canoe Sprint Ep., Other
    assert values == ["Canoe Marathon", "Canoe Sprint Ep.", "Other"]


@pytest.mark.asyncio
async def test_empty_data_returns_zeros() -> None:
    svc = OEEService(fetcher=await _make_fetcher([]))
    r = await svc.calculate(date(2026, 5, 11), date(2026, 5, 15))
    assert r.overall.sample_size == 0
    assert r.overall.oee == 0.0


@pytest.mark.asyncio
async def test_invalid_date_range_raises() -> None:
    svc = OEEService(fetcher=await _make_fetcher([]))
    with pytest.raises(ValueError):
        await svc.calculate(date(2026, 5, 15), date(2026, 5, 11))
