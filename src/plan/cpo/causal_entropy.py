"""
ProdPlan ONE — Causal entropy penalty (Sprint I.5)
=====================================================

Blueprint v2.0 §31 adds a **flexibility preservation** term to fitness:

    fit += w_causal_entropy * (1 - normalised_entropy)

Intuition: a schedule that funnels 90 % of the laminagem ops through a
single mould + a single worker is *locally* optimal but *globally*
fragile — a sick worker, a mould that cracks, a quality rework, and
the whole plan collapses. A plan that spreads the same throughput
across several moulds / several workers absorbs the hit.

Shannon entropy is the natural measure. We compute it over three
independent axes (machines, workers, moulds) and take the **mean**
so the penalty stays on the same scale regardless of which axis is
most concentrated. Empty ops → zero penalty (no schedule to judge).

The penalty enters the legacy fitness function at weight 0.05 by
default (§31). Set ``w_causal_entropy=0`` to disable entirely — tests
that predated this change keep their exact fitness numbers.

Why at fitness level and not decoder level
------------------------------------------
The decoder already respects hard constraints (worker skill, mould
compatibility). Entropy is a *soft* preference the GA should weigh
against makespan and tardiness — not a rule the decoder should
enforce. Landing here keeps the blast radius small and the
interpretation auditable.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping


def _counts_by_key(ops: Iterable[Mapping[str, Any]], key: str) -> Dict[str, int]:
    """Tally operations per value of ``key`` (e.g. ``machine_id``).

    Operations with a missing / empty value are ignored — they are
    "unassigned" rows which don't represent real concentration.
    Multi-value fields (e.g. ``workers``: list) are flattened: each
    worker gets one count per op, so a pair-op on a single worker is
    twice as concentrated as a pair-op across two workers.
    """
    counts: Dict[str, int] = {}
    for op in ops:
        value = op.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if item is None or item == "":
                    continue
                counts[str(item)] = counts.get(str(item), 0) + 1
        else:
            counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def shannon_entropy(counts: Mapping[str, int]) -> float:
    """Classical Shannon entropy H(X) in nats.

    Returns 0.0 for an empty or single-bucket distribution (no
    uncertainty). Works on raw counts — we normalise internally.
    """
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for n in counts.values():
        if n <= 0:
            continue
        p = n / total
        entropy -= p * math.log(p)
    return entropy


def normalised_entropy(counts: Mapping[str, int]) -> float:
    """Entropy divided by log(n_buckets). Lands in [0, 1] so we can
    average across axes with different bucket counts.

    A flat distribution (every bucket equal) → 1.0.
    A degenerate distribution (one bucket) → 0.0.
    """
    n_buckets = sum(1 for v in counts.values() if v > 0)
    if n_buckets <= 1:
        return 0.0
    max_entropy = math.log(n_buckets)
    if max_entropy <= 0:
        return 0.0
    return shannon_entropy(counts) / max_entropy


# Axes we weight equally when we average. Keys must match the op dict
# shape produced by `_scheduled_to_dict` in the decoder.
_AXES: tuple[str, ...] = ("machine_id", "workers", "mold_id")


def causal_entropy_score(schedule: Mapping[str, Any]) -> float:
    """Mean normalised entropy over the three flexibility axes.

    Returns the "spread" score in [0, 1]. A caller turning this into
    a fitness penalty typically uses ``1 - score`` so that MORE
    concentration = HIGHER penalty.

    A return of ``0.0`` is ambiguous on its own: it means either the
    schedule is empty OR every axis is maximally concentrated. Use
    :func:`causal_entropy_penalty` which disambiguates via the op
    count.
    """
    ops: List[Mapping[str, Any]] = list(schedule.get("operations") or [])
    if not ops:
        return 0.0
    samples: List[float] = []
    for axis in _AXES:
        counts = _counts_by_key(ops, axis)
        if not counts:
            continue
        samples.append(normalised_entropy(counts))
    if not samples:
        return 0.0
    return sum(samples) / len(samples)


def causal_entropy_penalty(schedule: Mapping[str, Any]) -> float:
    """``1 - causal_entropy_score`` for schedules that actually have
    resource assignments.

    Two edge cases return 0 (no penalty) instead of "maximally
    concentrated":

    * An empty schedule — nothing to spread.
    * A schedule whose ops have none of the tracked axes populated
      (machine_id / workers / mold_id). Abstract / stub ops in unit
      tests — we can't assess concentration, so we stay silent.

    Both cases would otherwise yield ``score=0 → penalty=1`` which is
    semantically wrong; "no signal" is not the same as "one bucket
    holds everything".
    """
    ops = schedule.get("operations") or []
    if not ops:
        return 0.0
    has_any_axis = any(
        _counts_by_key(ops, axis) for axis in _AXES
    )
    if not has_any_axis:
        return 0.0
    score = causal_entropy_score(schedule)
    return max(0.0, min(1.0, 1.0 - score))


__all__ = [
    "causal_entropy_penalty",
    "causal_entropy_score",
    "normalised_entropy",
    "shannon_entropy",
]
