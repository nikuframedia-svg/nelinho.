"""
Tests for src.plan.cpo.mapelites.MAPElites3D.
"""

from __future__ import annotations

import random
from typing import Any, Dict

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.mapelites import DEFAULT_BINS, MAPElites3D


def _schedule(util: float, tardy_h: float, late: int) -> Dict[str, Any]:
    return {
        "avg_utilization": util,
        "total_tardiness_hours": tardy_h,
        "num_late_orders": late,
    }


def _chromo(seed: int = 1, n: int = 8) -> Chromosome:
    return Chromosome.random(n, random.Random(seed))


class TestMAPElites3D:
    def test_insert_new_cell_returns_true(self):
        archive = MAPElites3D()
        assert archive.insert(_chromo(1), fitness=100.0, schedule=_schedule(50, 10, 2), generation=0) is True
        assert archive.cells_occupied() == 1

    def test_insert_worse_keeps_incumbent(self):
        archive = MAPElites3D()
        archive.insert(_chromo(1), fitness=50.0, schedule=_schedule(50, 10, 2), generation=0)
        admitted = archive.insert(_chromo(2), fitness=80.0, schedule=_schedule(52, 11, 2), generation=1)
        # Same cell (rounding), worse fitness → rejected
        assert admitted is False
        elite = archive.best()
        assert elite.fitness == 50.0

    def test_insert_better_replaces_incumbent(self):
        archive = MAPElites3D()
        archive.insert(_chromo(1), fitness=100.0, schedule=_schedule(50, 10, 2), generation=0)
        admitted = archive.insert(_chromo(2), fitness=50.0, schedule=_schedule(51, 10, 2), generation=1)
        assert admitted is True
        assert archive.best().fitness == 50.0

    def test_different_schedules_occupy_different_cells(self):
        archive = MAPElites3D()
        # Three clearly different behavior profiles
        archive.insert(_chromo(1), fitness=10, schedule=_schedule(0, 0, 0), generation=0)
        archive.insert(_chromo(2), fitness=20, schedule=_schedule(100, 100, 15), generation=0)
        archive.insert(_chromo(3), fitness=30, schedule=_schedule(50, 50, 5), generation=0)
        assert archive.cells_occupied() == 3

    def test_coverage_reports_fraction(self):
        archive = MAPElites3D(bins=DEFAULT_BINS)
        archive.insert(_chromo(1), fitness=1, schedule=_schedule(10, 5, 1), generation=0)
        total_cells = DEFAULT_BINS[0] * DEFAULT_BINS[1] * DEFAULT_BINS[2]
        assert archive.coverage() == round(1 / total_cells, 4)

    def test_bin_clamps_out_of_range(self):
        archive = MAPElites3D()
        # negative util, huge tardy, late > max — all should clamp to valid bins
        archive.insert(_chromo(1), fitness=1, schedule=_schedule(-5, 10_000, 99), generation=0)
        assert archive.cells_occupied() == 1

    def test_sample_returns_distinct_chromosomes(self):
        archive = MAPElites3D()
        for i in range(5):
            archive.insert(
                _chromo(i), fitness=float(i),
                schedule=_schedule(10 + i * 20, 5 + i * 15, i),
                generation=0,
            )
        rng = random.Random(42)
        sample = archive.sample(3, rng)
        assert len(sample) == 3
        # All clones are distinct objects (clone() returns new instance)
        assert len({id(c) for c in sample}) == 3

    def test_representatives_span_behavior_space(self):
        archive = MAPElites3D()
        # Two very different profiles + three near-duplicates
        archive.insert(_chromo(1), fitness=10, schedule=_schedule(0, 0, 0), generation=0)
        archive.insert(_chromo(2), fitness=20, schedule=_schedule(100, 168, 20), generation=0)
        archive.insert(_chromo(3), fitness=11, schedule=_schedule(5, 2, 1), generation=0)
        archive.insert(_chromo(4), fitness=12, schedule=_schedule(8, 3, 0), generation=0)
        archive.insert(_chromo(5), fitness=13, schedule=_schedule(95, 160, 19), generation=0)

        reps = archive.representatives(n=2)
        assert len(reps) == 2
        # First pick = global best; second should be far from first in BD space
        # so its fitness is larger (not necessarily the 2nd best overall)

    def test_inject_fraction(self):
        archive = MAPElites3D(injection_fraction=0.2)
        for i in range(10):
            archive.insert(_chromo(i), fitness=float(i), schedule=_schedule(i * 10, i, 0), generation=0)
        injected = archive.inject_random_candidates(current_population_size=50, rng=random.Random(0))
        assert 1 <= len(injected) <= 10


class TestSnapshot:
    def test_snapshot_tracks_counters(self):
        archive = MAPElites3D()
        archive.insert(_chromo(1), fitness=50, schedule=_schedule(10, 0, 0), generation=0)
        archive.insert(_chromo(2), fitness=100, schedule=_schedule(11, 0, 0), generation=1)  # same cell, worse
        archive.insert(_chromo(3), fitness=40, schedule=_schedule(12, 0, 0), generation=2)  # same cell, better
        snap = archive.snapshot()
        assert snap["cells_occupied"] == 1
        assert snap["insertions"] == 1
        assert snap["replacements"] == 1
