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

Sprint Q.54.G — closes the last two holes in Spelke axiom 7. The
decoder also emits `lam_utilization` (% scheduled minutes in Laminagem
— the bottleneck phase) and `idle_ratio` (horizon-normalised idle).
Both fed MAP-Elites as diversity axes but were invisible to the
safety net, so a candidate could drain the bottleneck or balloon the
idle ratio while tardiness/OTD stayed flat. They are now guardrails:
nine dimensions total.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

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
#   * setups: 15% rise tolerated
#   * total_idle_hours: 20% rise tolerated
#   * lam_utilization: 5pp drop tolerated  (Sprint Q.54.G)
#   * idle_ratio: 5pp rise tolerated       (Sprint Q.54.G)
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

# Sprint Q.54.G — closing the last two holes in Spelke axiom 7.
# `lam_utilization` and `idle_ratio` were emitted by the decoder
# (decoder.py — Sprint A ME1/F2) and consumed by MAP-Elites as
# diversity axes, but the safety net never compared them. A candidate
# could quietly drain Laminagem utilisation (the factory's bottleneck
# phase — 88.5% dual-resource) or balloon the idle ratio while keeping
# tardiness/OTD flat, and ship. Now both are checked.
#
# `lam_utilization` is a percentage (0-100); the decoder reports the
# share of scheduled minutes spent in LAMINAGEM* phases. It is an
# *absolute* metric, so the guardrail is an absolute drop in percentage
# POINTS, not a relative %: a candidate whose lam_utilization is 5pp
# below baseline is degrading the bottleneck and loses.
#
# `idle_ratio` is a fraction (0-1); we already gate `total_idle_hours`
# relatively, but that scales with team size and horizon. `idle_ratio`
# is the normalised version — guarded with an absolute 5pp rise so a
# candidate can't trade idle hours for a longer horizon and slip past.
_LAM_UTILIZATION_TOLERANCE_PP = 5.0   # 5 percentage-point drop ok
_IDLE_RATIO_TOLERANCE = 0.05          # 5 percentage-point (0.05) rise ok


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

    # otd_delivery: on-time-delivery rate, higher is better. Hard
    # guardrail — any drop vs baseline blocks. The decoder DOES emit
    # this key (decoder.py — "FASE 1B.6 (CRIT-24): populate otd_delivery
    # so safety_net can [check it]"); a previous note here wrongly
    # claimed otherwise and dropped the check.
    cand_otd = candidate.get("otd_delivery")
    base_otd = baseline.get("otd_delivery")
    if cand_otd is not None and base_otd is not None:
        if float(cand_otd) < float(base_otd) - 1e-6:  # float noise
            violations.append((
                "otd_delivery",
                f"otd={float(cand_otd):.4f} < baseline={float(base_otd):.4f}",
            ))

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

    # ── Sprint Q.54.G — Laminagem utilisation + idle_ratio guardrails ──

    # Laminagem utilisation (lam_utilization, % of scheduled minutes in
    # LAMINAGEM* phases): HIGHER is better — Laminagem is the factory's
    # bottleneck (88.5% dual-resource, the binding constraint on the
    # €30-35K/day target). A candidate that drains it more than 5
    # percentage points below baseline is hiding a throughput loss the
    # other KPIs may not catch. Absolute pp comparison, not relative %:
    # a 5pp drop from 60→55 is the same severity as 20→15.
    cand_lam = candidate.get("lam_utilization")
    base_lam = baseline.get("lam_utilization")
    if cand_lam is not None and base_lam is not None:
        cand_v = float(cand_lam)
        base_v = float(base_lam)
        if cand_v < base_v - _LAM_UTILIZATION_TOLERANCE_PP - 1e-6:
            violations.append((
                "lam_utilization",
                f"lam_util={cand_v:.2f}% < baseline={base_v:.2f}% "
                f"- {_LAM_UTILIZATION_TOLERANCE_PP:.0f}pp",
            ))

    # Idle ratio (idle_ratio, fraction in [0,1]): HIGHER is worse. This
    # is the horizon-normalised twin of total_idle_hours — a candidate
    # could keep idle_hours flat while stretching the horizon, and slip
    # the relative total_idle_hours check. idle_ratio closes that gap.
    # Absolute pp comparison (0.05 = 5pp).
    cand_ir = candidate.get("idle_ratio")
    base_ir = baseline.get("idle_ratio")
    if cand_ir is not None and base_ir is not None:
        cand_v = float(cand_ir)
        base_v = float(base_ir)
        if cand_v > base_v + _IDLE_RATIO_TOLERANCE + 1e-6:
            violations.append((
                "idle_ratio",
                f"idle_ratio={cand_v:.4f} > baseline={base_v:.4f} "
                f"+ {_IDLE_RATIO_TOLERANCE:.2f}",
            ))

    return violations


# Q.171.D — check_revenue_alignment_warning (guardrail Q.115.X7 de
# desvio >50% da faturação diária) foi REMOVIDO: nunca foi chamado em
# lado nenhum (dead code confirmado pela auditoria 2026-06-10) e os
# dados de revenue-target não fluem para os schedules. Religar = trazer
# o daily_revenue_target ao result-dict e chamar em apply_safety_net
# (histórico no git: Q.115.X7).

def is_worse_than_baseline(candidate: Dict[str, Any], baseline: Dict[str, Any]) -> bool:
    """True if the candidate fails any of the nine safety-net
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
