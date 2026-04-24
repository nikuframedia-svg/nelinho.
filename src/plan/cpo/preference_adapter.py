"""
ProdPlan ONE — CPO Preference Adapter (Sprint E.4, Camada 1 enforcement)
=========================================================================

The scheduler's hook for CONFIRMED ``PreferenceRule`` rows. Each schedule
result computed by the decoder is scored against the tenant's library of
confirmed rules and a scalar penalty is returned. ``compute_fitness``
adds it to the blended objective so candidates that violate a learned
rule fall behind candidates that respect it.

**Why a penalty, not a hard constraint?**

A soft penalty is the right shape for Camada 1 for three reasons:

1. **Safety** — a buggy or narrow rule that the operator confirmed
   without thinking wouldn't crash the planner; it would just nudge it.
2. **MAP-Elites** — the archive still explores neighbouring regions,
   so the UI can show the operator "what if you relax rule X?"
3. **Audit** — the rule is visible in the fitness breakdown, not hidden
   inside an infeasibility return.

The four Camada 1 rule types map to:

* ``temporal_block`` — +``TEMPORAL_PER_OP`` for every op whose
  ``start_time`` falls on the blocked weekday.
* ``phase_threshold`` — +``THRESHOLD_PER_SHORT_OP`` for every op in the
  flagged phase with fewer workers than the learned minimum team size.
  (Hard constraints on team size live inside the decoder; this layer
  captures the "less than the minimum" regressions.)
* ``operator_affinity`` — **negative** penalty (reward) when the
  preferred worker is assigned to the flagged phase, positive otherwise.
  The reward magnitude is smaller than the penalty so the schedule
  doesn't corrupt itself with needless re-assignments.
* ``tradeoff_preference`` — **skipped at fitness level**. These rules
  are already acted on by Sprint D.4 ``AdaptiveFitnessWeights`` which
  rebalances the weight vector up-front.

All coefficients are module-level constants so they're tunable from one
place and unit-testable without touching the engine.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional

logger = logging.getLogger(__name__)


# ─── Tunables ────────────────────────────────────────────────────────────

TEMPORAL_PER_OP: float = 50.0
"""Penalty added for each op scheduled on a blocked weekday."""

THRESHOLD_PER_SHORT_OP: float = 100.0
"""Penalty added for each op in a ``phase_threshold`` rule's phase that
runs with fewer workers than the learned minimum."""

AFFINITY_REWARD: float = -15.0
"""Bonus (negative → lowers fitness = better) when the preferred worker
is on the rule's phase."""

AFFINITY_MISS_PENALTY: float = 10.0
"""Smaller penalty when the preferred worker is absent — asymmetric so
the optimizer doesn't thrash assigning the same person everywhere."""


# Rule type constants (kept as strings so importing this module doesn't
# drag the ORM/enum — the fitness hot path cares about speed).
_TEMPORAL_BLOCK = "temporal_block"
_PHASE_THRESHOLD = "phase_threshold"
_OPERATOR_AFFINITY = "operator_affinity"
_TRADEOFF_PREFERENCE = "tradeoff_preference"


# ─── Public entry ────────────────────────────────────────────────────────


