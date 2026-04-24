"""Sprint F.3 — iterative POETIQ orchestrator.

Covers:

* ``default_kernel_score`` rubric — no-tardy bonus, utilisation, safety
  penalty.
* ``default_evaluator`` emits the right ``issues`` codes for each
  KPI violation and computes the composite score.
* ``default_iterator`` maps each issue class to the documented delta
  hint.
* ``default_qualifier`` gates on threshold AND the safety-net.
* ``run_iterative_poetiq`` early-exits when the score already beats
  the gate; iterates when the optimizer improves monotonically; stops
  at ``max_iterations``; records iterations + final score + qualified
  flag.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping

import pytest

from src.copilot.poetiq_expanded import CritiqueReport
from src.copilot.poetiq_iterative import (
    GOOD_ENOUGH_SCORE,
    QUALIFY_THRESHOLD,
    default_evaluator,
    default_iterator,
    default_kernel_score,
    default_qualifier,
    run_iterative_poetiq,
)


# ─── kernel_score ─────────────────────────────────────────────────────────


def test_kernel_score_rewards_no_tardy_and_high_util():
    good = {"num_late_orders": 0, "avg_utilization": 90.0}
    bad = {"num_late_orders": 3, "avg_utilization": 40.0}
    assert default_kernel_score(good) > default_kernel_score(bad)


def test_kernel_score_penalises_safety_net():
    clean = {"num_late_orders": 0, "avg_utilization": 80.0, "safety_net_triggered": False}
    broken = dict(clean, safety_net_triggered=True)
    assert default_kernel_score(broken) < default_kernel_score(clean)


# ─── evaluator ────────────────────────────────────────────────────────────


def test_evaluator_flags_tardiness_utilization_setup_safety():
    schedule = {
        "num_late_orders": 2,
        "avg_utilization": 45.0,
        "setups": 25,
        "safety_net_triggered": True,
        "makespan_hours": 260.0,
    }
    crit = default_evaluator(schedule)
    codes = {i.split(":")[0] for i in crit.issues}
    assert codes == {"tardiness", "utilization", "setup", "safety"}
    assert "makespan=260.0h" in crit.narrative


def test_evaluator_composite_score_formula():
    schedule = {"num_late_orders": 0, "avg_utilization": 80.0}
    crit = default_evaluator(schedule, llm_qual=0.5)
    # 0.7 × kernel + 0.3 × 0.5
    assert crit.score == pytest.approx(0.7 * crit.kernel_score + 0.3 * 0.5)


# ─── iterator ─────────────────────────────────────────────────────────────


def test_iterator_no_issues_returns_none():
    delta: Dict[str, Any] = {"entity_type": "x", "patch": {}}
    crit = CritiqueReport(kernel_score=0.9, llm_qual=1.0, narrative="ok", issues=[])
    assert default_iterator(delta, crit) is None


def test_iterator_adds_horizon_on_tardiness():
    delta: Dict[str, Any] = {"entity_type": "x", "patch": {}}
    crit = CritiqueReport(
        kernel_score=0.4, llm_qual=0.8, narrative="", issues=["tardiness:has_late_orders"],
    )
    new = default_iterator(delta, crit)
    assert new is not None
    assert new["iteration_hints"]["extend_horizon_days"] == 2


def test_iterator_bumps_shift_mode_on_utilization():
    delta: Dict[str, Any] = {"entity_type": "x", "patch": {}}
    crit = CritiqueReport(
        kernel_score=0.5, llm_qual=1.0, narrative="", issues=["utilization:below_60_pct"],
    )
    new = default_iterator(delta, crit)
    assert new["iteration_hints"]["shift_mode"] == 1.5


def test_iterator_flips_routing_on_setup_issue():
    delta: Dict[str, Any] = {
        "entity_type": "x", "patch": {},
        "iteration_hints": {"routing_variant": 0},
    }
    crit = CritiqueReport(
        kernel_score=0.5, llm_qual=1.0, narrative="", issues=["setup:high_count"],
    )
    new = default_iterator(delta, crit)
    assert new["iteration_hints"]["routing_variant"] == 1


def test_iterator_safety_widens_horizon_and_generations():
    delta: Dict[str, Any] = {"entity_type": "x", "patch": {}}
    crit = CritiqueReport(
        kernel_score=0.2, llm_qual=0.5, narrative="", issues=["safety:triggered"],
    )
    new = default_iterator(delta, crit)
    hints = new["iteration_hints"]
    assert hints["extend_horizon_days"] == 5
    assert hints["extra_generations"] == 20


# ─── qualifier ────────────────────────────────────────────────────────────


def test_qualifier_rejects_safety_triggered_even_with_high_score():
    crit = CritiqueReport(kernel_score=0.95, llm_qual=0.95, narrative="", issues=[])
    assert default_qualifier(
        {"safety_net_triggered": True}, crit,
    ) is False


def test_qualifier_accepts_clean_high_score():
    crit = CritiqueReport(kernel_score=0.95, llm_qual=0.9, narrative="", issues=[])
    assert default_qualifier(
        {"safety_net_triggered": False}, crit,
    ) is True


def test_qualifier_rejects_below_threshold():
    crit = CritiqueReport(kernel_score=0.4, llm_qual=0.3, narrative="", issues=[])
    assert default_qualifier({}, crit) is False


# ─── run_iterative_poetiq ─────────────────────────────────────────────────


def _scheduled(
    *,
    tardy: int = 0,
    util: float = 90.0,
    setups: int = 10,
    safety: bool = False,
    makespan: float = 200.0,
) -> Dict[str, Any]:
    return {
        "num_late_orders": tardy,
        "avg_utilization": util,
        "setups": setups,
        "safety_net_triggered": safety,
        "makespan_hours": makespan,
        "operations": [],
    }


def test_early_exit_when_first_schedule_beats_gate():
    """Kernel 1.0 + llm 1.0 → score 1.0 ≥ GOOD_ENOUGH_SCORE → stop after iter 1."""
    optimizer_calls = {"n": 0}

    def optimizer(_delta: Mapping[str, Any]) -> Dict[str, Any]:
        optimizer_calls["n"] += 1
        return _scheduled(tardy=0, util=100.0)

    result = run_iterative_poetiq(
        proposed_delta={"entity_type": "x", "patch": {}},
        optimizer=optimizer,
        tester=None,
        max_iterations=5,
    )
    assert result.iterations == 1
    assert optimizer_calls["n"] == 1
    assert result.final_score >= GOOD_ENOUGH_SCORE
    assert result.qualified is True


def test_loop_stops_at_max_iterations_when_critique_never_satisfied():
    def stuck_optimizer(_delta: Mapping[str, Any]) -> Dict[str, Any]:
        return _scheduled(tardy=3, util=45.0)

    result = run_iterative_poetiq(
        proposed_delta={"entity_type": "x", "patch": {}},
        optimizer=stuck_optimizer,
        tester=None,
        max_iterations=3,
    )
    assert result.iterations == 3
    assert len(result.critiques) == 3
    assert result.qualified is False


def test_loop_uses_iterator_to_refine_delta():
    """Optimizer looks at `iteration_hints.extend_horizon_days` and
    reduces tardiness proportionally. The loop should then pass the
    gate on a later iteration."""

    def responsive_optimizer(delta: Mapping[str, Any]) -> Dict[str, Any]:
        hints = (delta.get("iteration_hints") or {}) if isinstance(delta, Mapping) else {}
        extend = int(hints.get("extend_horizon_days", 0))
        tardy = max(0, 3 - extend)  # 3 late → 1 → 0 after two iterations
        util = 60.0 + 15.0 * extend
        return _scheduled(tardy=tardy, util=min(util, 95.0))

    result = run_iterative_poetiq(
        proposed_delta={"entity_type": "x", "patch": {}},
        optimizer=responsive_optimizer,
        tester=None,
        max_iterations=5,
    )
    # At least two iterations should be needed to reach the gate; the
    # loop terminated when either score ≥ gate or iterator returned None.
    assert result.iterations >= 2
    assert result.final_score >= GOOD_ENOUGH_SCORE


def test_qualifier_respects_threshold():
    """Score just below QUALIFY_THRESHOLD → qualified=False even with
    no safety violation."""
    def mediocre(_delta: Mapping[str, Any]) -> Dict[str, Any]:
        return _scheduled(tardy=1, util=50.0)

    result = run_iterative_poetiq(
        proposed_delta={"entity_type": "x", "patch": {}},
        optimizer=mediocre,
        tester=None,
        max_iterations=1,
    )
    assert result.qualified is False
    assert result.final_score < QUALIFY_THRESHOLD


def test_tester_runs_when_supplied():
    """The perturbation tester runs after the loop ends."""
    def opt(_delta: Mapping[str, Any]) -> Dict[str, Any]:
        return _scheduled(tardy=0, util=95.0)

    tester_calls = {"n": 0}

    def fake_tester(_sched: Mapping[str, Any]) -> list:
        tester_calls["n"] += 1
        return []

    result = run_iterative_poetiq(
        proposed_delta={"entity_type": "x", "patch": {}},
        optimizer=opt,
        tester=fake_tester,
        max_iterations=1,
    )
    assert tester_calls["n"] == 1
    assert result.perturbations == []
