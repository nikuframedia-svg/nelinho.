"""
Tests for Sprint I.3 — quality risk hook in compute_fitness.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from src.plan.cpo.fitness import (
    FitnessConfig,
    build_op_features_for_risk,
    compute_fitness,
)


def _schedule(ops: List[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    return {
        "makespan_hours": kwargs.get("makespan_hours", 10.0),
        "total_tardiness_hours": kwargs.get("total_tardiness_hours", 0.0),
        "setups": kwargs.get("setups", 0),
        "operations": ops or [],
    }


class TestNoPredictor:
    def test_base_fitness_without_quality(self):
        # w_quality_risk=0 by default → risk term ignored
        f = compute_fitness(_schedule(makespan_hours=5))
        assert f == 5.0

    def test_scalar_fallback_when_predictor_missing(self):
        # Callers may pre-compute risk and stick it on the schedule
        cfg = FitnessConfig(w_quality_risk=10.0)
        schedule = _schedule()
        schedule["quality_risk"] = 0.25
        f = compute_fitness(schedule, cfg)
        # base (10 h) + 10 * 0.25
        assert f == pytest.approx(10.0 + 10.0 * 0.25)


class TestPredictorWired:
    def test_mean_risk_added(self):
        def fake_predictor(rows: List[Dict[str, Any]]) -> List[float]:
            return [0.1, 0.2, 0.3]

        cfg = FitnessConfig(
            w_quality_risk=10.0,
            quality_risk_predictor=fake_predictor,
            quality_risk_hard_threshold=0.9,  # never trigger
        )
        schedule = _schedule(
            ops=[{"phase_id": "LAM"} for _ in range(3)],
            makespan_hours=0,  # isolate risk term
        )
        f = compute_fitness(schedule, cfg)
        # Mean of [0.1, 0.2, 0.3] = 0.2 → 10 * 0.2
        assert f == pytest.approx(2.0)

    def test_hard_threshold_penalty(self):
        # Two ops above the hard threshold → 2 × hard_penalty × w_quality
        def fake_predictor(rows):
            return [0.5, 0.6, 0.1]

        cfg = FitnessConfig(
            w_quality_risk=1.0,
            quality_risk_predictor=fake_predictor,
            quality_risk_hard_threshold=0.4,
            quality_risk_hard_penalty=100.0,
        )
        schedule = _schedule(
            ops=[{"phase_id": "LAM"} for _ in range(3)],
            makespan_hours=0,
        )
        f = compute_fitness(schedule, cfg)
        # Mean 0.4 + 2 hits × 100
        assert f == pytest.approx((0.5 + 0.6 + 0.1) / 3 + 200.0)

    def test_predictor_exception_does_not_crash(self):
        def broken_predictor(rows):
            raise RuntimeError("simulated")

        cfg = FitnessConfig(
            w_quality_risk=5.0,
            quality_risk_predictor=broken_predictor,
        )
        schedule = _schedule(ops=[{"phase_id": "LAM"}], makespan_hours=3)
        # Must not raise; risk term drops to 0 fallback (scalar = 0 default)
        f = compute_fitness(schedule, cfg)
        assert f == 3.0

    def test_empty_operations_uses_scalar_fallback(self):
        def fake_predictor(rows):
            return [0.9]  # never called — operations is empty

        cfg = FitnessConfig(
            w_quality_risk=10.0,
            quality_risk_predictor=fake_predictor,
        )
        schedule = _schedule(ops=[])
        schedule["quality_risk"] = 0.5
        f = compute_fitness(schedule, cfg)
        # ops is empty → predictor yields [], scalar fallback used
        # base 10h + 10 * 0.5
        assert f == pytest.approx(15.0)


class TestFeatureExtractor:
    def test_default_projector_covers_required_fields(self):
        op = {
            "operation_id": "o1",
            "phase_id": "LAM",
            "model_id": "K1",
            "workers": ["W1", "W2"],
        }
        features = build_op_features_for_risk(op)
        assert features["modelo_id"] == "K1"
        assert features["fase_id"] == "LAM"
        assert features["team_size"] == 2
        # Missing fields default to safe zeros
        assert features["mold_pocket_count"] == 1
        assert features["phase_error_rate"] == 0.0
        assert features["queue_depth"] == 0

    def test_missing_workers_becomes_team_size_1(self):
        features = build_op_features_for_risk({"phase_id": "LAM"})
        assert features["team_size"] == 1
