"""
ProdPlan ONE — Mill's method of difference (Sprint Q.15.D.4)
=============================================================

System prompt v2.2 §10.4: when the operator asks *"o que mudou?"*,
compare a "good" period with a "bad" period and rank what's different
by correlation strength (Cohen's d). The operator gets a punch list
of candidate causes, ordered by how strongly each correlates with the
observed degradation.

Closes the §9.3 ``DIFF-METHOD`` framework from the prompt — instead
of the LLM narrating "well, looks like X changed", the handler:

  1. Confirms the metric actually shifted (good_value vs bad_value).
  2. Iterates 7 dimensions (mold, workers, volume, transport, material,
     shift, routing).
  3. For each dimension: compute Cohen's d on the relevant samples;
     map to a 0-1 correlation; flag ``likely_cause`` when correlation
     >= 0.7 (≈ Cohen's "large" effect).
  4. Returns the changes ordered by correlation desc + a list of
     dimensions that didn't change at all.

Reuses
------

  * ``DiagnosticsRepository`` (D.0) — every query.
  * ``cohens_d`` / ``correlation_from_d`` (D.4 / correlation.py).
  * ``@record_rule_firing`` (Q.14.A) for audit + push.
  * Same Beta-Bernoulli credible-interval pattern when reporting per-
    mold or per-worker rates so cross-handler numbers stay comparable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from src.explain.diagnostics.correlation import (
    cohens_d,
    correlation_from_d,
    is_likely_cause,
)
from src.explain.diagnostics.repository import DiagnosticsRepository
from src.shared.decorators import record_rule_firing

logger = logging.getLogger(__name__)


# Cohen's d → correlation threshold for "likely cause" (≈ Cohen's
# "large effect"). Caller can override via the endpoint param.
_DEFAULT_LIKELY_THRESHOLD = 0.7

# Per-dimension floor: changes whose correlation falls below this are
# logged as "unchanged" rather than promoted to the changes list. Keeps
# the dashboard tight.
_NOISE_FLOOR_CORRELATION = 0.20


# ───────────────────────────────────────────────────────────────────────────
# Output shapes
# ───────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Change:
    """One candidate cause surfaced by Mill's diff."""

    category: str        # "mold" | "worker" | "volume" | "transport" | ...
    change: str          # human-readable description of the delta
    correlation: float   # 0-1 mapped from |Cohen's d|
    likely_cause: bool   # correlation >= threshold
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "change": self.change,
            "correlation": round(self.correlation, 4),
            "likely_cause": self.likely_cause,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class WhatChangedReport:
    """Output of :meth:`MillDiffDetector.what_changed`."""

    metric_comparison: Dict[str, Any]
    changes_found: List[Change]
    unchanged: List[str]
    verdict: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_comparison": self.metric_comparison,
            "changes_found": [c.to_dict() for c in self.changes_found],
            "unchanged": list(self.unchanged),
            "verdict": self.verdict,
        }


# ───────────────────────────────────────────────────────────────────────────
# Detector
# ───────────────────────────────────────────────────────────────────────────


