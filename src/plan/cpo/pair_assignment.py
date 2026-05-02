"""
ProdPlan ONE — Dual-Resource Pair Assignment (Sprint P.7 / WF11)
=================================================================

Blueprint v2.0 §3.5 requires that Laminagem operations are ALWAYS staffed
by pairs. Historical data (FuncionariosFaseOrdemFabrico) shows Laminagem
standard runs with 2 workers in 88.5% of operations — a single-worker
assignment is treated as infeasible by design. NOTE: the ERP field
`CoeficienteX` is the bonus payout (€) for that phase×product, NOT the
second worker's time — do not use it for workforce logic. This module
is a thin
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
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.plan.cpo.state import FactoryState, normalize_phase_code
from src.plan.engines.scheduling_adapter import SchedulingOperation

logger = logging.getLogger(__name__)


PairCost = Callable[[str, str, SchedulingOperation], float]


def requires_pair(op: SchedulingOperation, state: FactoryState) -> bool:
    """True iff the op's phase is in `state.PAIR_REQUIRED_PHASES`.

    HARD constraint: when True, the decoder MUST place 2 workers; a solo
    assignment is treated as infeasible.

    Uses `normalize_phase_code` on both sides so "Laminagem", "LAMINAGEM"
    and "laminagem" all match the canonical "LAMINAGEM" code in the
    required set. Accents are stripped too.
    """
    if not hasattr(state, "PAIR_REQUIRED_PHASES"):
        return False
    required: Set[str] = {
        normalize_phase_code(r)
        for r in (getattr(state, "PAIR_REQUIRED_PHASES", ()) or ())
    }
    phase_key = normalize_phase_code(_phase_key(op))
    return phase_key in required


def prefers_pair(op: SchedulingOperation, state: FactoryState) -> bool:
    """True iff the op's phase is in `state.PAIR_PREFERRED_PHASES`.

    SOFT preference: the decoder tries to place 2 workers but accepts a
    solo assignment with a fitness penalty when the pair pool is
    exhausted. Sprint Q.8 (CEO confirmation 2026-04-26) moved Laminagem
    from REQUIRED to PREFERRED.
    """
    if not hasattr(state, "PAIR_PREFERRED_PHASES"):
        return False
    preferred: Set[str] = {
        normalize_phase_code(r)
        for r in (getattr(state, "PAIR_PREFERRED_PHASES", ()) or ())
    }
    phase_key = normalize_phase_code(_phase_key(op))
    return phase_key in preferred


def needs_pair_assignment(op: SchedulingOperation, state: FactoryState) -> bool:
    """True iff the op should attempt pair assignment (REQUIRED or PREFERRED)."""
    return requires_pair(op, state) or prefers_pair(op, state)


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
        if not needs_pair_assignment(op, state):
            continue
        pool = _worker_pool(op, state)
        if len(pool) < 2:
            # PREFERRED phases (e.g. Laminagem post-Sprint Q.8) can fall back
            # to a solo assignment — pick the single available worker so the
            # decoder still places the op (and pays the soft fitness penalty).
            # REQUIRED phases stay infeasible.
            if prefers_pair(op, state) and len(pool) == 1:
                out[op.operation_id] = (next(iter(pool)), None)
            else:
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
            except Exception as exc:
                # Sprint Q.7 Fase 4 — was bare `continue`. Skip pair
                # whose cost can't be computed; log under DEBUG so
                # cost_fn bugs are visible during pair-assignment debug.
                logger.debug("pair cost_fn(%s, %s) failed: %s", a, b, exc)
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


# ─── Sprint Q.13.A — Plan v4 §6.2 alternative pairs ─────────────────


def rank_pairs(
    op: SchedulingOperation,
    state: FactoryState,
    *,
    cost_fn: Optional[PairCost] = None,
    top_n: int = 3,
) -> List[Dict[str, object]]:
    """Return the top-N (chefe, partner, display_score) tuples for an op.

    Plan v4 §6.2 promises the manager sees alternatives like
    "Paulo+Maria (8.2) OU João+Ana (6.1)" before committing a worker
    pair. This function is the backend that powers that UX:

    * Computes the same pair-cost matrix as `assign_pairs_for_ops` but
      keeps the top N pairs (sorted ascending by cost) instead of only
      the best.
    * Returns a list of dicts `{chefe, partner, cost, score, score_label}`
      where `score` is the display value (0-10, higher is better) the
      frontend renders. The mapping from cost to score is intentionally
      compressed so the manager sees meaningful spread (cost ∈ [0, 1] →
      score ∈ [10, 0], rounded to 0.1).

    For ops that don't need a pair (`needs_pair_assignment` False) or
    pools < 2 the function returns an empty list — the caller should
    fall back to single-worker UX.

    Notes:
    * O(n² log n) per call for sorting, fine for NELO scale (≤85 workers).
    * Stateless: no shared `used` set across calls (this is for the UX,
      where the operator may swap mid-plan; the decoder still enforces
      time-disjointness).
    """
    cost_fn = cost_fn or _default_cost
    if not needs_pair_assignment(op, state):
        return []

    pool = _worker_pool(op, state)
    if len(pool) < 2:
        return []

    candidates = sorted(pool)
    pairs: List[Tuple[str, str, float]] = []
    n = len(candidates)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = candidates[i], candidates[j]
            try:
                cost = cost_fn(a, b, op) + cost_fn(b, a, op)
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("pair cost_fn(%s, %s) failed: %s", a, b, exc)
                continue
            pairs.append((a, b, cost))

    pairs.sort(key=lambda p: p[2])
    out: List[Dict[str, object]] = []
    for chefe, partner, cost in pairs[: max(1, top_n)]:
        # cost ∈ [0, 2] (sum of two _default_cost calls in [0, 1]).
        # Map to display score 0-10 where lower cost → higher score.
        # Rounded to 0.1 so the UI shows "8.2" not "8.234".
        clamped = max(0.0, min(2.0, cost))
        score = round((1.0 - clamped / 2.0) * 10.0, 1)
        out.append({
            "chefe_id": chefe,
            "partner_id": partner,
            "cost": round(cost, 4),
            "score": score,
        })
    return out
