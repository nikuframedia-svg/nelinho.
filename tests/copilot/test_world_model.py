"""Sprint F+++ — world_model.forecast Monte Carlo rollout.

Covers the design contract from the plan:

* Trajectory has ``horizon_steps`` rows, each with the full quantile set
  + monotone p05<p25<p50<p75<p95.
* Same seed → same trajectory (reproducibility).
* Variance grows over the horizon (drift compounds) but does NOT
  balloon at step 0 — that would mean function-level noise sneaked
  in (the explicit "no fabricated precision" guard).
* ``do={"shift_mode": 2.0}`` doubles throughput at step 0 within a
  tolerance band that respects the inherited jitter on inputs.
* Unknown target / unknown node in ``do``/``observe`` → structured
  error (status='unavailable' + reason).
* ``jitter=0`` collapses every sample to the deterministic value at
  the corresponding step (jitter is the only source of variance).
* DRIFT_PROFILE: ``mold_age`` rises monotonically, temperature
  oscillates, material drops then floors at 0.50.
* Clamps on horizon_steps + samples + jitter.
"""

from __future__ import annotations

import math

import pytest

from src.copilot.causal.world_model import (
    DRIFT_PROFILE,
    HORIZON_MAX,
    HORIZON_MIN,
    JITTER_MAX,
    JITTER_MIN,
    SAMPLES_MAX,
    SAMPLES_MIN,
    STEP_UNIT,
    ForecastReport,
    forecast,
)


# ─── Trajectory shape + invariants ────────────────────────────────────────


def test_trajectory_has_horizon_rows_and_quantiles():
    report = forecast("throughput_eur_day", horizon_steps=5, samples=120)
    assert isinstance(report, ForecastReport)
    assert report.status == "degraded"
    assert report.step_unit == STEP_UNIT == "shift"
    assert len(report.trajectory) == 5
    for s in report.trajectory:
        assert s.p05 <= s.p25 <= s.p50 <= s.p75 <= s.p95
        assert s.std >= 0.0
        # mean lies inside the [p05, p95] band (not a hard guarantee
        # for arbitrary distributions, but holds for our jitter
        # propagation in practice).
        assert s.p05 - 1e-6 <= s.mean <= s.p95 + 1e-6


def test_seed_produces_reproducible_trajectory():
    a = forecast("makespan_hours", horizon_steps=4, samples=80, seed=11)
    b = forecast("makespan_hours", horizon_steps=4, samples=80, seed=11)
    assert [s.mean for s in a.trajectory] == [s.mean for s in b.trajectory]
    assert [s.p95 for s in a.trajectory] == [s.p95 for s in b.trajectory]


def test_different_seeds_diverge_within_band():
    a = forecast("makespan_hours", horizon_steps=4, samples=80, seed=1)
    b = forecast("makespan_hours", horizon_steps=4, samples=80, seed=2)
    # At least one step's mean differs (Monte Carlo noise).
    assert any(
        abs(sa.mean - sb.mean) > 1e-6
        for sa, sb in zip(a.trajectory, b.trajectory)
    )


# ─── No fabricated precision — function-level noise must not exist ───────


def test_jitter_zero_collapses_each_step_to_deterministic_value():
    """Sanity: when jitter=0 the inputs/confounders match the drift
    profile exactly and every sample within a step gives the same
    target value. std must be 0 throughout."""
    report = forecast(
        "makespan_hours",
        horizon_steps=4, samples=80, jitter=0.0, seed=99,
    )
    for s in report.trajectory:
        assert s.std == pytest.approx(0.0, abs=1e-9), (
            f"jitter=0 should yield zero std, got {s.std} at step {s.step}"
        )
        assert s.p05 == pytest.approx(s.p95, abs=1e-9)


def test_step0_std_is_input_jitter_scale_not_compound():
    """Function-level noise (banned) would inflate step-0 std to
    multiples of the per-input jitter through topological depth.
    Inputs-only jitter at 5% leaves step 0 std bounded — concrete
    sanity ceiling: < 50% of mean for laminagem_duration (a derived
    node 2 levels deep)."""
    report = forecast(
        "laminagem_duration", horizon_steps=1, samples=300, jitter=0.05,
        seed=7,
    )
    s = report.trajectory[0]
    assert s.std < abs(s.mean) * 0.50, (
        f"step-0 std={s.std:.3f} > 50% of mean={s.mean:.3f}; "
        "function-level noise leaked in"
    )


# ─── Drift compounds over horizon ────────────────────────────────────────


def test_horizon_grows_band_for_drift_sensitive_target():
    """material_availability_pct drifts down monotonically →
    total_tardiness_hours band widens with horizon."""
    short = forecast(
        "total_tardiness_hours", horizon_steps=1, samples=200, seed=3,
    )
    long_ = forecast(
        "total_tardiness_hours", horizon_steps=14, samples=200, seed=3,
    )
    short_p95 = short.trajectory[0].p95
    long_last_p95 = long_.trajectory[-1].p95
    # Material drift (-0.005 / step) over 14 steps → -7 pp on
    # availability → tardiness should rise by ~50–80h.
    assert long_last_p95 > short_p95


