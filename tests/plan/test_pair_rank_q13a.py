"""Sprint Q.13.A — `rank_pairs()` regression test.

Plan v4 §6.2 promises "Paulo+Maria (8.2) OU João+Ana (6.1)". The
backend that powers this UX is `rank_pairs(op, state, top_n=3)`.
These tests pin its contract:

  * Returns empty list for ops that don't need a pair
  * Returns up to N tuples ordered by ascending cost (score desc)
  * Scores are 0-10, rounded to 0.1
  * Empty pool / single worker → empty list (caller falls back to solo UI)
"""

from __future__ import annotations

from typing import Set
from uuid import uuid4

from src.plan.cpo.pair_assignment import rank_pairs
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingOperation


class _StubState:
    """Tiny FactoryState replacement so the test doesn't need to load
    a real DB. `rank_pairs` only touches `PAIR_REQUIRED_PHASES`,
    `PAIR_PREFERRED_PHASES`, and `workers_for(phase_id)`."""

    PAIR_REQUIRED_PHASES = ("LAMINAGEM",)
    PAIR_PREFERRED_PHASES = ("LAMINAGEM",)

    def __init__(self, pool):
        self._pool: Set[str] = set(pool)

    def workers_for(self, phase_id: str):
        return self._pool


def _op(phase_id="LAMINAGEM"):
    return SchedulingOperation(
        operation_id=str(uuid4()),
        order_id="OF-1",
        product_id="K1",
        sequence=1,
        operation_code=phase_id,
        duration_minutes=240.0,
        machine_id=None,
        phase_id=phase_id,
    )


def test_returns_empty_when_phase_does_not_need_pair():
    """Non-pair phases (e.g. CURA) get empty list — caller falls back
    to single-worker UX."""
    state = _StubState({"w1", "w2", "w3"})
    op = _op(phase_id="CURA")  # not in pair phases
    assert rank_pairs(op, state) == []


def test_returns_empty_when_pool_too_small():
    state = _StubState({"w1"})  # only 1 worker
    op = _op()
    assert rank_pairs(op, state) == []


def test_returns_top_n_pairs_for_paired_phase():
    state = _StubState({f"w{i}" for i in range(1, 6)})  # 5 workers
    op = _op()
    pairs = rank_pairs(op, state, top_n=3)
    assert len(pairs) == 3
    # Each entry has the expected shape
    for p in pairs:
        assert "chefe_id" in p and "partner_id" in p
        assert "score" in p and isinstance(p["score"], float)
        assert 0.0 <= p["score"] <= 10.0


def test_pairs_sorted_descending_by_score():
    """First pair has the highest score (lowest cost) — that's the UX
    contract: top of the list is the best alternative."""
    state = _StubState({f"w{i}" for i in range(1, 8)})
    op = _op()
    pairs = rank_pairs(op, state, top_n=5)
    scores = [p["score"] for p in pairs]
    assert scores == sorted(scores, reverse=True)


def test_score_rounded_to_one_decimal():
    """Plan v4 §6.2 example reads "8.2" not "8.234". Operator sees
    one-decimal precision so the spread between alternatives is
    immediately scannable."""
    state = _StubState({f"w{i}" for i in range(1, 6)})
    op = _op()
    pairs = rank_pairs(op, state, top_n=3)
    for p in pairs:
        # Each score should round-trip through one-decimal display.
        assert round(p["score"], 1) == p["score"]


def test_pairs_unique_workers_within_each_pair():
    state = _StubState({f"w{i}" for i in range(1, 6)})
    op = _op()
    pairs = rank_pairs(op, state, top_n=3)
    for p in pairs:
        assert p["chefe_id"] != p["partner_id"]


def test_top_n_clamped_at_pool_size():
    """Asking for top_n=10 from a 3-worker pool returns 3 pairs (3
    choose 2 = 3) and not more."""
    state = _StubState({"a", "b", "c"})
    op = _op()
    pairs = rank_pairs(op, state, top_n=10)
    assert len(pairs) == 3  # C(3, 2)
