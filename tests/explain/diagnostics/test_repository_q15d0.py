"""Sprint Q.15.D.0 — DiagnosticsRepository tests.

Each helper is tested with a fake session that captures statements +
returns canned scalar / row results. We're NOT testing SQL correctness
(that needs an integration DB and is covered by `tests/factory_data_product`);
we ARE testing:

  1. Empty / unreachable curated layer → defensive default (0, [], 0.0).
  2. Composed helpers (`mold_usage`, `phase_error_rate`) call the
     primitive helpers with the right args.
  3. Boats-through-phases set-intersection logic.
  4. WIP queries scope by date correctly via the fake's clause walker.
"""

from __future__ import annotations

from datetime import date
from typing import Any, List
from uuid import UUID

import pytest

from src.explain.diagnostics.repository import DiagnosticsRepository
from src.explain.diagnostics.types import MoldUsage, WorkerStats
from tests.conftest import FakeSession


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ───────────────────────────────────────────────────────────────────────────
# Fake session — minimal enough to drive the repository's queries.
# ───────────────────────────────────────────────────────────────────────────


class _FakeResult:
    """Q.68.3.3 — Light spec for a single ``execute()`` result.

    Holds either a ``value`` (consumed via ``Result.scalar()``) or a
    list of ``rows`` (consumed via ``Result.all()``). The script
    :func:`_repo` then plays each spec into the canonical
    :class:`FakeSession` queues in order.
    """

    def __init__(self, value: Any = None, rows: list = None):
        self.value = value
        self.rows = rows or []


def _repo(results: List[_FakeResult] | None = None) -> DiagnosticsRepository:
    """Q.68.3.3 — Replays a list of :class:`_FakeResult` specs into the
    canonical ``FakeSession`` queues so the repository can execute them
    in order.
    """
    session = FakeSession()
    for spec in results or []:
        # Each execute() call consumes one scalar + one scalars batch.
        # We script both so callers don't need to know which the repo
        # method picks.
        session.queue_scalar(spec.value)
        session.queue_scalars(list(spec.rows))
    return DiagnosticsRepository(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
    )


# ───────────────────────────────────────────────────────────────────────────
# Defensive defaults — empty curated returns sane values
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_molds_active_during_returns_empty_when_no_data():
    repo = _repo([_FakeResult(rows=[])])
    out = await repo.molds_active_during(date(2026, 4, 1), date(2026, 5, 1))
    assert out == []


@pytest.mark.asyncio
async def test_mold_phase_count_returns_zero_on_empty():
    repo = _repo([_FakeResult(value=0)])
    n = await repo.mold_phase_count("M-7", date(2026, 4, 1), date(2026, 5, 1))
    assert n == 0


@pytest.mark.asyncio
async def test_mold_error_count_returns_zero_on_empty():
    repo = _repo([_FakeResult(value=0)])
    n = await repo.mold_error_count("M-7", date(2026, 4, 1), date(2026, 5, 1))
    assert n == 0