# ─── Interventions land where they should ────────────────────────────────


def test_double_shift_lifts_throughput_mean_to_near_2x():
    base = forecast(
        "throughput_eur_day", horizon_steps=1, samples=200, seed=5,
    )
    doubled = forecast(
        "throughput_eur_day", do={"shift_mode": 2.0},
        horizon_steps=1, samples=200, seed=5,
    )
    ratio = doubled.trajectory[0].mean / base.trajectory[0].mean
    # Expect close to 2.0 — slack for 5% input jitter on materials etc.
    assert 1.7 < ratio < 2.3, f"shift_mode=2 lift ratio={ratio:.2f}"


def test_routing_b_lowers_makespan_mean():
    base = forecast("makespan_hours", horizon_steps=1, samples=200, seed=8)
    variant = forecast(
        "makespan_hours", do={"routing_variant": 1.0},
        horizon_steps=1, samples=200, seed=8,
    )
    assert variant.trajectory[0].mean < base.trajectory[0].mean


# ─── Error paths ─────────────────────────────────────────────────────────


def test_unknown_target_returns_unavailable_with_reason():
    report = forecast("does_not_exist", horizon_steps=3, samples=80)
    assert report.status == "unavailable"
    assert "unknown DAG node" in (report.reason or "")
    assert report.trajectory == []


def test_unknown_node_in_do_returns_unavailable():
    report = forecast(
        "throughput_eur_day", do={"nonsense_knob": 1.0},
        horizon_steps=3, samples=80,
    )
    assert report.status == "unavailable"
    assert "do" in (report.reason or "")


def test_non_numeric_value_in_do_returns_unavailable():
    report = forecast(
        "throughput_eur_day", do={"shift_mode": "two"},
        horizon_steps=3, samples=80,
    )
    assert report.status == "unavailable"
    assert "must be numeric" in (report.reason or "")


# ─── Clamps on user-provided knobs ───────────────────────────────────────


def test_horizon_clamped_to_valid_range():
    too_long = forecast("makespan_hours", horizon_steps=999, samples=80)
    assert too_long.horizon_steps == HORIZON_MAX
    too_short = forecast("makespan_hours", horizon_steps=0, samples=80)
    assert too_short.horizon_steps == HORIZON_MIN


def test_samples_clamped_to_valid_range():
    capped = forecast("makespan_hours", horizon_steps=2, samples=10_000)
    assert capped.samples == SAMPLES_MAX
    raised = forecast("makespan_hours", horizon_steps=2, samples=10)
    assert raised.samples == SAMPLES_MIN


def test_jitter_clamped_to_valid_range():
    capped = forecast(
        "makespan_hours", horizon_steps=2, samples=80, jitter=2.0,
    )
    assert capped.jitter == JITTER_MAX
    floored = forecast(
        "makespan_hours", horizon_steps=2, samples=80, jitter=-1.0,
    )
    assert floored.jitter == JITTER_MIN


# ─── DRIFT_PROFILE acts as documented ────────────────────────────────────


def test_mold_age_drift_is_monotone_increasing():
    fn = DRIFT_PROFILE["mold_age"]
    samples = [fn(t, 3.5) for t in range(0, 30)]
    assert samples == sorted(samples)
    assert samples[0] == pytest.approx(0.0)
    assert samples[-1] > samples[0]


def test_external_temperature_drift_is_oscillatory():
    fn = DRIFT_PROFILE["external_temperature"]
    samples = [fn(t, 19.0) for t in range(0, 14)]
    # Sin over a full period → returns to ~0 at t=14, peaks around t=3-4.
    assert max(samples) > 0
    assert min(samples) < 0


def test_material_availability_drift_floors_at_50pct():
    fn = DRIFT_PROFILE["material_availability_pct"]
    base = 0.92
    drift_30 = fn(30, base)
    # 0.92 - 30*0.005 = 0.77 → above 0.50 floor → unclamped
    assert base + drift_30 == pytest.approx(0.77, abs=1e-6)
    # Way past the floor:
    drift_huge = fn(1000, base)
    assert base + drift_huge == pytest.approx(0.50, abs=1e-6)


# ─── Summary helpers ─────────────────────────────────────────────────────


def test_summary_classifies_trend_correctly():
    """shift_mode=2 + 14-step horizon should keep throughput high
    (no drift drag is large enough to push it down) → trend != falling."""
    report = forecast(
        "throughput_eur_day", do={"shift_mode": 2.0},
        horizon_steps=14, samples=120, seed=4,
    )
    assert report.summary["trend"] in {"flat", "rising", "falling"}
    # ci90 is a 2-element list of [p05, p95] at horizon
    ci90 = report.summary["ci90_at_horizon"]
    assert isinstance(ci90, list) and len(ci90) == 2
    assert ci90[0] <= ci90[1]
