"""
ProdPlan ONE — CPO v4 Workforce Assignment (Sprint I.1)
========================================================

Hungarian (linear_sum_assignment) optimal worker ↔ operation matching.
Replaces the first-fit assignment in `decoder._pick_workers` when the
caller opts in via `CPOConfig.use_hungarian_workforce`.

Input: a list of operations, each with its eligible worker pool and
earliest-start time, plus a global worker-free-at map. Output: a dict
`operation_id → List[worker_id]` satisfying team_size per op.

NELO domain rules respected:
- `team_size=2` (enforced by caller for Laminagem/Laminagem Infusão) —
  Hungarian solves two instances, picks 1 worker each, guarantees
  distinct workers per op.
- Rework routing (phase "Pintura Acabamento" etc.) pulls the historical
  `chefe` to the top of the ranked pool — passed via `worker_affinity`.
- Complex boats (peso >= P75) restrict the pool to senior workers —
  passed via `eligible_subset` (computed by the caller from tenure).

Cost model (lower is better — scipy.linear_sum_assignment minimizes):
    cost[op, worker] = free_at_delta + skill_penalty + affinity_bonus
                     + error_rate_penalty

- free_at_delta   — seconds until the worker becomes free (idleness cost)
- skill_penalty   — 0 if worker is in the op's skill pool, INF otherwise
- affinity_bonus  — negative (reward) when worker == preferred chefe
- error_rate      — positive penalty proportional to historical error rate

Hungarian is O(n^3); we cap `n` at ~500 workers/ops per call and fall
back to first-fit when the matrix is larger than the budget.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

try:
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)

#: Hard cap: above this matrix size we fall back to first-fit.
MATRIX_SIZE_CAP = 1500
# "Infinity" for unavailable pairings. Large but finite so scipy accepts.
INFEASIBLE_COST = 1e12


@dataclass
class WorkforceRequest:
    """One operation's worker-assignment request."""

    operation_id: str
    eligible_workers: Sequence[str]
    team_size: int = 1
    preferred_worker: Optional[str] = None  # e.g. historical chefe
    error_rate_by_worker: Optional[Dict[str, float]] = None  # 0-1 per worker
    earliest_start: Optional[datetime] = None


def assign_workers_hungarian(
    requests: Sequence[WorkforceRequest],
    worker_free_at: Dict[str, datetime],
    *,
    horizon_start: Optional[datetime] = None,
) -> Dict[str, List[str]]:
    """
    Run Hungarian matching and return {operation_id: [worker_id, ...]}.

    Falls back to first-fit when scipy isn't available or the matrix is
    too big. Operations with `team_size=k` contribute `k` "virtual slots"
    to the assignment matrix so the same worker can't cover both slots.
    """
    if not SCIPY_AVAILABLE or not requests:
        return _first_fit_fallback(requests, worker_free_at, horizon_start)

    # Build a flat list of slots (one per team_size unit per op)
    slots: List[tuple] = []  # (op_index, slot_index_within_op, request)
    for op_idx, req in enumerate(requests):
        for slot in range(max(1, int(req.team_size))):
            slots.append((op_idx, slot, req))

    # Collect all candidate workers (union of eligible pools) for the matrix
    workers: List[str] = sorted(
        set().union(*[set(r.eligible_workers) for r in requests])
    )

    if not workers or not slots:
        return {r.operation_id: [] for r in requests}

    if len(slots) * len(workers) > MATRIX_SIZE_CAP * MATRIX_SIZE_CAP:
        logger.info(
            f"Workforce matrix too large ({len(slots)}x{len(workers)}) — "
            f"falling back to first-fit"
        )
        return _first_fit_fallback(requests, worker_free_at, horizon_start)

    # Cost matrix rows = slots, cols = workers
    ref = horizon_start or datetime.utcnow()
    cost = np.full((len(slots), len(workers)), INFEASIBLE_COST, dtype=np.float64)

    for row, (_op_idx, _slot_idx, req) in enumerate(slots):
        eligible_set: Set[str] = set(req.eligible_workers)
        start_ref = req.earliest_start or ref
        for col, worker_id in enumerate(workers):
            if worker_id not in eligible_set:
                continue
            # 1. free-at delta — how long until the worker can start
            free_at = worker_free_at.get(worker_id, ref)
            delta = (free_at - start_ref).total_seconds()
            free_penalty = max(0.0, delta)

            # 2. affinity bonus for preferred chefe
            affinity = -3600.0 if worker_id == req.preferred_worker else 0.0

            # 3. error rate penalty (scaled so 100% error == 1h of idle cost)
            err_rate = 0.0
            if req.error_rate_by_worker:
                err_rate = float(req.error_rate_by_worker.get(worker_id, 0.0) or 0.0)
            err_penalty = 3600.0 * err_rate  # seconds

            cost[row, col] = free_penalty + affinity + err_penalty

    # Pad columns with dummy "noone" to allow more slots than workers if needed
    n_slots, n_workers = cost.shape
    if n_slots > n_workers:
        padding = np.full((n_slots, n_slots - n_workers), INFEASIBLE_COST)
        cost = np.concatenate([cost, padding], axis=1)

    try:
        row_ind, col_ind = linear_sum_assignment(cost)
    except Exception as e:
        logger.warning(f"Hungarian failed ({e}) — falling back to first-fit")
        return _first_fit_fallback(requests, worker_free_at, horizon_start)

    result: Dict[str, List[str]] = {r.operation_id: [] for r in requests}
    for row, col in zip(row_ind, col_ind):
        if col >= len(workers):
            continue  # assigned to dummy — slot stays empty
        if cost[row, col] >= INFEASIBLE_COST:
            continue  # unreachable assignment (skill mismatch)
        op_idx, _, req = slots[row]
        result[req.operation_id].append(workers[col])

    return result


# ---------------------------------------------------------------------------
# First-fit fallback (matches decoder._pick_workers behaviour)
# ---------------------------------------------------------------------------

def _first_fit_fallback(
    requests: Sequence[WorkforceRequest],
    worker_free_at: Dict[str, datetime],
    horizon_start: Optional[datetime],
) -> Dict[str, List[str]]:
    ref = horizon_start or datetime.utcnow()
    result: Dict[str, List[str]] = {}
    for req in requests:
        pool = list(req.eligible_workers)
        if not pool:
            result[req.operation_id] = []
            continue
        pool.sort(key=lambda w: (worker_free_at.get(w, ref), w))
        result[req.operation_id] = pool[: max(1, int(req.team_size))]
    return result
