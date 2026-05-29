"""
Q.67.3.B — Mutation-pin tests for src.plan.cpo.fitness.

Strategy
========
Same posture as ``test_decoder_mutation_pin_q67.py``: anticipate
mutmut's typical survivor classes (comparison operators, magic
numbers, arithmetic signs, default values) and pin them with
small, fast tests instead of running ``mutmut --paths-to-mutate
src/plan/cpo/fitness.py`` (10-30min).

Pinned functions
----------------
* ``compute_fitness`` (top-level dispatch + branches)
* ``_legacy_fitness`` (weighted sum + predictor mean + hard penalty)
* ``_v2_fitness`` (normalised KPIs, throughput sign flip)
* ``_rework_penalty_hours`` (factor <=1.0 short-circuit, threshold boundary)
* ``build_op_features_for_risk`` (int/float fallback, ``len(workers) or 1``)

Each weight, each threshold, each magic number gets at least one
test that fails if a mutation neutralises it.

Mutation-aware test design — see ``agent_docs/q67_3b_mutation_pin_strategy.md``.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from src.plan.cpo.fitness import (
    FitnessConfig,
    _legacy_fitness,
    _rework_penalty_hours,
    _v2_fitness,
    build_op_features_for_risk,
    compute_fitness,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _schedule(**kwargs) -> Dict[str, Any]:
    """Build a schedule dict with neutral defaults so each test isolates
    exactly the term it wants to probe."""
    return {
        "makespan_hours": kwargs.get("makespan_hours", 0.0),
        "total_tardiness_hours": kwargs.get("total_tardiness_hours", 0.0),
        "setups": kwargs.get("setups", 0),
        "operations": kwargs.get("operations", []),
        **{
            k: v for k, v in kwargs.items()
            if k not in ("makespan_hours", "total_tardiness_hours", "setups", "operations")
        },
    }


# ---------------------------------------------------------------------------
# 1) Legacy weights — pin each scalar weight individually
# ---------------------------------------------------------------------------

class TestLegacyWeightsPinned:
    """Each legacy weight (1.0 / 10.0 / 0.5) must change the output in
    exactly the expected proportion. Mutmut flipping ``1.0`` → ``0.0`` or
    ``10.0`` → ``1.0`` makes one of these tests fail.
    """

    def test_makespan_weight_one_to_one(self):
        # Default w_makespan=1.0, isolated.
        f = compute_fitness(_schedule(makespan_hours=7))
        assert f == 7.0

    def test_tardiness_weight_is_ten(self):
        # Default w_tardiness=10.0 — 1h of tardiness costs 10 units.
        f = compute_fitness(_schedule(total_tardiness_hours=1))
        assert f == 10.0

    def test_tardiness_dominates_makespan_by_ten(self):
        # Pin the 10× domain ratio: 1h tardy must be exactly 10× worse
        # than 1h of makespan. If a mutation makes them equal, this fails.
        f_makespan = compute_fitness(_schedule(makespan_hours=1))
        f_tardy = compute_fitness(_schedule(total_tardiness_hours=1))
        assert f_tardy == 10.0 * f_makespan

    def test_setup_weight_is_half(self):
        # Default w_setups=0.5 — 2 setups cost 1.0 of fitness.
        f = compute_fitness(_schedule(setups=2))
        assert f == 1.0

    def test_zero_schedule_zero_fitness(self):
        # All-zeros input must produce 0.0 — pins that nothing is hard-coded
        # to add a non-zero bias.
        assert compute_fitness(_schedule()) == 0.0

    def test_legacy_uses_safety_penalty_one_million(self):
        # safety_penalty=1e6 is a deliberate choke — mutmut flipping the
        # constant to 1.0 would break this.
        f = compute_fitness(_schedule(safety_violated=True))
        assert f == 1_000_000.0

    def test_quality_risk_scalar_fallback(self):
        # When no predictor wired, ``schedule["quality_risk"]`` is used
        # with weight=w_quality_risk (default 0.10).
        cfg = FitnessConfig(w_quality_risk=10.0)
        f = compute_fitness(_schedule(quality_risk=0.5), cfg)
        # No other costs → 10 * 0.5
        assert f == pytest.approx(5.0)

    def test_default_quality_risk_weight_is_ten_percent(self):
        # Pin the 0.10 default — Blueprint v2.0 §5.5 raised it from 0.0.
        cfg = FitnessConfig()
        assert cfg.w_quality_risk == 0.10

    def test_legacy_fitness_helper_matches_direct_sum(self):
        # Pin the exact arithmetic of ``_legacy_fitness`` (no surprises).
        cfg = FitnessConfig()
        s = _schedule(makespan_hours=2, total_tardiness_hours=1, setups=4)
        # 1.0*2 + 10.0*1 + 0.5*4 = 2 + 10 + 2 = 14
        assert _legacy_fitness(s, cfg) == 14.0


# ---------------------------------------------------------------------------
# 2) Predictor branch — mean and hard-threshold penalty
# ---------------------------------------------------------------------------

class TestPredictorBranch:
    """Pin the ``cfg.quality_risk_predictor is not None`` branch."""

    def test_predictor_mean_added(self):
        # Mean P(error) = 0.2; w_quality_risk=10 → contribution = 2.0.
        cfg = FitnessConfig(
            w_quality_risk=10.0,
            quality_risk_predictor=lambda rows: [0.1, 0.2, 0.3],
            quality_risk_hard_threshold=0.99,  # never trigger
        )
        s = _schedule(operations=[{"phase_id": "P"}] * 3)
        assert compute_fitness(s, cfg) == pytest.approx(2.0)

    def test_hard_threshold_inclusive_lower_bound(self):
        # Threshold check is ``r >= threshold`` (inclusive). Mutmut may
        # flip to ``>``; a probability exactly equal to threshold must trip.
        cfg = FitnessConfig(
            w_quality_risk=1.0,
            quality_risk_predictor=lambda rows: [0.4],   # == threshold
            quality_risk_hard_threshold=0.4,
            quality_risk_hard_penalty=100.0,
        )
        s = _schedule(operations=[{"phase_id": "P"}])
        # mean=0.4 → 0.4*1.0 contribution.
        # 1 hard hit → 1 * 100 * 1.0 = 100 extra.
        assert compute_fitness(s, cfg) == pytest.approx(0.4 + 100.0)

    def test_hard_threshold_just_below_not_triggered(self):
        # Probability 0.39 vs threshold 0.4 → strictly below, no hard hit.
        cfg = FitnessConfig(
            w_quality_risk=1.0,
            quality_risk_predictor=lambda rows: [0.39],
            quality_risk_hard_threshold=0.4,
            quality_risk_hard_penalty=100.0,
        )
        s = _schedule(operations=[{"phase_id": "P"}])
        # Only mean contribution, no hard penalty.
        assert compute_fitness(s, cfg) == pytest.approx(0.39)

    def test_predictor_empty_ops_falls_back_to_scalar(self):
        # When there are no ops, the predictor branch is skipped and the
        # scalar ``quality_risk`` field is used. Pins the ``if not ops``
        # early-return path inside ``_predict_risks_safe``.
        cfg = FitnessConfig(
            w_quality_risk=10.0,
            quality_risk_predictor=lambda rows: [0.5],
        )
        s = _schedule(operations=[], quality_risk=0.1)
        # No ops → scalar fallback: 10 * 0.1
        assert compute_fitness(s, cfg) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 3) V2 normalised weights — sum-to-one + throughput sign flip
# ---------------------------------------------------------------------------

class TestV2NormalisedWeights:
    """Pin Blueprint v2.0 normalisation reference magnitudes + sign of throughput."""

    def test_v2_weight_set_sums_to_one(self):
        # Pin the design constraint that the 7 normalised weights
        # sum to 1.0 — a mutmut tweak that drifts the sum surfaces.
        # Q.115.X7 re-balanceou: setup 0.15->0.10, throughput 0.15->0.10,
        # + novo revenue_target_alignment 0.10 (delta net 0 -> soma=1.0).
        cfg = FitnessConfig()
        total = (
            cfg.w_v2_makespan
            + cfg.w_v2_tardiness_transport
            + cfg.w_v2_idle_operators
            + cfg.w_v2_setup_time
            + cfg.w_v2_quality_risk
            + cfg.w_v2_throughput_eur_day
            + cfg.w_v2_revenue_target_alignment
        )
        assert total == pytest.approx(1.0)

    def test_v2_throughput_subtracted_not_added(self):
        # Throughput is subtracted in v2 (so more throughput -> lower/better
        # fitness). The revenue-alignment offset is identical in both calls
        # (constant -0.10 sem target), so it cancels in this delta and only
        # the throughput term remains.
        cfg = FitnessConfig(use_v2_weights=True)
        base = compute_fitness(_schedule(), cfg)
        better = compute_fitness(_schedule(throughput_eur_day=35000), cfg)
        # _NORM_THROUGHPUT_EUR_DAY=35000 → norm=1.0; w_v2_throughput_eur_day
        # = 0.10 (Q.115.X7, era 0.15) → subtracted 0.10.
        assert better == pytest.approx(base - 0.10)

    def test_v2_makespan_normalisation_caps_at_one(self):
        # The ``_norm`` clamp at 1.0 — values above _NORM_MAKESPAN_H=1000
        # must NOT keep growing fitness. Pin the cap at the boundary.
        cfg = FitnessConfig(use_v2_weights=True)
        at_cap = compute_fitness(_schedule(makespan_hours=1000), cfg)
        way_over = compute_fitness(_schedule(makespan_hours=999_999), cfg)
        assert at_cap == way_over

    def test_v2_norm_floor_at_zero(self):
        # ``_norm`` clamps below at 0 as well — negative values must not
        # produce negative fitness contributions.
        cfg = FitnessConfig(use_v2_weights=True)
        zero = compute_fitness(_schedule(), cfg)
        negative_input = compute_fitness(_schedule(makespan_hours=-500), cfg)
        assert zero == negative_input

    def test_v2_makespan_half_norm_pinned(self):
        # makespan=500, _NORM=1000 → norm=0.5; w_v2_makespan=0.20 → +0.10.
        # menos o offset revenue-neutral (-0.10*1.0, sem target) → 0.0.
        cfg = FitnessConfig(use_v2_weights=True)
        assert compute_fitness(_schedule(makespan_hours=500), cfg) == pytest.approx(0.0)

    def test_v2_uses_transport_tardiness_when_present(self):
        # When ``total_tardiness_transport_hours`` is set, v2 prefers it
        # over the legacy ``total_tardiness_hours`` field.
        cfg = FitnessConfig(use_v2_weights=True)
        # transport=250, _NORM=500 → norm=0.5; weight=0.25 → +0.125;
        # menos o offset revenue-neutral (-0.10) → 0.025.
        f = compute_fitness(
            _schedule(
                total_tardiness_transport_hours=250,
                total_tardiness_hours=0,  # legacy zeroed
            ),
            cfg,
        )
        assert f == pytest.approx(0.025)

    def test_v2_safety_violated_adds_full_million(self):
        # Even in v2 mode, the safety penalty is unscaled (1e6).
        cfg = FitnessConfig(use_v2_weights=True)
        f = compute_fitness(_schedule(safety_violated=True), cfg)
        assert f == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# 4) _rework_penalty_hours — factor <= 1.0 short-circuit + threshold boundary
# ---------------------------------------------------------------------------

class TestReworkPenaltyHours:
    """Pin Sprint Q.13.E E.1 capacity-correction:

    * factor == 1.0 → 0.0 (default — no penalty)
    * factor < 1.0  → 0.0 (defensive)
    * factor > 1.0 + phase rate >= threshold → contribution
    * factor > 1.0 + phase rate <  threshold → 0.0
    """

    def test_unity_factor_returns_zero(self):
        # ``cfg.rework_capacity_factor <= 1.0 → 0`` — pin the boundary at 1.0.
        cfg = FitnessConfig(
            rework_capacity_factor=1.0,
            phase_error_rates={"PH_X": 0.9},
        )
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 600}])
        assert _rework_penalty_hours(s, cfg) == 0.0

    def test_sub_unity_factor_returns_zero(self):
        # ``<= 1.0`` includes the < case too.
        cfg = FitnessConfig(
            rework_capacity_factor=0.8,
            phase_error_rates={"PH_X": 0.9},
        )
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 600}])
        assert _rework_penalty_hours(s, cfg) == 0.0

    def test_no_error_rates_returns_zero(self):
        # Empty ``phase_error_rates`` → bail out.
        cfg = FitnessConfig(rework_capacity_factor=1.5)
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 600}])
        assert _rework_penalty_hours(s, cfg) == 0.0

    def test_below_threshold_skipped(self):
        # Phase rate 0.39 < default threshold 0.40 → no contribution.
        cfg = FitnessConfig(
            rework_capacity_factor=1.5,
            phase_error_rates={"PH_X": 0.39},
        )
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 600}])
        assert _rework_penalty_hours(s, cfg) == 0.0

    def test_threshold_inclusive(self):
        # Pin the ``< threshold`` comparison: rate equal to threshold IS
        # included. The function reads ``if rate < threshold: continue``
        # so equal rates fall through and add cost.
        cfg = FitnessConfig(
            rework_capacity_factor=1.5,
            phase_error_rates={"PH_X": 0.40},
        )
        # 600min = 10h; extra_factor = 0.5; contribution = 5.0h.
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 600}])
        assert _rework_penalty_hours(s, cfg) == pytest.approx(5.0)

    def test_extra_factor_is_factor_minus_one(self):
        # Pin ``extra_factor = rework_capacity_factor - 1.0``.
        # factor=2.0 → extra=1.0; 1h → 1h cost.
        cfg = FitnessConfig(
            rework_capacity_factor=2.0,
            phase_error_rates={"PH_X": 0.9},
        )
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 60}])
        assert _rework_penalty_hours(s, cfg) == pytest.approx(1.0)

    def test_zero_duration_skipped(self):
        # ``duration_min <= 0: continue`` — pin the boundary at 0.
        cfg = FitnessConfig(
            rework_capacity_factor=1.5,
            phase_error_rates={"PH_X": 0.9},
        )
        s = _schedule(operations=[{"phase_id": "PH_X", "duration_minutes": 0}])
        assert _rework_penalty_hours(s, cfg) == 0.0

    def test_missing_phase_id_skipped(self):
        cfg = FitnessConfig(
            rework_capacity_factor=1.5,
            phase_error_rates={"PH_X": 0.9},
        )
        s = _schedule(operations=[{"phase_id": None, "duration_minutes": 60}])
        assert _rework_penalty_hours(s, cfg) == 0.0


# ---------------------------------------------------------------------------
# 5) Truck consolidation — ``> 0`` guard
# ---------------------------------------------------------------------------

class TestTruckConsolidationGuard:
    """Pin the ``if cfg.truck_consolidation_weight > 0`` branch."""

    def test_zero_weight_skips_penalty(self):
        # Default weight=0.0 → schedule's truck_consolidation_penalty_h ignored.
        cfg = FitnessConfig()
        s = _schedule(makespan_hours=5, truck_consolidation_penalty_h=100)
        assert compute_fitness(s, cfg) == 5.0  # only makespan, no truck term

    def test_positive_weight_adds_penalty(self):
        cfg = FitnessConfig(truck_consolidation_weight=2.0)
        s = _schedule(makespan_hours=0, truck_consolidation_penalty_h=10)
        # 2.0 * 10 = 20.0
        assert compute_fitness(s, cfg) == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 6) build_op_features_for_risk — int/float fallbacks, ``or 1``
# ---------------------------------------------------------------------------

class TestBuildOpFeaturesForRisk:
    """Pin defaults: missing fields collapse to neutral values."""

    def test_empty_dict_neutral_defaults(self):
        # ``len(op_record.get("workers", [])) or 1`` → team_size=1.
        # All ints land at 0 / 1; floats at 0.0; strings at "".
        out = build_op_features_for_risk({})
        assert out == {
            "modelo_id": "",
            "fase_id": "",
            "team_size": 1,
            "mold_pocket_count": 1,
            "phase_error_rate": 0.0,
            "queue_depth": 0,
        }

    def test_empty_workers_list_collapses_to_one(self):
        # Empty list → ``len(...) or 1`` = 1. Pins the ``or 1`` clause —
        # a mutation that drops it would yield team_size=0.
        out = build_op_features_for_risk({"workers": []})
        assert out["team_size"] == 1

    def test_workers_list_size_counted(self):
        out = build_op_features_for_risk({"workers": ["w1", "w2", "w3"]})
        assert out["team_size"] == 3

    def test_modelo_id_falls_back_to_model_id(self):
        # The ``or`` chain: modelo_id → model_id → "".
        out = build_op_features_for_risk({"model_id": "MOD42"})
        assert out["modelo_id"] == "MOD42"

    def test_fase_id_falls_back_to_phase_id(self):
        out = build_op_features_for_risk({"phase_id": "PH7"})
        assert out["fase_id"] == "PH7"

    def test_pocket_count_zero_falls_back_to_one(self):
        # ``int(op.get("mold_pocket_count", 1) or 1)`` — 0 is falsy.
        out = build_op_features_for_risk({"mold_pocket_count": 0})
        assert out["mold_pocket_count"] == 1

    def test_phase_error_rate_zero_kept_as_float(self):
        # ``float(op.get("phase_error_rate", 0.0) or 0.0)`` — 0 stays 0.0.
        out = build_op_features_for_risk({"phase_error_rate": 0})
        assert out["phase_error_rate"] == 0.0
        assert isinstance(out["phase_error_rate"], float)

    def test_queue_depth_passed_through(self):
        out = build_op_features_for_risk({"queue_depth": 7})
        assert out["queue_depth"] == 7


# ---------------------------------------------------------------------------
# 7) compute_fitness branch dispatch — use_v2_weights flag
# ---------------------------------------------------------------------------

class TestDispatchBranch:
    """Pin that ``use_v2_weights`` actually flips the implementation."""

    def test_use_v2_false_calls_legacy(self):
        # Legacy mode at makespan=1 → exactly 1.0 (w_makespan=1.0).
        cfg = FitnessConfig(use_v2_weights=False)
        assert compute_fitness(_schedule(makespan_hours=1), cfg) == 1.0

    def test_use_v2_true_calls_v2(self):
        # V2 mode at makespan=1 → 1/1000 * 0.20 = 0.0002, menos o offset
        # revenue-neutral (-0.10*1.0, sem target) → -0.0998 — drasticamente
        # diferente de legacy (1.0). Se o dispatch for mutado (flipped ou
        # constant-True/False), isto apanha.
        cfg = FitnessConfig(use_v2_weights=True)
        assert compute_fitness(_schedule(makespan_hours=1), cfg) == pytest.approx(
            -0.0998,
        )

    def test_safety_penalty_applied_in_both_modes(self):
        # ``safety_violated`` adds penalty AFTER the dispatch; pin that the
        # 1e6 choke is added regardless of mode. Usa o DELTA vs a mesma
        # config sem violacao para isolar a penalty do offset revenue-neutral
        # do v2 (-0.10), pinando a magnitude exacta em ambos os modos.
        cfg_legacy = FitnessConfig(use_v2_weights=False)
        cfg_v2 = FitnessConfig(use_v2_weights=True)
        legacy_delta = (
            compute_fitness(_schedule(safety_violated=True), cfg_legacy)
            - compute_fitness(_schedule(), cfg_legacy)
        )
        v2_delta = (
            compute_fitness(_schedule(safety_violated=True), cfg_v2)
            - compute_fitness(_schedule(), cfg_v2)
        )
        assert legacy_delta == pytest.approx(1_000_000.0)
        assert v2_delta == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# 8) Direct _v2_fitness call — quality risk path
# ---------------------------------------------------------------------------

class TestV2FitnessQualityRisk:
    """Pin ``_v2_fitness`` quality-risk hard-hit accounting."""

    # NOTA: estes testes chamam `_v2_fitness` directamente, logo incluem
    # sempre o termo revenue_target_alignment. Sem `daily_revenue_target_eur`
    # o score é 1.0 (neutro) e contribui -0.10 (= -w_v2_revenue_target_alignment
    # * 1.0) — um offset constante que se soma a cada expected abaixo.

    def test_v2_mean_risk_uses_quality_risk_mean(self):
        # Without a predictor, ``_v2_fitness`` reads ``quality_risk_mean``
        # before falling back to ``quality_risk``.
        cfg = FitnessConfig()
        s = _schedule(quality_risk_mean=0.5)
        # weight=0.10 → +0.05; menos o offset revenue-neutral (-0.10) → -0.05.
        assert _v2_fitness(s, cfg) == pytest.approx(-0.05)

    def test_v2_quality_risk_fallback_to_legacy_field(self):
        # When ``quality_risk_mean`` absent, falls back to ``quality_risk``.
        cfg = FitnessConfig()
        s = _schedule(quality_risk=0.5)
        # +0.05 (0.10*0.5) menos offset revenue-neutral (-0.10) → -0.05.
        assert _v2_fitness(s, cfg) == pytest.approx(-0.05)

    def test_v2_idle_norm_uses_400h_reference(self):
        # _NORM_IDLE_H=400. idle=200 → norm=0.5; weight=0.15 → +0.075;
        # menos offset revenue-neutral (-0.10) → -0.025.
        cfg = FitnessConfig()
        s = _schedule(total_idle_hours=200)
        assert _v2_fitness(s, cfg) == pytest.approx(-0.025)

    def test_v2_setups_norm_uses_50_reference(self):
        # _NORM_SETUPS=50. setups=25 → norm=0.5; w_v2_setup_time=0.10
        # (Q.115.X7, era 0.15) → +0.05; menos offset revenue-neutral → -0.05.
        cfg = FitnessConfig()
        s = _schedule(setups=25)
        assert _v2_fitness(s, cfg) == pytest.approx(-0.05)