def compute_preference_penalty(
    schedule: Mapping[str, Any],
    rules: Iterable[Mapping[str, Any]],
) -> float:
    """Sum the penalties for every confirmed rule that affects this schedule.

    ``schedule`` is the dict shape produced by
    ``src.plan.cpo.decoder._scheduled_to_dict`` — in particular
    ``schedule["operations"]`` is a list of op dicts with ``phase_id``,
    ``workers`` (list of worker ids), and ``start_time`` (ISO string).

    ``rules`` is an iterable of dicts with ``type`` and ``predicate``
    keys. Both ORM rows (``PreferenceRule`` instances) and plain dicts
    work — the function reads attributes via ``_get`` so tests don't
    need to instantiate SQLAlchemy models.
    """
    ops = schedule.get("operations") or []
    if not ops:
        return 0.0

    penalty = 0.0
    for rule in rules:
        rule_type = _get(rule, "type")
        predicate = _get(rule, "predicate") or {}
        if not isinstance(predicate, Mapping):
            continue

        if rule_type == _TEMPORAL_BLOCK:
            penalty += _temporal_penalty(ops, predicate)
        elif rule_type == _PHASE_THRESHOLD:
            penalty += _threshold_penalty(ops, predicate)
        elif rule_type == _OPERATOR_AFFINITY:
            penalty += _affinity_penalty(ops, predicate)
        elif rule_type == _TRADEOFF_PREFERENCE:
            # Tradeoff weights are absorbed by AdaptiveFitnessWeights
            # (Camada 2). Skip here to avoid double counting.
            continue
        else:
            logger.debug("preference_adapter: unknown rule type %r", rule_type)

    return penalty


# ─── Per-rule evaluators ─────────────────────────────────────────────────


def _temporal_penalty(
    ops: List[Mapping[str, Any]],
    predicate: Mapping[str, Any],
) -> float:
    """+TEMPORAL_PER_OP for each op whose ``start_time`` lands on the
    blocked ISO weekday (1 = Monday, 7 = Sunday).

    Predicate shape: ``{"weekday": int, ...}``. Missing or invalid
    weekday → no penalty (defensive: never crash the fitness loop).
    """
    weekday = predicate.get("weekday")
    if not isinstance(weekday, int) or not (1 <= weekday <= 7):
        return 0.0
    hits = 0
    for op in ops:
        op_weekday = _weekday_from_op(op)
        if op_weekday == weekday:
            hits += 1
    return hits * TEMPORAL_PER_OP


def _threshold_penalty(
    ops: List[Mapping[str, Any]],
    predicate: Mapping[str, Any],
) -> float:
    """+THRESHOLD_PER_SHORT_OP per op in the flagged phase staffed below
    the learned minimum."""
    phase_id = predicate.get("phase_id")
    min_team = predicate.get("min_team_size")
    if not phase_id or not isinstance(min_team, int) or min_team <= 0:
        return 0.0
    short = 0
    for op in ops:
        if str(op.get("phase_id")) != str(phase_id):
            continue
        workers = op.get("workers") or []
        if len(workers) < min_team:
            short += 1
    return short * THRESHOLD_PER_SHORT_OP


def _affinity_penalty(
    ops: List[Mapping[str, Any]],
    predicate: Mapping[str, Any],
) -> float:
    """Reward each op in the flagged phase where the preferred worker is
    on the crew; lightly penalise ops missing them."""
    phase_id = predicate.get("phase_id")
    worker_id = predicate.get("worker_id")
    if not phase_id or not worker_id:
        return 0.0
    phase_id_s = str(phase_id)
    worker_id_s = str(worker_id)
    score = 0.0
    for op in ops:
        if str(op.get("phase_id")) != phase_id_s:
            continue
        workers = [str(w) for w in (op.get("workers") or [])]
        if worker_id_s in workers:
            score += AFFINITY_REWARD
        else:
            score += AFFINITY_MISS_PENALTY
    return score


# ─── Helpers ─────────────────────────────────────────────────────────────


def _weekday_from_op(op: Mapping[str, Any]) -> Optional[int]:
    """Return the ISO weekday (Monday=1, Sunday=7) of an op's start time
    or ``None`` if the field is absent / unparsable."""
    start = op.get("start_time") or op.get("start")
    if not start:
        return None
    if isinstance(start, datetime):
        return start.isoweekday()
    if isinstance(start, str):
        try:
            # Accept both "2026-04-24T08:00:00" and "…+00:00" forms.
            parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
            return parsed.isoweekday()
        except ValueError:
            return None
    return None


def _get(obj: Any, key: str) -> Any:
    """Read ``key`` from either a dict or an ORM row (has attributes)."""
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)