class MillDiffDetector:
    """Compare 'good' vs 'bad' period across 7 dimensions.

    The detector NEVER hard-fails: each ``_diff_*`` method is wrapped
    in try/except so a single broken query doesn't sink the whole
    investigation. Dimensions with no data (material, shift) surface
    in ``unchanged`` with the explicit "data unavailable" note.
    """

    DIMENSIONS: Tuple[Tuple[str, str], ...] = (
        ("mold", "_diff_molds"),
        ("worker", "_diff_workers"),
        ("volume", "_diff_volume"),
        ("transport", "_diff_transport"),
        ("material", "_diff_material"),
        ("shift", "_diff_shift"),
        ("routing", "_diff_routing"),
    )

    def __init__(self, session: Any, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self._repo = DiagnosticsRepository(session, tenant_id)

    @record_rule_firing(
        rule_id="diagnostics.mill_diff",
        extract_payload=lambda self, *,
        good_start, good_end, bad_start, bad_end, metric="error_rate",
        phase_id=None: {
            "good_period": [good_start.isoformat(), good_end.isoformat()],
            "bad_period": [bad_start.isoformat(), bad_end.isoformat()],
            "metric": metric,
            "phase_id": phase_id,
        },
        serialise_output=lambda result: {
            "verdict": result.verdict,
            "changes_count": len(result.changes_found),
            "likely_causes": [
                c.category for c in result.changes_found if c.likely_cause
            ],
        },
        dedupe_key=lambda self, *,
        good_start, good_end, bad_start, bad_end, metric="error_rate",
        phase_id=None: (
            f"mill_diff:{good_start.isoformat()}:{bad_end.isoformat()}:"
            f"{metric}:{phase_id or 'global'}"
        ),
    )
    async def what_changed(
        self,
        *,
        good_start: date,
        good_end: date,
        bad_start: date,
        bad_end: date,
        metric: str = "error_rate",
        phase_id: Optional[str] = None,
        likely_threshold: float = _DEFAULT_LIKELY_THRESHOLD,
    ) -> WhatChangedReport:
        """End-to-end: confirm shift → diff each dimension → rank.

        Args:
            good_start / good_end / bad_start / bad_end: window bounds.
                ``end`` is exclusive (mirrors the repository convention).
            metric: ``error_rate`` (default) or one of the future
                ``throughput`` / ``lead_time`` extensions.
            phase_id: optional — restrict to a single phase.
            likely_threshold: correlation cutoff for ``likely_cause``.
        """
        # 1. Confirm the metric actually shifted between the two periods.
        comparison = await self._compare_metric(
            metric=metric,
            phase_id=phase_id,
            good_start=good_start, good_end=good_end,
            bad_start=bad_start, bad_end=bad_end,
        )
        if comparison is None or comparison.get("delta_correlation", 0.0) < _NOISE_FLOOR_CORRELATION:
            return WhatChangedReport(
                metric_comparison=comparison or {"verdict": "no_data"},
                changes_found=[],
                unchanged=[
                    "Métrica não mudou significativamente entre os dois períodos."
                ],
                verdict="no_shift",
            )

        # 2. Diff each dimension.
        changes: List[Change] = []
        unchanged: List[str] = []

        for dim_name, method_name in self.DIMENSIONS:
            diff_method = getattr(self, method_name, None)
            if diff_method is None:
                continue
            try:
                result = await diff_method(
                    good_start, good_end, bad_start, bad_end, phase_id,
                )
            except Exception as exc:
                logger.warning(
                    "MillDiffDetector: %s failed (%s) — skipping",
                    method_name, exc,
                )
                continue
            if result is None:
                unchanged.append(f"{dim_name}: sem dados disponíveis")
                continue
            change_obj = result
            change_obj = Change(
                category=change_obj.category,
                change=change_obj.change,
                correlation=change_obj.correlation,
                likely_cause=change_obj.correlation >= likely_threshold,
                evidence=change_obj.evidence,
            )
            if change_obj.correlation < _NOISE_FLOOR_CORRELATION:
                unchanged.append(
                    f"{dim_name}: shift detectado mas abaixo do floor "
                    f"({change_obj.correlation:.0%})"
                )
            else:
                changes.append(change_obj)

        # 3. Rank by correlation desc.
        changes.sort(key=lambda c: -c.correlation)

        verdict = self._compose_verdict(changes)
        return WhatChangedReport(
            metric_comparison=comparison,
            changes_found=changes,
            unchanged=unchanged,
            verdict=verdict,
        )

    # ────────────────────────────────────────────────────────────────
    # Dimension diffs
    # ────────────────────────────────────────────────────────────────

    async def _compare_metric(
        self,
        *,
        metric: str,
        phase_id: Optional[str],
        good_start: date, good_end: date,
        bad_start: date, bad_end: date,
    ) -> Optional[Dict[str, Any]]:
        """Confirm the metric shifted. Returns mean comparison + a
        ``delta_correlation`` derived from Cohen's d on daily samples
        (when available)."""
        if metric != "error_rate":
            # throughput / lead_time TBD — defer until real data wiring.
            return {
                "metric": metric,
                "verdict": "metric_not_supported_yet",
            }

        if phase_id is None:
            # Global error rate — not yet supported (needs averaging
            # across phases). Defer.
            return {
                "metric": metric,
                "verdict": "phase_id_required_for_error_rate",
            }

        good_samples = await self._repo.daily_phase_error_rate_samples(
            phase_id, good_start, good_end,
        )
        bad_samples = await self._repo.daily_phase_error_rate_samples(
            phase_id, bad_start, bad_end,
        )
        if not good_samples or not bad_samples:
            return None

        d = cohens_d(good_samples, bad_samples)
        corr = correlation_from_d(d)
        good_mean = sum(good_samples) / len(good_samples)
        bad_mean = sum(bad_samples) / len(bad_samples)
        return {
            "metric": metric,
            "phase_id": phase_id,
            "good_mean": round(good_mean, 4),
            "bad_mean": round(bad_mean, 4),
            "delta": round(bad_mean - good_mean, 4),
            "delta_pp": (
                f"{(bad_mean - good_mean) * 100:+.1f}pp"
                if metric.endswith("_rate") else None
            ),
            "cohens_d": round(d, 4) if d is not None else None,
            "delta_correlation": round(corr, 4),
        }

    async def _diff_molds(
        self, gs: date, ge: date, bs: date, be: date, _phase_id,
    ) -> Optional[Change]:
        """Did one or more molds drift? Pick the most-shifted mold's
        Cohen's d on per-day error rates."""
        # Universe of molds active in either period.
        good_molds = set(await self._repo.molds_active_during(gs, ge))
        bad_molds = set(await self._repo.molds_active_during(bs, be))
        all_molds = good_molds | bad_molds
        if not all_molds:
            return None

        # For each mold, build daily error-rate samples in both windows.
        # Use mold_usage as a coarser proxy when daily samples are too
        # sparse.
        worst_mold: Optional[str] = None
        worst_corr = 0.0
        worst_evidence: List[str] = []

        for mold_id in all_molds:
            usage_good = await self._repo.mold_usage(mold_id, gs, ge)
            usage_bad = await self._repo.mold_usage(mold_id, bs, be)
            # Need some activity on both sides to compare.
            if usage_good.total_phases == 0 or usage_bad.total_phases == 0:
                continue
            # Cohen's d on the rate values (1 sample per period) is
            # undefined; fall back to a normalised |delta| -> correlation.
            delta = usage_bad.error_rate - usage_good.error_rate
            if abs(delta) < 0.05:
                continue
            # Map a ratio shift to a correlation: 0.0 at delta=0,
            # ~0.7 at delta=0.20, saturating at 1.0 around delta=0.30.
            corr = min(1.0, abs(delta) / 0.3)
            if corr > worst_corr:
                worst_corr = corr
                worst_mold = mold_id
                worst_evidence = [
                    f"Molde {mold_id}: erro {usage_good.error_rate:.0%} → "
                    f"{usage_bad.error_rate:.0%} ({delta:+.0%})",
                    f"Usos: {usage_good.total_phases} → {usage_bad.total_phases}",
                ]

        if worst_mold is None or worst_corr <= 0:
            return None
        return Change(
            category="mold",
            change=f"Molde {worst_mold} taxa erro mudou {worst_corr * 30:+.0f}pp",
            correlation=worst_corr,
            likely_cause=False,  # set by caller using its threshold
            evidence=worst_evidence,
        )

    async def _diff_workers(
        self, gs: date, ge: date, bs: date, be: date, phase_id,
    ) -> Optional[Change]:
        """Did the worker roster change? Reports new entries and exits."""
        if phase_id is None:
            return None
        good_workers = await self._repo.workers_in_phase_set(phase_id, gs, ge)
        bad_workers = await self._repo.workers_in_phase_set(phase_id, bs, be)
        if not good_workers and not bad_workers:
            return None
        entered = bad_workers - good_workers
        exited = good_workers - bad_workers
        if not entered and not exited:
            return None

        # Correlation proxy: relative size of the change against the
        # union. 50% turnover saturates near 1.0.
        union = max(1, len(good_workers | bad_workers))
        change_size = (len(entered) + len(exited)) / union
        corr = min(1.0, change_size * 1.5)

        evidence: List[str] = []
        if entered:
            evidence.append(
                f"Entraram em {phase_id}: {sorted(entered)[:5]}"
                + (f" (+{len(entered) - 5} mais)" if len(entered) > 5 else "")
            )
        if exited:
            evidence.append(
                f"Saíram de {phase_id}: {sorted(exited)[:5]}"
                + (f" (+{len(exited) - 5} mais)" if len(exited) > 5 else "")
            )
        change_str = (
            f"{len(entered)} entradas + {len(exited)} saídas "
            f"(roster: {len(good_workers)} → {len(bad_workers)})"
        )
        return Change(
            category="worker",
            change=change_str,
            correlation=corr,
            likely_cause=False,
            evidence=evidence,
        )

    async def _diff_volume(
        self, gs: date, ge: date, bs: date, be: date, _phase_id,
    ) -> Optional[Change]:
        """WIP shift between periods — Cohen's d on daily samples."""
        good_samples = await self._repo.daily_wip_samples(gs, ge)
        bad_samples = await self._repo.daily_wip_samples(bs, be)
        if not good_samples or not bad_samples:
            return None
        d = cohens_d(good_samples, bad_samples)
        corr = correlation_from_d(d)
        if corr <= 0:
            return None
        good_mean = sum(good_samples) / len(good_samples)
        bad_mean = sum(bad_samples) / len(bad_samples)
        return Change(
            category="volume",
            change=f"WIP {good_mean:.0f} → {bad_mean:.0f} barcos",
            correlation=corr,
            likely_cause=False,
            evidence=[
                f"WIP médio bom: {good_mean:.0f}, mau: {bad_mean:.0f}",
                f"Cohen's d = {d:.2f}" if d is not None else "d undefined",
            ],
        )

    async def _diff_transport(
        self, gs: date, ge: date, bs: date, be: date, _phase_id,
    ) -> Optional[Change]:
        """Transport volume shift between periods."""
        good_vol = await self._repo.transport_volume_during(gs, ge)
        bad_vol = await self._repo.transport_volume_during(bs, be)
        if good_vol == 0 and bad_vol == 0:
            return None
        # Treat the two single numbers as 1-sample groups isn't valid
        # for Cohen's d. Use relative change instead, mapping to corr:
        #   0% change → 0.0
        #   50% increase → ~0.5
        #   100%+ → 1.0
        denom = max(good_vol, 1)
        ratio = (bad_vol - good_vol) / denom
        corr = min(1.0, abs(ratio))
        if corr <= 0:
            return None
        return Change(
            category="transport",
            change=f"Volume expedição {good_vol} → {bad_vol} barcos ({ratio:+.0%})",
            correlation=corr,
            likely_cause=False,
            evidence=[
                f"Pressão de expedição mudou {ratio:+.0%} entre os dois períodos",
            ],
        )

    async def _diff_material(
        self, gs: date, ge: date, bs: date, be: date, _phase_id,
    ) -> Optional[Change]:
        """Graceful no-data — same pattern as Reichenbach SharedMaterialCheck."""
        if not await self._repo.has_material_lot_tracking():
            return None
        # Future: compare lot distributions between windows.
        return None

    async def _diff_shift(
        self, gs: date, ge: date, bs: date, be: date, _phase_id,
    ) -> Optional[Change]:
        """Graceful no-data — shift_id not in curated layer today."""
        if not await self._repo.has_shift_tracking():
            return None
        return None

    async def _diff_routing(
        self, gs: date, ge: date, bs: date, be: date, _phase_id,
    ) -> Optional[Change]:
        """Routing change diff — defer until ScheduleCommit.routing_variant
        history is queryable. Today returns None (routing changes aren't
        directly tracked in the curated layer)."""
        return None

    # ────────────────────────────────────────────────────────────────
    # Verdict composition
    # ────────────────────────────────────────────────────────────────

    def _compose_verdict(self, changes: List[Change]) -> str:
        """Pick a one-liner that summarises the strongest cause."""
        if not changes:
            return (
                "Métrica mudou mas nenhuma dimensão isolou-se "
                "(possível combinação de factores)."
            )
        top = changes[0]
        likely = [c for c in changes if c.likely_cause]
        if likely:
            top_likely = likely[0]
            secondary = [
                c for c in changes
                if c is not top_likely and c.correlation >= 0.4
            ]
            verdict = (
                f"Causa mais provável: {top_likely.change} "
                f"(correlação {top_likely.correlation:.0%})."
            )
            if secondary:
                verdict += (
                    f" Factor secundário: {secondary[0].change}."
                )
            return verdict
        return (
            f"Causa mais provável: {top.change} "
            f"(correlação {top.correlation:.0%}). "
            "Sinal moderado — sem confiança alta para acção isolada."
        )


__all__ = [
    "Change",
    "MillDiffDetector",
    "WhatChangedReport",
]
