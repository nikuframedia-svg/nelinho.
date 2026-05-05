"""
ProdPlan ONE — Shared diagnostic types (Sprint Q.15.D.0)
=========================================================

Dataclasses used across the ERRO-TREE / Reichenbach / Mill's handlers.

Design choices:

  * **Beta-Bernoulli confidence** — `Hypothesis` carries (alpha, beta)
    pseudo-counts rather than a raw `confidence` float. `confidence`
    becomes a derived property; `credible_interval(level)` computes
    Beta CI on demand using `scipy.stats.beta` (with the same
    Beasley-Springer-Moro fallback as `governance.ab_framework`).
    Math is now comparable across detectors (one detector saying
    "α=8, β=2 → 0.80" is the same statistical claim as another saying
    the same).

  * **Frozen-by-default** — these flow through async pipelines and
    eventually into JSONB columns. Frozen prevents accidental mutation
    after a handler emits the hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional, Tuple


class TriggerType(str, Enum):
    """Why an investigation was launched.

    The string values are **stable** — they appear in the audit log
    (governance.rule_firing.trigger_payload.trigger), in the function-
    calling tool spec enum, and in the CausalChain question template.
    Adding values is fine; renaming would break audit history.
    """
    QUALITY_DROP = "quality_drop"
    THROUGHPUT_DROP = "throughput_drop"
    DELAY_SPIKE = "delay_spike"


@dataclass(frozen=True)
class Hypothesis:
    """One detector's answer.

    Beta-Bernoulli pseudo-counts: ``alpha = evidence_for + 1``,
    ``beta = evidence_against + 1``. The +1 is a uniform prior (same
    convention as `improve.record_adoption_signal` and
    `governance.ab_framework.compute_adoption_stats`).
    """

    type: str               # "mold_degradation" | "worker_skill" | "overload" | ...
    entity: str             # the specific thing blamed (mold name, worker name, ...)
    alpha: float            # >= 1.0 (evidence_for + 1)
    beta: float             # >= 1.0 (evidence_against + 1)
    evidence: List[str]     # human-readable lines for the audit + UI

    @property
    def confidence(self) -> float:
        """Posterior mean of the Beta distribution. In [0, 1]."""
        n = self.alpha + self.beta
        if n <= 0:
            return 0.5  # truly empty prior — uniform
        return self.alpha / n

    def credible_interval(self, level: float = 0.95) -> Tuple[float, float]:
        """``(low, high)`` of the Beta posterior at ``level`` (default 95%).

        Uses scipy when available; falls back to the Beasley-Springer-
        Moro normal approximation reused from
        :mod:`src.governance.ab_framework`. Both branches handle the
        clamp to [0, 1] so callers never see slightly-negative or
        >1 bounds from numerical jitter.
        """
        from src.governance.ab_framework import _beta_credible_interval
        return _beta_credible_interval(self.alpha, self.beta, level)


@dataclass(frozen=True)
class MoldUsage:
    """Per-mold rollup over a period."""

    mold_id: str
    total_phases: int       # count of CuratedOrderPhase rows referencing this mold
    error_count: int        # quality events on those phases
    phase_ids: List[str] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(1, self.total_phases)


@dataclass(frozen=True)
class WorkerStats:
    """Per-worker rollup in a single phase over a period."""

    worker_id: str
    phase_id: str
    total_allocations: int
    error_count: int
    allocation_dates: List[date] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.error_count / max(1, self.total_allocations)

    @property
    def first_seen(self) -> Optional[date]:
        return min(self.allocation_dates) if self.allocation_dates else None

    @property
    def last_seen(self) -> Optional[date]:
        return max(self.allocation_dates) if self.allocation_dates else None


@dataclass(frozen=True)
class BoatJourney:
    """One order's pass through ≥ 1 phase in a period.

    Used by the Reichenbach `_check_shared_mold` to find boats that
    passed through ALL of a set of deviating phases AND share a mold.
    """

    of_id: str
    phase_ids: List[str]
    mold_id: Optional[str]


@dataclass(frozen=True)
class DiagnosticResult:
    """The outcome of a single :meth:`investigate` call.

    Persisted as a row in `governance.rule_firing` (via
    `@record_rule_firing` on the handler method) and as the JSON body
    of the `/v1/explain/diagnostics/investigate` response.
    """

    root_cause: Optional[Hypothesis]
    chain: List[str]
    steps_checked: List[dict]
    recommendation: dict


__all__ = [
    "BoatJourney",
    "DiagnosticResult",
    "Hypothesis",
    "MoldUsage",
    "TriggerType",
    "WorkerStats",
]
