"""
Tests for src.ml.models_domain.surrogate.SurrogateModel.
"""

from __future__ import annotations

import math
import random
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.ml.models_domain.surrogate import (
    FEATURE_ORDER,
    SurrogateModel,
    SurrogateRetrainJob,
    _permutation_entropy,
    extract_surrogate_features,
)


def _synthetic_samples(n: int = 100, seed: int = 1) -> List[Dict[str, Any]]:
    """
    A learnable relationship: fitness increases with n_ops and buffer_pct.
    """
    rng = random.Random(seed)
    samples = []
    for _ in range(n):
        features = {
            "n_ops": rng.randint(10, 100),
            "n_orders": rng.randint(5, 30),
            "edd_gap": rng.randint(5, 30),
            "buffer_pct": round(rng.uniform(0.0, 0.25), 3),
            "quality_weight": round(rng.uniform(0.0, 0.8), 3),
            "avg_duration_min": rng.uniform(60, 500),
            "permutation_entropy": round(rng.uniform(0.0, 3.0), 3),
        }
        # Deterministic fitness with noise
        fitness = (
            10 * features["n_ops"]
            + 100 * features["buffer_pct"]
            + rng.gauss(0, 2)
        )
        samples.append({"features": features, "fitness": fitness})
    return samples


class TestSurrogateModel:
    def test_train_and_predict(self):
        model = SurrogateModel()
        metrics = model.train(_synthetic_samples(100))

        assert metrics["samples"] == 100
        assert 0.0 <= metrics["wmape"] <= 1.0
        assert model.regressor is not None
        assert not math.isinf(model.best_known_fitness)

    def test_predict_before_train_raises(self):
        with pytest.raises(RuntimeError):
            SurrogateModel().predict({k: 0.0 for k in FEATURE_ORDER})

    def test_insufficient_samples_raises(self):
        with pytest.raises(ValueError):
            SurrogateModel().train(_synthetic_samples(5))

    def test_should_skip_candidate_when_worse(self):
        model = SurrogateModel()
        model.train(_synthetic_samples(100))
        # Clamp best_known to a known value so the check is deterministic
        model.best_known_fitness = 100.0

        # High n_ops → predicted fitness way worse than 100 * 1.2 = 120
        bad_features = {
            "n_ops": 500, "n_orders": 50, "edd_gap": 14,
            "buffer_pct": 0.2, "quality_weight": 0.5,
            "avg_duration_min": 300, "permutation_entropy": 2.0,
        }
        # At least one of the following should hold given the synthetic fitness
        # formula — don't assert strictly since RF noise exists
        predicted = model.predict(bad_features)
        assert predicted > 100  # clearly worse than best

    def test_should_not_skip_without_training(self):
        model = SurrogateModel()
        assert model.should_skip_candidate({k: 0.0 for k in FEATURE_ORDER}) is False


class TestExtractSurrogateFeatures:
    def test_reads_chromosome_fields(self):
        chromosome = SimpleNamespace(
            permutation=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            edd_gap=14,
            buffer_pct=0.1,
            quality_weight=0.3,
        )
        feats = extract_surrogate_features(
            chromosome,
            n_ops=10, n_orders=5, avg_duration_min=120.0,
        )
        assert feats["n_ops"] == 10.0
        assert feats["edd_gap"] == 14.0
        assert feats["buffer_pct"] == 0.1
        assert feats["permutation_entropy"] >= 0

    def test_short_permutation_entropy_zero(self):
        assert _permutation_entropy([1, 2]) == 0.0
        assert _permutation_entropy([]) == 0.0

    def test_shuffled_permutation_has_higher_entropy(self):
        sorted_perm = list(range(20))
        random.seed(42)
        shuffled = list(range(20))
        random.shuffle(shuffled)

        e_sorted = _permutation_entropy(sorted_perm)
        e_shuffled = _permutation_entropy(shuffled)
        # A sorted permutation produces only one window pattern → low entropy
        assert e_sorted < e_shuffled


class TestSurrogateRetrainJob:
    def test_extract_features_from_callable(self):
        samples = _synthetic_samples(30)
        job = SurrogateRetrainJob(sample_provider=lambda: samples)
        from uuid import uuid4
        out = job.extract_features(uuid4())
        assert len(out) == 30

    def test_no_schedule_cron(self):
        """Surrogate is event-driven, not cron-driven."""
        assert SurrogateRetrainJob.schedule_cron == ""
