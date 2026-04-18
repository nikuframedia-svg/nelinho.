"""
Tests for src.plan.cpo.workforce.assign_workers_hungarian.

Scipy is already a Sprint H requirement so this module always has
`SCIPY_AVAILABLE=True` in CI. If that changes, the fallback test still
exercises first-fit identically.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

import pytest

from src.plan.cpo.workforce import (
    SCIPY_AVAILABLE,
    WorkforceRequest,
    _first_fit_fallback,
    assign_workers_hungarian,
)


START = datetime(2026, 4, 20, 8, 0, 0)


def _free_at(**kw) -> Dict[str, datetime]:
    return {w: START + timedelta(minutes=m) for w, m in kw.items()}


class TestAssignWorkersHungarian:
    def test_empty_requests_returns_empty(self):
        assert assign_workers_hungarian([], worker_free_at={}) == {}

    def test_single_op_single_worker(self):
        req = WorkforceRequest(
            operation_id="op1",
            eligible_workers=["W1"],
            team_size=1,
            earliest_start=START,
        )
        result = assign_workers_hungarian([req], worker_free_at=_free_at(W1=0))
        assert result == {"op1": ["W1"]}

    def test_team_size_2_picks_two_distinct_workers(self):
        req = WorkforceRequest(
            operation_id="op1",
            eligible_workers=["W1", "W2", "W3"],
            team_size=2,
            earliest_start=START,
        )
        result = assign_workers_hungarian([req], worker_free_at=_free_at(W1=0, W2=0, W3=120))
        assert len(result["op1"]) == 2
        assert len(set(result["op1"])) == 2  # distinct

    def test_concurrent_ops_no_worker_double_booking(self):
        # Two ops ready at the same time, both need 1 worker, pool of 2
        r1 = WorkforceRequest("o1", ["W1", "W2"], team_size=1, earliest_start=START)
        r2 = WorkforceRequest("o2", ["W1", "W2"], team_size=1, earliest_start=START)
        result = assign_workers_hungarian([r1, r2], worker_free_at=_free_at(W1=0, W2=0))
        workers = result["o1"] + result["o2"]
        # Hungarian must give different workers
        assert len(workers) == 2 and len(set(workers)) == 2

    def test_prefers_earliest_free_worker(self):
        req = WorkforceRequest(
            operation_id="op1",
            eligible_workers=["W1", "W2"],
            team_size=1,
            earliest_start=START,
        )
        # W2 is free NOW, W1 is free in 60 minutes → Hungarian picks W2
        result = assign_workers_hungarian([req], worker_free_at={"W1": START + timedelta(minutes=60), "W2": START})
        assert result == {"op1": ["W2"]}

    def test_affinity_bonus_prefers_preferred_worker(self):
        # All 3 workers are free at the same time; preferred_worker should win
        req = WorkforceRequest(
            operation_id="op1",
            eligible_workers=["W1", "W2", "W3"],
            team_size=1,
            preferred_worker="W2",
            earliest_start=START,
        )
        result = assign_workers_hungarian([req], worker_free_at=_free_at(W1=0, W2=0, W3=0))
        assert result == {"op1": ["W2"]}

    def test_error_rate_penalty(self):
        # W1 and W2 both free; W2 has high historical error rate → Hungarian
        # should prefer W1 despite tie on free-at.
        req = WorkforceRequest(
            operation_id="op1",
            eligible_workers=["W1", "W2"],
            team_size=1,
            error_rate_by_worker={"W1": 0.01, "W2": 0.9},
            earliest_start=START,
        )
        result = assign_workers_hungarian([req], worker_free_at=_free_at(W1=0, W2=0))
        assert result == {"op1": ["W1"]}

    def test_insufficient_workers_leaves_slots_empty(self):
        req = WorkforceRequest(
            operation_id="op1",
            eligible_workers=["W1"],
            team_size=2,  # need 2 but only 1 available
            earliest_start=START,
        )
        result = assign_workers_hungarian([req], worker_free_at=_free_at(W1=0))
        # Only 1 slot filled; the other is dummy-padded
        assert result["op1"] == ["W1"]

    def test_skill_mismatch_filtered(self):
        # op1 needs W1 or W2; the global worker pool also contains W3 (for op2)
        r1 = WorkforceRequest("op1", ["W1", "W2"], team_size=1, earliest_start=START)
        r2 = WorkforceRequest("op2", ["W3"], team_size=1, earliest_start=START)
        result = assign_workers_hungarian([r1, r2], worker_free_at=_free_at(W1=0, W2=0, W3=0))
        # op1 must get W1 or W2 (not W3); op2 must get W3
        assert result["op1"][0] in {"W1", "W2"}
        assert result["op2"] == ["W3"]


class TestFirstFitFallback:
    def test_matches_hungarian_for_simple_case(self):
        req = WorkforceRequest("op1", ["W1", "W2"], team_size=1, earliest_start=START)
        free = _free_at(W1=0, W2=60)
        hungarian = assign_workers_hungarian([req], free)
        first_fit = _first_fit_fallback([req], free, START)
        assert hungarian["op1"] == first_fit["op1"]  # both pick the earliest-free

    def test_empty_pool_is_handled(self):
        req = WorkforceRequest("op1", [], team_size=1, earliest_start=START)
        assert _first_fit_fallback([req], {}, START) == {"op1": []}
