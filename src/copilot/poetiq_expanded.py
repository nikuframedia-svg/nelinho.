"""
ProdPlan ONE — POETIQ Expanded Loop (Sprint P.13)
==================================================

Blueprint v2.0 §5.6 spells out the six letters:

    PROPOSE  → LLM generates a scenario (informed by RLM exploration)
    OPTIMIZE → Kernel CPO runs: greedy → GA → MAP-Elites → CP-SAT
    EVALUATE → Analytical rubric + MAP-Elites archive comparison
    TEST     → Perturbation simulation ("what if machine X fails?")
    ITERATE  → Refinement driven by the critique
    QUALIFY  → Admit into the MAP-Elites grid + memory

The Sprint K MVP (`copilot/poetiq.py`) covers propose→optimize→evaluate as a
single-shot call. This module stacks the TEST + ITERATE + QUALIFY pieces on
top, returning a richer `POETIQExpandedResult` so the UI can show the
critique trail.

Keeping this in a separate module means Sprint K's stable API doesn't move;
the expanded loop is opt-in (copilot calls `run_expanded()` instead of the
MVP endpoint).
"""

from __future__ import annotations

import logging
import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CritiqueReport:
    """Output of the EVALUATE step."""

    kernel_score: float
    llm_qual: float = 1.0
    narrative: str = ""
    issues: List[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        # Blueprint v2.0 §5.6 composite.
        return 0.7 * self.kernel_score + 0.3 * self.llm_qual


@dataclass
class PerturbationReport:
    """Output of the TEST step."""

    scenario: str
    kernel_score_delta: float
    ops_affected: int
    robust: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "kernel_score_delta": round(self.kernel_score_delta, 4),
            "ops_affected": self.ops_affected,
            "robust": self.robust,
        }


@dataclass
class POETIQExpandedResult:
    proposed_delta: Dict[str, Any]
    final_schedule: Dict[str, Any]
    iterations: int
    critiques: List[CritiqueReport] = field(default_factory=list)
    perturbations: List[PerturbationReport] = field(default_factory=list)
    qualified: bool = False
    qualify_reason: str = ""
    final_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposed_delta": self.proposed_delta,
            "iterations": self.iterations,
            "critiques": [
                {
                    "kernel_score": round(c.kernel_score, 4),
                    "llm_qual": round(c.llm_qual, 4),
                    "score": round(c.score, 4),
                    "narrative": c.narrative,
                    "issues": c.issues,
                }
                for c in self.critiques
            ],
            "perturbations": [p.as_dict() for p in self.perturbations],
            "qualified": self.qualified,
            "qualify_reason": self.qualify_reason,
            "final_score": round(self.final_score, 4),
        }


# Type aliases for the two pluggable callbacks — keeps the module free of
# direct CPO imports, and lets tests stub them with deterministic fns.
Optimizer = Callable[[Dict[str, Any]], Dict[str, Any]]
Evaluator = Callable[[Dict[str, Any]], CritiqueReport]
Tester = Callable[[Dict[str, Any]], List[PerturbationReport]]
Iterator = Callable[[Dict[str, Any], CritiqueReport], Optional[Dict[str, Any]]]
Qualifier = Callable[[Dict[str, Any], CritiqueReport], bool]


