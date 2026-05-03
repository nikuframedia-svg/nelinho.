"""Sprint Q.13.E E.1 — Capacity 1.5× rework penalty in fitness.

Plan v4 §3.3: Lixagem água, Pintura Acab and Lixagem polim run at
49.2% / 42.4% / 41.3% historical rework rates. Without a capacity
correction, the GA over-promises throughput on these phases — a
schedule that physically fits in 200h actually burns ~300h once the
rework loops are factored back in.

These tests pin the contract:
  * The penalty is 0 when the factor is at unity (default).
  * The penalty is 0 when no phase breaches the threshold.
  * The penalty equals (factor - 1) × Σ duration_h for matching ops.
  * Schedules with high-rework ops score *worse* than identical
    schedules built on low-rework phases.
"""

from __future__ import annotations

import pytest

from src.plan.cpo.fitness import (
    FitnessConfig,
    _rework_penalty_hours,
    compute_fitness,
)


def _schedule(ops):
    return {
        "operations": ops,
        "makespan_hours": 100.0,
        "total_tardiness_hours": 0.0,
        "setups": 0,
        "quality_risk": 0.0,
    }


def test_rework_penalty_is_zero_when_factor_is_unity():
    cfg = FitnessConfig(
        rework_capacity_factor=1.0,
        phase_error_rates={"PHASE_X": 0.5},
    )
    sched = _schedule([{"phase_id": "PHASE_X", "duration_minutes": 60}])
    assert _rework_penalty_hours(sched, cfg) == 0.0


def test_rework_penalty_is_zero_when_no_phase_breaches_threshold():
    cfg = FitnessConfig(
        rework_capacity_factor=1.5,
        rework_error_threshold=0.40,
        phase_error_rates={"PHASE_X": 0.20},  # below threshold
    )
    sched = _schedule([{"phase_id": "PHASE_X", "duration_minutes": 120}])
    assert _rework_penalty_hours(sched, cfg) == 0.0


def test_rework_penalty_equals_extra_factor_times_duration_hours():
    """Plan v4 §3.3 — `(1.5 - 1) × duration_hours` for high-rework ops."""
    cfg = FitnessConfig(
        rework_capacity_factor=1.5,
        rework_error_threshold=0.40,
        phase_error_rates={"LIXAGEM_AGUA": 0.49},
    )
    # 120 min = 2h → expect 0.5 × 2 = 1.0h penalty
    sched = _schedule([
        {"phase_id": "LIXAGEM_AGUA", "duration_minutes": 120},
    ])
    assert _rework_penalty_hours(sched, cfg) == pytest.approx(1.0)


def test_rework_penalty_aggregates_across_ops_and_phases():
    cfg = FitnessConfig(
        rework_capacity_factor=1.5,
        rework_error_threshold=0.40,
        phase_error_rates={
            "LIXAGEM_AGUA": 0.49,
            "PINTURA_ACAB": 0.42,
            "LAMINAGEM": 0.05,  # ignored
        },
    )
    sched = _schedule([
        {"phase_id": "LIXAGEM_AGUA", "duration_minutes": 60},   # 1h * 0.5 = 0.5
        {"phase_id": "PINTURA_ACAB", "duration_minutes": 120},  # 2h * 0.5 = 1.0
        {"phase_id": "LAMINAGEM", "duration_minutes": 240},     # ignored
    ])
    assert _rework_penalty_hours(sched, cfg) == pytest.approx(1.5)


def test_high_rework_schedule_scores_worse_than_low_rework_schedule():
    cfg = FitnessConfig(
        rework_capacity_factor=1.5,
        rework_error_threshold=0.40,
        phase_error_rates={
            "LIXAGEM_AGUA": 0.49,   # high
            "LAMINAGEM": 0.05,      # low
        },
    )
    same_ops_field = lambda phase: _schedule([
        {"phase_id": phase, "duration_minutes": 480},  # 8h
    ])
    high = compute_fitness(same_ops_field("LIXAGEM_AGUA"), cfg)
    low = compute_fitness(same_ops_field("LAMINAGEM"), cfg)
    assert high > low, (
        f"High-rework schedule should score worse than low-rework "
        f"schedule (got high={high} <= low={low})"
    )


def test_rework_penalty_robust_to_missing_phase_or_duration():
    cfg = FitnessConfig(
        rework_capacity_factor=1.5,
        phase_error_rates={"PHASE_X": 0.50},
    )
    # Mixed: one valid op + one without phase + one with zero duration
    sched = _schedule([
        {"phase_id": "PHASE_X", "duration_minutes": 60},  # 1h × 0.5 = 0.5
        {"phase_id": None, "duration_minutes": 60},        # ignored (no phase)
        {"phase_id": "PHASE_X", "duration_minutes": 0},    # ignored (zero)
        {"phase_id": "PHASE_Y", "duration_minutes": 30},   # ignored (no rate)
    ])
    assert _rework_penalty_hours(sched, cfg) == pytest.approx(0.5)
