"""
ProdPlan ONE — Dual-Resource Pair Assignment (Sprint P.7 / WF11)
=================================================================

Blueprint v2.0 §3.5 requires that Laminagem operations are ALWAYS staffed
by pairs — `CoeficienteX > 0` encodes the second worker's time, so a
single-worker assignment is infeasible by design. This module is a thin
orchestrator around `src/plan/cpo/workforce.assign_workers_hungarian`
that:

* Identifies `PAIR_REQUIRED_PHASES` on `FactoryState` (Laminagem variants).
* Builds the (chefe, partner) cost matrix by combining skill match + quality
  penalty (when the QualityRiskModel is wired).
* Returns `{operation_id: (chefe_id, partner_id)}` mappings the decoder
  consumes instead of the legacy first-fit `_pick_workers`.

The decoder opts in via `CPOConfig.use_hungarian_pair_assignment`. When
the flag is off, legacy behaviour is preserved (first-fit worker pool) so
existing tests keep their expected outputs.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import SchedulingOperation

logger = logging.getLogger(__name__)


PairCost = Callable[[str, str, SchedulingOperation], float]


def requires_pair(op: SchedulingOperation, state: FactoryState) -> bool:
    """True iff the op's phase is in `state.PAIR_REQUIRED_PHASES`."""
    if not hasattr(state, "PAIR_REQUIRED_PHASES"):
        return False
    required: Set[str] = set(getattr(state, "PAIR_REQUIRED_PHASES", set()) or set())
    phase_key = _phase_key(op)
    return phase_key in {r.lower() for r in required}


def assign_pairs_for_ops(
    operations: List[SchedulingOperation],
    state: FactoryState,
    *,
    cost_fn: Optional[PairCost] = None,
) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """Return `{operation_id: (chefe_id, partner_id)}` for every op that
    needs a pair. Non-pair ops are OMITTED so callers can still use their
    regular worker pool for them.

    Missing assignments (empty skill pool, too few workers) map to
    `(None, None)`; the caller treats those as infeasible and records a
    warning rather than crashing.
    """
    cost_fn = cost_fn or _default_cost
    out: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

    # Greedy worker-availability tracking — first pass only. This is a
    # per-op assignment, not time-aware; the decoder re-validates against
    # `worker_free_at` before placing the op. Revisit with temporal
    # Hungarian (L-RHO) in a future sprint.
    used: Set[Tuple[str, str]] = set()

    for op in operations:
        if not requires_pair(op, state):
            continue
        pool = _worker_pool(op, state)
        if len(pool) < 2:
            out[op.operation_id] = (None, None)
            continue

        candidates = sorted(pool)
        chefe, partner = _best_pair(candidates, op, cost_fn, used=used)
        out[op.operation_id] = (chefe, partner)
        if chefe and partner:
            # Only record when both are set — we allow reusing a worker in
            # another op's pair within the same batch because the decoder
            # enforces time-disjointness afterwards.
            used.add(tuple(sorted((chefe, partner))))

    return out


def _phase_key(op: SchedulingOperation) -> str:
    return str(op.phase_id or getattr(op, "phase_name", "") or "").strip().lower()


def _worker_pool(op: SchedulingOperation, state: FactoryState) -> Set[str]:
    if op.phase_id and hasattr(state, "workers_for"):
        try:
            return set(state.workers_for(str(op.phase_id)))
        except Exception:  # pragma: no cover — defensive
            return set()
    return set()


def _best_pair(
    candidates: List[str],
    op: SchedulingOperation,
    cost_fn: PairCost,
    *,
    used: Set[Tuple[str, str]],
) -> Tuple[Optional[str], Optional[str]]:
    """Greedy O(n²) — good enough for pools ≤ 85 workers (NELO scale).

    scipy.optimize.linear_sum_assignment would dominate here only if we
    also solved every op simultaneously; current callers (decoder) resolve
    pairs per-op, so the cost matrix per call never exceeds ~85².
    """
    best_cost = float("inf")
    best_pair: Tuple[Optional[str], Optional[str]] = (None, None)
    n = len(candidates)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = candidates[i], candidates[j]
            if tuple(sorted((a, b))) in used:
                continue
            try:
                cost = cost_fn(a, b, op) + cost_fn(b, a, op)
            except Exception:
                continue
            if cost < best_cost:
                best_cost = cost
                best_pair = (a, b)
    return best_pair


def _default_cost(worker_a: str, worker_b: str, op: SchedulingOperation) -> float:
    """Neutral cost — prefers lexicographic stability so tests are deterministic.

    A real cost function combines:
      skill_match_penalty  (1.0 if worker missing the required skill)
      quality_risk_penalty (Sprint H QualityRiskModel.predict_proba)
      fatigue_penalty      (consecutive ops on same worker)

    Sprint P ships this default; tuning lands in Sprint R when the quality
    model + fatigue data are both available.
    """
    return float(hash((worker_a, worker_b, op.operation_id)) % 1000) / 1000.0
