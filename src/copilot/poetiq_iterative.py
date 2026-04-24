"""
ProdPlan ONE — POETIQ iterative orchestrator (Sprint F.3)
===========================================================

Thin wiring layer on top of :class:`POETIQLoop` (Sprint P.13 scaffold
in :mod:`src.copilot.poetiq_expanded`). The scaffold already knows how
to run ``Propose → Optimize → Evaluate → Iterate → Qualify`` with
pluggable callbacks. This module provides:

* :func:`run_iterative_poetiq` — a convenience entry point that wires
  the four default callbacks together and returns the expanded result.
* :func:`default_iterator` — a **deterministic** critique-to-delta
  refinement. No LLM calls, so tests can exercise the loop without an
  Ollama service. The refinement picks tweaks from ``critique.issues``:
  tardiness complaints add horizon days, utilisation complaints raise
  shift_mode, setup complaints flip routing_variant. A real LLM
  iterator can replace this via the ``iterator=`` arg.
* :func:`default_qualifier` — admits a delta into the archive when the
  final score exceeds ``QUALIFY_THRESHOLD`` AND the safety-net wasn't
  triggered.

Why default_iterator is rule-based
----------------------------------
Sprint F.3's stated target is "2-5 iterations with kernel feedback".
The *signal* the loop needs is a better next delta on every round,
not necessarily an LLM-generated one. A deterministic iterator gives
reliable tests today (no Ollama fixture) and a known baseline to beat
when we plug the real LLM refiner in Sprint H / I. The interface is
identical (``iterator(delta, critique) → delta | None``) so swapping
is a one-line change.

The :class:`POETIQLoop` invariants stay intact: ``max_iterations`` is
a hard cap, ``good_enough_score`` is the early-exit threshold, and
every callback is wrapped in ``try/except`` by the loop so one bad
critique never takes the whole pipeline down.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional

from src.copilot.poetiq_expanded import (
    CritiqueReport,
    Evaluator,
    Iterator as IteratorFn,
    Optimizer,
    PerturbationReport,
    POETIQExpandedResult,
    POETIQLoop,
    Qualifier,
    Tester,
    default_perturbation_tester,
)

logger = logging.getLogger(__name__)


GOOD_ENOUGH_SCORE: float = 0.85
QUALIFY_THRESHOLD: float = 0.80


# ═══════════════════════════════════════════════════════════════════════════
# Default callbacks
# ═══════════════════════════════════════════════════════════════════════════


def default_kernel_score(schedule: Mapping[str, Any]) -> float:
    """Fitness→[0, 1] rubric, duplicated from :func:`src.copilot.poetiq
    ._kernel_score` so the iterative pipeline doesn't need the FastAPI
    module on its import graph.

    Three axes, each clamped to [0, 1], averaged:

    * **no_tardy** — 1.0 when no late orders, 0.5 otherwise.
    * **utilization** — ``avg_utilization / 100`` (raw percent).
    * **safety_net** — penalise hard when triggered (0.2) else 1.0.
    """
    no_tardy = 1.0 if int(schedule.get("num_late_orders", 0)) == 0 else 0.5
    util = max(0.0, min(1.0, float(schedule.get("avg_utilization", 0.0)) / 100.0))
    safety = 0.2 if bool(schedule.get("safety_net_triggered", False)) else 1.0
    return (no_tardy + util + safety) / 3.0


def default_evaluator(
    schedule: Mapping[str, Any],
    *,
    kernel_fn: Callable[[Mapping[str, Any]], float] = default_kernel_score,
    llm_qual: float = 1.0,
) -> CritiqueReport:
    """Kernel-only evaluator: produces a CritiqueReport with a
    narrative summarising the headline KPIs and a per-axis issue list
    that :func:`default_iterator` can parse.

    The ``llm_qual`` knob lets callers inject a structured LLM
    assessment (0..1) when one is available; the composite ``score``
    is then ``0.7 × kernel + 0.3 × llm_qual`` (matching Blueprint
    v2.0 §5.6).
    """
    kernel = float(kernel_fn(schedule))
    issues: List[str] = []

    if int(schedule.get("num_late_orders", 0)) > 0:
        issues.append("tardiness:has_late_orders")
    util_pct = float(schedule.get("avg_utilization", 0.0))
    if util_pct < 60.0:
        issues.append("utilization:below_60_pct")
    if bool(schedule.get("safety_net_triggered", False)):
        issues.append("safety:triggered")
    setups = int(schedule.get("setups", 0))
    if setups >= 20:
        issues.append("setup:high_count")

    narrative = (
        f"makespan={schedule.get('makespan_hours', 0):.1f}h, "
        f"tardy={schedule.get('num_late_orders', 0)}, "
        f"util={util_pct:.1f}%, setups={setups}"
    )

    return CritiqueReport(
        kernel_score=kernel,
        llm_qual=llm_qual,
        narrative=narrative,
        issues=issues,
    )


def default_iterator(
    delta: Mapping[str, Any],
    critique: CritiqueReport,
) -> Optional[Dict[str, Any]]:
    """Deterministic refinement: translate ``critique.issues`` into a
    fresh delta dict. Returns ``None`` when no issue is actionable
    so :class:`POETIQLoop` exits the loop cleanly.

    The delta follows the same shape as :class:`src.copilot.poetiq
    .POETIQDelta.patch`: a dict of hints the scheduler-side handler
    can interpret. We accumulate hints under ``iteration_hints`` so
    the optimizer can read them without confusing the original patch.
    """
    if not critique.issues:
        return None

    new_delta = deepcopy(dict(delta))
    hints = dict(new_delta.get("iteration_hints") or {})

    changed = False
    for issue in critique.issues:
        if issue.startswith("tardiness:"):
            hints["extend_horizon_days"] = int(hints.get("extend_horizon_days", 0)) + 2
            changed = True
        elif issue.startswith("utilization:"):
            # Ask the optimizer to bump the shift mode toward double shift.
            hints["shift_mode"] = min(2.0, float(hints.get("shift_mode", 1.0)) + 0.5)
            changed = True
        elif issue.startswith("setup:"):
            # Flip routing variant if not already.
            hints["routing_variant"] = 1 if int(hints.get("routing_variant", 0)) == 0 else 0
            changed = True
        elif issue.startswith("safety:"):
            # Safety is almost always an infeasibility; widen the horizon
            # and ask for an extra generation budget.
            hints["extend_horizon_days"] = int(hints.get("extend_horizon_days", 0)) + 5
            hints["extra_generations"] = int(hints.get("extra_generations", 0)) + 20
            changed = True

    if not changed:
        return None

    new_delta["iteration_hints"] = hints
    return new_delta


def default_qualifier(
    schedule: Mapping[str, Any],
    critique: CritiqueReport,
    *,
    threshold: float = QUALIFY_THRESHOLD,
) -> bool:
    """Admit when the composite score beats the threshold AND the
    safety-net is clean. A schedule that hits the safety penalty is
    never qualified, even if kernel + llm happen to score well
    together — Blueprint v2.0 §5.6 says qualification gates on both
    signals."""
    if bool(schedule.get("safety_net_triggered", False)):
        return False
    return critique.score >= threshold


# ═══════════════════════════════════════════════════════════════════════════
# Public entry
# ═══════════════════════════════════════════════════════════════════════════


def run_iterative_poetiq(
    *,
    proposed_delta: Dict[str, Any],
    optimizer: Optimizer,
    evaluator: Optional[Evaluator] = None,
    iterator: Optional[IteratorFn] = None,
    tester: Optional[Tester] = default_perturbation_tester,
    qualifier: Optional[Qualifier] = None,
    max_iterations: int = 3,
    good_enough_score: float = GOOD_ENOUGH_SCORE,
) -> POETIQExpandedResult:
    """Run the expanded POETIQ loop with sensible defaults.

    The only mandatory callback is ``optimizer`` (the thing that turns
    a delta into a schedule dict). Everything else has a deterministic
    default so unit tests can exercise the loop without any LLM /
    external service.

    Callers wanting an LLM-backed critique or iterator pass their own
    function here — the signature matches :class:`POETIQLoop`'s
    ``Evaluator`` / ``Iterator`` protocol.
    """
    evaluator = evaluator or default_evaluator
    iterator = iterator or default_iterator
    qualifier = qualifier or default_qualifier

    loop = POETIQLoop(
        optimizer=optimizer,
        evaluator=evaluator,
        tester=tester,
        iterator=iterator,
        qualifier=qualifier,
        max_iterations=max_iterations,
        good_enough_score=good_enough_score,
    )
    result = loop.run_expanded(proposed_delta)
    logger.info(
        "POETIQ iterative: iterations=%d final_score=%.3f qualified=%s",
        result.iterations, result.final_score, result.qualified,
    )
    return result


__all__ = [
    "GOOD_ENOUGH_SCORE",
    "QUALIFY_THRESHOLD",
    "default_evaluator",
    "default_iterator",
    "default_kernel_score",
    "default_qualifier",
    "run_iterative_poetiq",
]
