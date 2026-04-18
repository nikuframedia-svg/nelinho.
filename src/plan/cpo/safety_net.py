"""
ProdPlan ONE — CPO v4 Safety Net
=================================

Inviolable rule: the CPO NEVER returns a schedule worse than the baseline
greedy. If GA produces a candidate that degrades OTD or tardiness, the
baseline wins.

This is both a correctness guarantee (regressions can't ship) and a UX
guarantee (users learn to trust the optimizer).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_worse_than_baseline(candidate: Dict[str, Any], baseline: Dict[str, Any]) -> bool:
    """
    True if the candidate schedule is strictly worse than baseline on any
    hard-guardrail metric (OTD, tardiness count).

    Metrics compared:
    - num_late_orders (lower is better)
    - total_tardiness_hours (lower is better)
    - otd_delivery, if present (higher is better)
    """
    cand_late = int(candidate.get("num_late_orders", 0))
    base_late = int(baseline.get("num_late_orders", 0))
    if cand_late > base_late:
        logger.warning(
            f"Safety net: candidate tardy_count={cand_late} > baseline={base_late}"
        )
        return True

    cand_tardy_h = float(candidate.get("total_tardiness_hours", 0))
    base_tardy_h = float(baseline.get("total_tardiness_hours", 0))
    if cand_tardy_h > base_tardy_h + 1e-6:  # ignore float noise
        logger.warning(
            f"Safety net: candidate tardiness_h={cand_tardy_h:.2f} > baseline={base_tardy_h:.2f}"
        )
        return True

    cand_otd = candidate.get("otd_delivery")
    base_otd = baseline.get("otd_delivery")
    if cand_otd is not None and base_otd is not None:
        if float(cand_otd) < float(base_otd) - 1e-6:
            logger.warning(
                f"Safety net: candidate OTD={cand_otd} < baseline={base_otd}"
            )
            return True

    return False


def apply_safety_net(
    candidate: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return the better of (candidate, baseline). When baseline wins, stamp
    the result with `safety_net_triggered=True` so observability picks it up.
    """
    if is_worse_than_baseline(candidate, baseline):
        out = dict(baseline)
        out["safety_net_triggered"] = True
        out["safety_net_reason"] = "candidate worse than baseline on OTD/tardiness"
        return out

    candidate.setdefault("safety_net_triggered", False)
    return candidate
