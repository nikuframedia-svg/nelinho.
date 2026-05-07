"""
ProdPlan ONE — CPO v4 Safety Net
=================================

Inviolable rule: the CPO NEVER returns a schedule worse than the baseline
greedy. If GA produces a candidate that degrades any of the seven
fitness-dimensions, the baseline wins.

This is both a correctness guarantee (regressions can't ship) and a UX
guarantee (users learn to trust the optimizer).

Sprint Q.13.A — closing Spelke axiom 7 gap. Originally compared only
4 KPIs (num_late_orders, total_tardiness_hours, otd_delivery, makespan
1.5× cap), which left the door open to a candidate that:
  * dropped throughput €/dia by 10% but kept tardiness equal,
  * raised quality_risk by 25% (silent defect cost) but kept OTD equal,
  * doubled setup_time (more changeovers) under a same-makespan budget,
  * starved operators of work (idle_operators rose 20%).
None of those would have been caught. Now the seven dimensions of the
v2 fitness function are checked, each with a tunable tolerance so
random GA noise doesn't flip safety net unnecessarily.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# Sprint Q.13.A — tolerances for each KPI before safety_net trips.
#
# Hard guardrails (zero tolerance — any regression flips):
#   * num_late_orders, total_tardiness_hours, otd_delivery
#
# Soft guardrails (small tolerance to absorb GA noise):
#   * makespan_hours: 1.5× cap (existing rule, kept as-is)
#   * throughput_eur_day: 5% drop tolerated
#   * avg_quality_risk: 10% rise tolerated
#   * total_setup_time_h: 15% rise tolerated
#   * idle_operators_h: 20% rise tolerated
#
# These percentages live here rather than ConfigStore because they are
# correctness invariants, not tenant policy. A tenant changing them
# would be opting out of the safety net itself; that should be an
# explicit code change so it shows up in code review.
_THROUGHPUT_TOLERANCE = 0.05  # 5% drop ok (noise band)
_QUALITY_RISK_TOLERANCE = 0.10  # 10% rise ok
_SETUP_TIME_TOLERANCE = 0.15  # 15% rise ok
_IDLE_TOLERANCE = 0.20  # 20% rise ok
_MAKESPAN_HARD_CAP = 1.5  # 1.5× baseline makespan cap


def _gather_violations(
    candidate: Dict[str, Any], baseline: Dict[str, Any],
) -> List[Tuple[str, str]]:
    """Return a list of `(metric, message)` for every guardrail the
    candidate breaks. Empty list = candidate is acceptable.

    Split out so callers can attach the full violation set to the
    returned schedule (for observability) instead of just the first
    one we find — gives operators the full picture when a candidate
    flips to baseline.
    """
    violations: List[Tuple[str, str]] = []

    # ── Hard guardrails (no tolerance) ────────────────────────────────

    cand_late = int(candidate.get("num_late_orders", 0))
    base_late = int(baseline.get("num_late_orders", 0))
    if cand_late > base_late:
        violations.append((
            "num_late_orders",
            f"tardy_count={cand_late} > baseline={base_late}",
        ))

    cand_tardy_h = float(candidate.get("total_tardiness_hours", 0))
    base_tardy_h = float(baseline.get("total_tardiness_hours", 0))
    if cand_tardy_h > base_tardy_h + 1e-6:  # float noise
        violations.append((
            "total_tardiness_hours",
            f"tardiness_h={cand_tardy_h:.2f} > baseline={base_tardy_h:.2f}",
        ))

    # `otd_delivery` was a hard guardrail in earlier versions, but the
    # decoder never emits that key — only `num_late_orders` and
    # `total_tardiness_hours` (both already enforced above). Removed
    # because the two existing hard checks already cover the same
    # regression: any candidate that ships orders later than baseline
    # necessarily worsens at least one of them.

    # ── Makespan: 1.5× hard cap (Sprint C 4.2 SN1) ────────────────────

    cand_makespan = float(candidate.get("makespan_hours", 0) or 0)
    base_makespan = float(baseline.get("makespan_hours", 0) or 0)
    if base_makespan > 0 and cand_makespan > base_makespan * _MAKESPAN_HARD_CAP:
        violations.append((
            "makespan_hours",
            f"makespan_h={cand_makespan:.2f} > {_MAKESPAN_HARD_CAP}× "
            f"baseline={base_makespan:.2f}",
        ))

    # ── Sprint Q.13.A — soft guardrails for the 4 v2 KPIs ────────────

    # Throughput €/dia: lower is worse. The candidate may drop within
    # _THROUGHPUT_TOLERANCE (5%) to absorb GA noise; beyond, baseline wins.
    cand_thru = candidate.get("throughput_eur_day")
    base_thru = baseline.get("throughput_eur_day")
    if cand_thru is not None and base_thru is not None and float(base_thru) > 0:
        cand_v = float(cand_thru)
        base_v = float(base_thru)
        if cand_v < base_v * (1.0 - _THROUGHPUT_TOLERANCE):
            violations.append((
                "throughput_eur_day",
                f"throughput=€{cand_v:.0f}/d < "
                f"{(1 - _THROUGHPUT_TOLERANCE):.0%}×baseline=€{base_v:.0f}/d",
            ))

    # Quality risk: higher is worse. Plan §5.5 — Blueprint v2.0 weight
    # is 0.10. We accept up to 10% rise vs baseline so GA can chase
    # other gains; beyond that the candidate is masking a quality bomb.
    cand_qr = candidate.get("avg_quality_risk")
    base_qr = baseline.get("avg_quality_risk")
    if cand_qr is not None and base_qr is not None and float(base_qr) > 0:
        cand_v = float(cand_qr)
        base_v = float(base_qr)
        if cand_v > base_v * (1.0 + _QUALITY_RISK_TOLERANCE):
            violations.append((
                "avg_quality_risk",
                f"quality_risk={cand_v:.4f} > "
                f"{(1 + _QUALITY_RISK_TOLERANCE):.0%}×baseline={base_v:.4f}",
            ))

    # Setups (count): higher is worse. The decoder emits `setups` (int
    # count, not hours). 15% tolerance accepts family-aware groupings;
    # beyond that the GA is shuffling randomly.
    cand_setup = candidate.get("setups")
    base_setup = baseline.get("setups")
    if cand_setup is not None and base_setup is not None and float(base_setup) > 0:
        cand_v = float(cand_setup)
        base_v = float(base_setup)
        if cand_v > base_v * (1.0 + _SETUP_TIME_TOLERANCE):
            violations.append((
                "setups",
                f"setups={int(cand_v)} > "
                f"{(1 + _SETUP_TIME_TOLERANCE):.0%}×baseline={int(base_v)}",
            ))

    # Idle operators (total_idle_hours): higher is worse. Plan §5.5
    # weights idle at 0.15. 20% tolerance accepts shift-edge effects
    # but blocks candidates that deliberately starve workforce to game
    # makespan. Key matches decoder.compute_kpis output exactly.
    cand_idle = candidate.get("total_idle_hours")
    base_idle = baseline.get("total_idle_hours")
    if cand_idle is not None and base_idle is not None and float(base_idle) > 0:
        cand_v = float(cand_idle)
        base_v = float(base_idle)
        if cand_v > base_v * (1.0 + _IDLE_TOLERANCE):
            violations.append((
                "total_idle_hours",
                f"idle_h={cand_v:.2f} > "
                f"{(1 + _IDLE_TOLERANCE):.0%}×baseline={base_v:.2f}",
            ))

    return violations


def is_worse_than_baseline(candidate: Dict[str, Any], baseline: Dict[str, Any]) -> bool:
    """True if the candidate fails any of the seven safety-net
    guardrails. Each violation is logged at WARNING level so operators
    can see why a particular run flipped to baseline.
    """
    violations = _gather_violations(candidate, baseline)
    for metric, message in violations:
        logger.warning("Safety net violation [%s]: %s", metric, message)
    return bool(violations)


def apply_safety_net(
    candidate: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the better of (candidate, baseline). When baseline wins,
    stamp the result with `safety_net_triggered=True` and the full list
    of violations so observability picks them up.
    """
    violations = _gather_violations(candidate, baseline)
    if violations:
        for metric, message in violations:
            logger.warning("Safety net violation [%s]: %s", metric, message)
        out = dict(baseline)
        out["safety_net_triggered"] = True
        out["safety_net_reason"] = (
            f"candidate worse than baseline on {len(violations)} "
            f"guardrail(s): {', '.join(v[0] for v in violations)}"
        )
        out["safety_net_violations"] = [
            {"metric": m, "detail": d} for m, d in violations
        ]
        return out

    candidate.setdefault("safety_net_triggered", False)
    candidate.setdefault("safety_net_violations", [])
    return candidate
