"""Sprint E.4 — PreferenceAdapter + FitnessConfig integration.

Covers:

* Each rule type evaluator in ``preference_adapter``:
  - temporal_block applied per op on blocked weekday
  - phase_threshold applied per op short-staffed in the flagged phase
  - operator_affinity rewards preferred worker, penalises absence
  - tradeoff_preference no-op at fitness level (handled by Camada 2)
* FitnessConfig wiring — a schedule with no rules equals the un-penalised
  legacy fitness; adding a matching temporal_block rule raises fitness
  by exactly ``TEMPORAL_PER_OP`` per violating op.
* Unknown rule type + malformed predicate never crash the hot path.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from src.plan.cpo.fitness import FitnessConfig, compute_fitness
from src.plan.cpo.preference_adapter import (
    AFFINITY_MISS_PENALTY,
    AFFINITY_REWARD,
    TEMPORAL_PER_OP,
    THRESHOLD_PER_SHORT_OP,
    compute_preference_penalty,
)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _op(
    *,
    phase_id: str = "LAMINAGEM",
    workers: List[str] | None = None,
    start_time: str = "2026-04-24T08:00:00",  # Friday (ISO weekday 5)
) -> Dict[str, Any]:
    return {
        "operation_id": "op-1",
        "order_id": "ord-1",
        "phase_id": phase_id,
        "workers": workers or ["w1", "w2"],
        "start_time": start_time,
    }


def _schedule(ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Minimal schedule envelope the fitness function consumes."""
    return {
        "operations": list(ops),
        "makespan_hours": 10.0,
        "total_tardiness_hours": 0.0,
        "setups": 0,
        "quality_risk": 0.0,
    }


# ─── Temporal block ───────────────────────────────────────────────────────


def test_temporal_block_penalises_each_op_on_blocked_weekday():
    rule = {"type": "temporal_block", "predicate": {"weekday": 5}}
    ops = [
        _op(start_time="2026-04-24T08:00:00"),  # Friday
        _op(start_time="2026-04-24T12:00:00"),  # Friday
        _op(start_time="2026-04-23T08:00:00"),  # Thursday — not penalised
    ]
    penalty = compute_preference_penalty(_schedule(ops), [rule])
    assert penalty == pytest.approx(2 * TEMPORAL_PER_OP)


def test_temporal_block_with_bad_predicate_is_noop():
    rule = {"type": "temporal_block", "predicate": {"weekday": "not-a-day"}}
    ops = [_op()]
    assert compute_preference_penalty(_schedule(ops), [rule]) == 0.0


def test_temporal_block_tolerates_missing_start_time():
    rule = {"type": "temporal_block", "predicate": {"weekday": 5}}
    op = _op()
    del op["start_time"]
    # Missing start_time → no weekday → no penalty
    assert compute_preference_penalty(_schedule([op]), [rule]) == 0.0


# ─── Phase threshold ─────────────────────────────────────────────────────


def test_phase_threshold_penalises_only_short_ops_in_flagged_phase():
    rule = {
        "type": "phase_threshold",
        "predicate": {"phase_id": "PINTURA", "min_team_size": 3},
    }
    ops = [
        _op(phase_id="PINTURA", workers=["w1"]),           # short → penalty
        _op(phase_id="PINTURA", workers=["w1", "w2"]),     # short → penalty
        _op(phase_id="PINTURA", workers=["w1", "w2", "w3"]),  # OK
        _op(phase_id="LAMINAGEM", workers=["w1"]),         # different phase
    ]
    penalty = compute_preference_penalty(_schedule(ops), [rule])
    assert penalty == pytest.approx(2 * THRESHOLD_PER_SHORT_OP)


def test_phase_threshold_requires_valid_predicate():
    rule = {"type": "phase_threshold", "predicate": {"phase_id": "X", "min_team_size": 0}}
    ops = [_op(phase_id="X", workers=[])]
    assert compute_preference_penalty(_schedule(ops), [rule]) == 0.0


# ─── Operator affinity ───────────────────────────────────────────────────