@pytest.mark.asyncio
async def test_phase_error_rate_returns_zero_when_total_zero():
    """No phases ran → can't compute rate. Return 0.0, NOT divide-by-zero."""
    repo = _repo([_FakeResult(value=0)])  # phase_total_count → 0
    rate = await repo.phase_error_rate(
        "PHASE_X", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert rate == 0.0


@pytest.mark.asyncio
async def test_phase_error_rate_clamps_to_one():
    """If somehow errors > total (data anomaly), rate caps at 1.0."""
    repo = _repo([
        _FakeResult(value=10),  # phase_total_count
        _FakeResult(value=15),  # phase_error_count (anomalous)
    ])
    rate = await repo.phase_error_rate(
        "PHASE_X", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert rate == 1.0


# ───────────────────────────────────────────────────────────────────────────
# Returns from canned data
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_molds_active_during_returns_distinct_ids():
    rows = [("M-7",), ("M-9",), ("M-7",)]  # SQL DISTINCT already removes dups; sim
    repo = _repo([_FakeResult(rows=rows)])
    out = await repo.molds_active_during(date(2026, 4, 1), date(2026, 5, 1))
    assert out == ["M-7", "M-9", "M-7"]
    # We're not testing SQL DISTINCT (that's the DB's job); we test
    # the repository PASSES THROUGH the rows it receives. Real DB
    # gives distinct.


@pytest.mark.asyncio
async def test_mold_phase_count_returns_scalar():
    repo = _repo([_FakeResult(value=42)])
    n = await repo.mold_phase_count("M-7", date(2026, 4, 1), date(2026, 5, 1))
    assert n == 42


@pytest.mark.asyncio
async def test_mold_error_count_returns_scalar():
    repo = _repo([_FakeResult(value=7)])
    n = await repo.mold_error_count("M-7", date(2026, 4, 1), date(2026, 5, 1))
    assert n == 7


@pytest.mark.asyncio
async def test_mold_error_types_returns_counter():
    rows = [
        ("interior enrugado", 5),
        ("molde baço", 3),
        ("bolhas", 1),
    ]
    repo = _repo([_FakeResult(rows=rows)])
    counter = await repo.mold_error_types(
        "M-7", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert counter["interior enrugado"] == 5
    assert counter["molde baço"] == 3
    assert sum(counter.values()) == 9


@pytest.mark.asyncio
async def test_mold_error_types_filters_null_keys():
    """A NULL erro_tipo from the DB must not become a key in the Counter."""
    rows = [(None, 99), ("real_type", 3)]
    repo = _repo([_FakeResult(rows=rows)])
    counter = await repo.mold_error_types(
        "M-7", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert "real_type" in counter
    assert None not in counter


# ───────────────────────────────────────────────────────────────────────────
# mold_usage composes the primitives
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mold_usage_returns_typed_struct():
    repo = _repo([
        _FakeResult(value=20),  # mold_phase_count
        _FakeResult(value=5),   # mold_error_count
    ])
    usage = await repo.mold_usage(
        "M-7", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert isinstance(usage, MoldUsage)
    assert usage.mold_id == "M-7"
    assert usage.total_phases == 20
    assert usage.error_count == 5
    assert usage.error_rate == 0.25


# ───────────────────────────────────────────────────────────────────────────
# Worker helpers
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workers_active_in_phase_returns_pairs():
    rows = [("w-1", 12), ("w-2", 5), ("w-3", 1)]
    repo = _repo([_FakeResult(rows=rows)])
    out = await repo.workers_active_in_phase(
        "LAMINAGEM", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert out == [("w-1", 12), ("w-2", 5), ("w-3", 1)]


@pytest.mark.asyncio
async def test_workers_active_in_phase_filters_null_worker_id():
    rows = [(None, 99), ("w-real", 5)]
    repo = _repo([_FakeResult(rows=rows)])
    out = await repo.workers_active_in_phase(
        "LAMINAGEM", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert ("w-real", 5) in out
    assert all(w[0] is not None for w in out)


@pytest.mark.asyncio
async def test_worker_phase_stats_returns_typed_struct():
    repo = _repo([
        _FakeResult(value=10),  # allocations
        _FakeResult(value=3),   # errors
    ])
    stats = await repo.worker_phase_stats(
        "w-1", "LAMINAGEM", date(2026, 4, 1), date(2026, 5, 1),
    )
    assert isinstance(stats, WorkerStats)
    assert stats.worker_id == "w-1"
    assert stats.phase_id == "LAMINAGEM"
    assert stats.total_allocations == 10
    assert stats.error_count == 3
    assert stats.error_rate == pytest.approx(0.3)


# ───────────────────────────────────────────────────────────────────────────
# WIP / overload
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_wip_returns_scalar():
    repo = _repo([_FakeResult(value=410)])
    n = await repo.current_wip()
    assert n == 410


@pytest.mark.asyncio
async def test_avg_wip_during_divides_by_window_length():
    """630 overlapping rows over a 7-day window → 90 avg/day."""
    repo = _repo([_FakeResult(value=630)])
    avg = await repo.avg_wip_during(date(2026, 4, 1), date(2026, 4, 8))
    assert avg == pytest.approx(90.0)


@pytest.mark.asyncio
async def test_avg_wip_during_handles_zero_day_window():
    """Defensive: same-day start/end → window of 1 day, no divide-by-zero."""
    repo = _repo([_FakeResult(value=5)])
    avg = await repo.avg_wip_during(date(2026, 4, 1), date(2026, 4, 1))
    assert avg == pytest.approx(5.0)  # divided by max(1, 0) = 1


# ───────────────────────────────────────────────────────────────────────────
# Cross-phase
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_boats_through_phases_returns_intersection():
    """Boats that passed through ALL listed phases. Test 3 phases:
    OF-A in all 3, OF-B in 2 only → only OF-A returned."""
    # Phase 1 → A, B
    # Phase 2 → A, B, C
    # Phase 3 → A, C
    # Intersection: {A}
    repo = _repo([
        _FakeResult(rows=[("OF-A",), ("OF-B",)]),
        _FakeResult(rows=[("OF-A",), ("OF-B",), ("OF-C",)]),
        _FakeResult(rows=[("OF-A",), ("OF-C",)]),
    ])
    out = await repo.boats_through_phases(
        ["P1", "P2", "P3"], date(2026, 4, 1), date(2026, 5, 1),
    )
    assert out == ["OF-A"]


@pytest.mark.asyncio
async def test_boats_through_phases_empty_input_returns_empty():
    repo = _repo([])
    out = await repo.boats_through_phases([], date(2026, 4, 1), date(2026, 5, 1))
    assert out == []


@pytest.mark.asyncio
async def test_phase_precedes_returns_true_when_avg_seq_a_lt_b():
    """LAMINAGEM (avg seq 4) precedes DESMOLDE (avg seq 6)."""
    repo = _repo([
        _FakeResult(value=4.0),  # avg(LAMINAGEM)
        _FakeResult(value=6.0),  # avg(DESMOLDE)
    ])
    assert await repo.phase_precedes("LAMINAGEM", "DESMOLDE") is True


@pytest.mark.asyncio
async def test_phase_precedes_returns_false_when_no_data():
    """When either phase has no avg (NULL → 0), precedes returns False."""
    repo = _repo([
        _FakeResult(value=0),
        _FakeResult(value=0),
    ])
    assert await repo.phase_precedes("UNKNOWN_A", "UNKNOWN_B") is False