class POETIQLoop:
    """Expanded loop over the kernel + LLM critique cycle."""

    def __init__(
        self,
        *,
        optimizer: Optimizer,
        evaluator: Evaluator,
        tester: Optional[Tester] = None,
        iterator: Optional[Iterator] = None,
        qualifier: Optional[Qualifier] = None,
        max_iterations: int = 3,
        good_enough_score: float = 0.85,
    ) -> None:
        self.optimizer = optimizer
        self.evaluator = evaluator
        self.tester = tester
        self.iterator = iterator
        self.qualifier = qualifier
        self.max_iterations = max_iterations
        self.good_enough_score = good_enough_score

    def run_expanded(self, proposed_delta: Dict[str, Any]) -> POETIQExpandedResult:
        """Execute the full Propose→Optimize→Evaluate→Test→Iterate→Qualify loop."""
        critiques: List[CritiqueReport] = []
        perturbations: List[PerturbationReport] = []
        current_delta = deepcopy(proposed_delta)
        schedule = self.optimizer(current_delta)

        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            critique = self.evaluator(schedule)
            critiques.append(critique)

            if critique.score >= self.good_enough_score:
                logger.info(
                    "POETIQ: score %.3f ≥ threshold %.3f — stopping loop",
                    critique.score, self.good_enough_score,
                )
                break

            if self.iterator is None:
                break
            refined = self.iterator(current_delta, critique)
            if refined is None:
                break
            current_delta = refined
            schedule = self.optimizer(current_delta)

        # TEST — optional perturbations, not gated by score.
        if self.tester is not None:
            try:
                perturbations = list(self.tester(schedule))
            except Exception as exc:
                logger.warning("POETIQ tester failed: %s", exc)

        # QUALIFY — let the caller decide whether this proposal deserves
        # admission into the MAP-Elites archive (+ copilot memory).
        final_critique = critiques[-1]
        qualified = False
        qualify_reason = "no_qualifier_wired"
        if self.qualifier is not None:
            try:
                qualified = bool(self.qualifier(schedule, final_critique))
                qualify_reason = "auto_qualified" if qualified else "rejected_by_qualifier"
            except Exception as exc:
                qualify_reason = f"qualifier_error:{exc}"
                qualified = False

        return POETIQExpandedResult(
            proposed_delta=current_delta,
            final_schedule=schedule,
            iterations=iterations,
            critiques=critiques,
            perturbations=perturbations,
            qualified=qualified,
            qualify_reason=qualify_reason,
            final_score=final_critique.score,
        )


# ---------------------------------------------------------------------------
# Reference implementations for tests + simple callers
# ---------------------------------------------------------------------------

def default_perturbation_tester(
    schedule: Dict[str, Any],
    *,
    perturbations: Optional[List[str]] = None,
) -> List[PerturbationReport]:
    """Cheap robustness probes that don't require re-running the solver.

    * drop_worker — assume the busiest worker goes on sick leave.
    * block_machine — assume the highest-loaded machine breaks for 4h.
    * mold_unavailable — assume a random mould is locked for maintenance.
    """
    perturbations = perturbations or ["drop_worker", "block_machine", "mold_unavailable"]
    ops = schedule.get("operations") or []
    reports: List[PerturbationReport] = []
    baseline_makespan = float(schedule.get("makespan_hours", 0) or 0)
    for scenario in perturbations:
        affected = _count_affected(ops, scenario)
        # Estimate degradation: each affected op adds 1 hour of slack.
        kernel_delta = -1.0 * affected  # lower fitness = better, so positive delta → worse
        reports.append(PerturbationReport(
            scenario=scenario,
            kernel_score_delta=kernel_delta,
            ops_affected=affected,
            robust=affected == 0 or (baseline_makespan > 0 and affected / max(1, len(ops)) < 0.10),
        ))
    return reports


def _count_affected(ops: List[Dict[str, Any]], scenario: str) -> int:
    if not ops:
        return 0
    if scenario == "drop_worker":
        busiest_worker: Optional[str] = None
        tally: Dict[str, int] = {}
        for op in ops:
            for w in op.get("workers") or []:
                tally[w] = tally.get(w, 0) + 1
        if tally:
            busiest_worker = max(tally, key=tally.get)
        return sum(1 for op in ops if busiest_worker in (op.get("workers") or []))
    if scenario == "block_machine":
        if not ops:
            return 0
        tally: Dict[str, int] = {}
        for op in ops:
            mid = op.get("machine_id")
            if mid:
                tally[mid] = tally.get(mid, 0) + 1
        if not tally:
            return 0
        busiest = max(tally, key=tally.get)
        return tally[busiest]
    if scenario == "mold_unavailable":
        rng = random.Random(len(ops))
        with_mold = [op for op in ops if op.get("mold_id")]
        if not with_mold:
            return 0
        unlucky = rng.choice(with_mold).get("mold_id")
        return sum(1 for op in ops if op.get("mold_id") == unlucky)
    return 0
