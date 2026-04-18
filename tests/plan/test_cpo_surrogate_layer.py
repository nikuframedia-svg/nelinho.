"""
Tests for src.plan.cpo.surrogate.CPOSurrogateLayer.
"""

from __future__ import annotations

import random

import pytest

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.surrogate import CPOSurrogateLayer


CTX = {"n_ops": 20, "n_orders": 5, "avg_duration_min": 120.0}


def _chromo(seed: int = 1, n: int = 10) -> Chromosome:
    return Chromosome.random(n, random.Random(seed))


class TestDisabled:
    def test_disabled_never_skips(self):
        layer = CPOSurrogateLayer(enabled=False)
        layer.record(_chromo(1), CTX, fitness=100)
        assert layer.should_skip_candidate(_chromo(1), CTX) is False
        assert layer.is_trained is False

    def test_disabled_ignores_record(self):
        layer = CPOSurrogateLayer(enabled=False)
        for i in range(200):
            layer.record(_chromo(i), CTX, fitness=100 + i)
        snap = layer.snapshot()
        assert snap["samples"] == 0


class TestEnabledTraining:
    def test_record_accumulates_and_retrains(self):
        layer = CPOSurrogateLayer(
            enabled=True,
            retrain_every=20,
            min_samples_to_train=20,
        )
        # Feed 30 samples with a learnable linear-ish relationship
        for i in range(30):
            chromo = _chromo(i)
            fitness = 10.0 * i  # clearly deterministic
            layer.record(chromo, CTX, fitness)
        assert layer.is_trained is True
        snap = layer.snapshot()
        assert snap["samples"] == 30
        assert snap["samples_since_last_train"] == 10  # 30 - 20 (last retrain)

    def test_should_skip_false_until_trained(self):
        layer = CPOSurrogateLayer(enabled=True, retrain_every=100, min_samples_to_train=100)
        for i in range(50):
            layer.record(_chromo(i), CTX, fitness=10 + i)
        # Not enough samples to train → no skipping
        assert layer.should_skip_candidate(_chromo(1), CTX) is False

    def test_snapshot_tracks_skip_attempts(self):
        layer = CPOSurrogateLayer(enabled=True, retrain_every=20, min_samples_to_train=20)
        for i in range(25):
            layer.record(_chromo(i), CTX, fitness=10.0 * i)
        # After training, at least one should_skip_candidate call is made
        for i in range(10):
            layer.should_skip_candidate(_chromo(100 + i), CTX)
        snap = layer.snapshot()
        assert snap["skips_attempted"] == 10


class TestReset:
    def test_reset_clears_state(self):
        layer = CPOSurrogateLayer(enabled=True, retrain_every=20, min_samples_to_train=20)
        for i in range(25):
            layer.record(_chromo(i), CTX, fitness=10.0 * i)
        assert layer.is_trained is True
        layer.reset()
        assert layer.is_trained is False
        assert layer.snapshot()["samples"] == 0
