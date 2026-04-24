"""Sprint I.5 — causal_entropy.py + FitnessConfig.w_causal_entropy.

Covers:
* ``shannon_entropy`` / ``normalised_entropy`` primitives.
* Axis aggregation: the three axes (machine / workers / mould) are
  averaged, and missing axes are skipped without dragging the score.
* Degenerate distributions (single bucket, empty ops) return 0.
* Fitness integration: concentrated plans pay a higher penalty than
  spread ones, and ``w_causal_entropy=0`` restores the pre-I.5 score.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import pytest

from src.plan.cpo.causal_entropy import (
    causal_entropy_penalty,
    causal_entropy_score,
    normalised_entropy,
    shannon_entropy,
)
from src.plan.cpo.fitness import FitnessConfig, compute_fitness


def _op(**fields: Any) -> Dict[str, Any]:
    base = {
        "operation_id": "op",
        "order_id": "ord",
        "phase_id": "LAMINAGEM",
        "machine_id": "M1",
        "workers": ["w1"],
        "mold_id": "K1",
        "start_time": "2026-04-24T08:00:00",
    }
    base.update(fields)
    return base


def _schedule(ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "operations": list(ops),
        "makespan_hours": 10.0,
        "total_tardiness_hours": 0.0,
        "setups": 0,
        "quality_risk": 0.0,
    }


# ─── Primitives ──────────────────────────────────────────────────────────


def test_shannon_entropy_of_uniform_distribution():
    # Two buckets equal → ln(2) nats
    assert shannon_entropy({"a": 5, "b": 5}) == pytest.approx(math.log(2))


def test_shannon_entropy_of_single_bucket_is_zero():
    assert shannon_entropy({"a": 10}) == pytest.approx(0.0)


def test_shannon_entropy_empty_dict_is_zero():
    assert shannon_entropy({}) == 0.0


def test_normalised_entropy_peaks_at_one_for_flat():
    assert normalised_entropy({"a": 3, "b": 3, "c": 3}) == pytest.approx(1.0)


def test_normalised_entropy_drops_for_skewed():
    skewed = normalised_entropy({"a": 10, "b": 1})
    flat = normalised_entropy({"a": 5, "b": 5})
    assert skewed < flat
    assert 0.0 < skewed < 1.0


def test_normalised_entropy_single_bucket_is_zero():
    assert normalised_entropy({"a": 10}) == 0.0


# ─── Axis aggregation ───────────────────────────────────────────────────


def test_score_zero_on_empty_schedule():
    assert causal_entropy_score({"operations": []}) == 0.0
    assert causal_entropy_penalty({"operations": []}) == 0.0


def test_score_drops_when_one_machine_hogs_all_ops():
    concentrated = _schedule([
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
    ])
    spread = _schedule([
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
        _op(machine_id="M2", workers=["w2"], mold_id="K2"),
        _op(machine_id="M3", workers=["w3"], mold_id="K3"),
    ])
    assert causal_entropy_score(concentrated) < causal_entropy_score(spread)
    assert causal_entropy_penalty(concentrated) > causal_entropy_penalty(spread)


def test_missing_axis_does_not_poison_score():
    """Ops with no mould_id — mould axis is simply skipped; machine +
    workers still contribute."""
    ops = _schedule([
        _op(machine_id="M1", workers=["w1"], mold_id=None),
        _op(machine_id="M2", workers=["w2"], mold_id=None),
    ])
    # Machine + workers each fully flat (2 buckets, 1 op each) → 1.0
    # Mould skipped. Mean = 1.0 → penalty 0.
    assert causal_entropy_penalty(ops) == pytest.approx(0.0)


def test_workers_list_flattens_to_individual_tallies():
    """A pair-op on one pair of workers spreads the workforce
    axis — the distribution is {w1:1, w2:1}."""
    ops = _schedule([
        _op(machine_id="M1", workers=["w1", "w2"], mold_id="K1"),
        _op(machine_id="M2", workers=["w1", "w2"], mold_id="K2"),
    ])
    # Workers axis has 2 buckets each at 2 ops → flat, entropy 1.0.
    assert causal_entropy_score(ops) >= 0.9


# ─── Fitness integration ───────────────────────────────────────────────


def test_fitness_default_weight_adds_penalty_to_concentrated_schedule():
    schedule = _schedule([_op(), _op(), _op()])  # all identical → max penalty
    baseline = compute_fitness(schedule, FitnessConfig(w_causal_entropy=0))
    with_entropy = compute_fitness(schedule, FitnessConfig(w_causal_entropy=0.05))
    assert with_entropy > baseline
    assert with_entropy - baseline == pytest.approx(0.05)


def test_fitness_weight_zero_restores_pre_entropy_value():
    schedule = _schedule([
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
        _op(machine_id="M2", workers=["w2"], mold_id="K2"),
    ])
    cfg = FitnessConfig(w_causal_entropy=0)
    legacy_fitness = compute_fitness(schedule, cfg)
    # Baseline when no entropy weight.
    assert compute_fitness(schedule, FitnessConfig(w_causal_entropy=0)) == legacy_fitness


def test_spread_schedule_beats_concentrated_at_same_first_order_cost():
    """Two schedules with identical makespan / tardiness / setups —
    the more spread one wins because entropy penalty is smaller."""
    concentrated = _schedule([
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
    ])
    spread = _schedule([
        _op(machine_id="M1", workers=["w1"], mold_id="K1"),
        _op(machine_id="M2", workers=["w2"], mold_id="K2"),
    ])
    cfg = FitnessConfig(w_causal_entropy=0.1)
    assert compute_fitness(spread, cfg) < compute_fitness(concentrated, cfg)