def test_operator_affinity_rewards_preferred_worker_and_penalises_absence():
    rule = {
        "type": "operator_affinity",
        "predicate": {"phase_id": "LAMINAGEM", "worker_id": "paulo"},
    }
    ops = [
        _op(phase_id="LAMINAGEM", workers=["paulo", "ana"]),  # reward
        _op(phase_id="LAMINAGEM", workers=["ana", "joao"]),   # miss penalty
        _op(phase_id="PINTURA", workers=["paulo"]),           # different phase
    ]
    penalty = compute_preference_penalty(_schedule(ops), [rule])
    assert penalty == pytest.approx(AFFINITY_REWARD + AFFINITY_MISS_PENALTY)


def test_operator_affinity_reward_is_negative_so_preferred_assignment_lowers_fitness():
    """Sanity: a schedule that places the preferred worker always beats
    one that never does, all else equal."""
    rule = {
        "type": "operator_affinity",
        "predicate": {"phase_id": "LAMINAGEM", "worker_id": "paulo"},
    }
    good = [_op(workers=["paulo", "ana"]), _op(workers=["paulo", "ana"])]
    bad = [_op(workers=["ana", "joao"]), _op(workers=["ana", "joao"])]
    p_good = compute_preference_penalty(_schedule(good), [rule])
    p_bad = compute_preference_penalty(_schedule(bad), [rule])
    assert p_good < p_bad


# ─── Tradeoff preference (no-op at fitness level) ────────────────────────


def test_tradeoff_preference_is_skipped_at_fitness_level():
    rule = {
        "type": "tradeoff_preference",
        "predicate": {"kpi_improved": "setups", "kpi_sacrificed": "throughput_eur_day"},
    }
    ops = [_op()]
    # AdaptiveFitnessWeights handles this category — this adapter must
    # stay silent to avoid double-counting.
    assert compute_preference_penalty(_schedule(ops), [rule]) == 0.0


# ─── Robustness ───────────────────────────────────────────────────────────


def test_unknown_rule_type_does_not_crash_and_contributes_zero():
    rule = {"type": "mystery_constraint", "predicate": {}}
    ops = [_op()]
    assert compute_preference_penalty(_schedule(ops), [rule]) == 0.0


def test_malformed_predicate_is_ignored():
    rule = {"type": "temporal_block", "predicate": "not-a-dict"}
    ops = [_op()]
    assert compute_preference_penalty(_schedule(ops), [rule]) == 0.0


def test_empty_rules_yields_zero_penalty():
    ops = [_op()]
    assert compute_preference_penalty(_schedule(ops), []) == 0.0


def test_empty_operations_yields_zero_penalty():
    rule = {"type": "temporal_block", "predicate": {"weekday": 5}}
    assert compute_preference_penalty({"operations": []}, [rule]) == 0.0


# ─── FitnessConfig integration ───────────────────────────────────────────


def test_fitness_without_preference_rules_matches_legacy_baseline():
    """Baseline: no rules → fitness is the legacy weighted sum alone."""
    schedule = _schedule([_op()])
    baseline = compute_fitness(schedule, FitnessConfig())
    with_empty_rules = compute_fitness(
        schedule, FitnessConfig(preference_rules=[]),
    )
    assert with_empty_rules == pytest.approx(baseline)


def test_fitness_grows_by_temporal_per_op_when_rule_matches():
    ops = [
        _op(start_time="2026-04-24T08:00:00"),  # Friday
        _op(start_time="2026-04-24T10:00:00"),  # Friday
    ]
    schedule = _schedule(ops)
    rule = {"type": "temporal_block", "predicate": {"weekday": 5}}
    baseline = compute_fitness(schedule, FitnessConfig())
    with_rule = compute_fitness(
        schedule, FitnessConfig(preference_rules=[rule]),
    )
    # Expect exactly 2 * TEMPORAL_PER_OP additional penalty.
    assert with_rule - baseline == pytest.approx(2 * TEMPORAL_PER_OP)


def test_fitness_absorbs_adapter_exceptions_without_crashing():
    """If something in the adapter path explodes (e.g. custom rule with
    weird type), the fitness function still returns a number. Simulate
    by passing a rule dict that our adapter's _get() can't parse."""
    ops = [_op()]
    schedule = _schedule(ops)
    weird_rule = {"type": "temporal_block", "predicate": None}
    baseline = compute_fitness(schedule, FitnessConfig())
    with_weird = compute_fitness(
        schedule, FitnessConfig(preference_rules=[weird_rule]),
    )
    # No penalty applies (predicate is None so the adapter skips it),
    # but crucially no exception leaks to the caller.
    assert with_weird == pytest.approx(baseline)
