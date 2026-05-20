"""
ProdPlan ONE — Preference Rule Detector (Sprint C 2.2)
========================================================

The first concrete piece of the "learning system" in the plan §IV
(the moat): scans recent `ScheduleCommit` rows that carry
`rejected_alternatives` + `user_preference_signal`, mines recurring
patterns, and inserts `PreferenceRule` rows awaiting operator review.

Not ML — **counters + thresholds**. That is on purpose:
* Deterministic, auditable, unit-testable.
* Every rule has a `confidence` derived from counts, not a black box.
* Human confirms before the scheduler applies (no silent drift).

Four sub-detectors, each must see at least `min_samples=5` matching
commits and yield `confidence ≥ 0.7` before producing a rule:

1. `_detect_temporal_patterns` — "manager rejects plans that touch
   phase X on weekday Y" (ISO weekday 1-7, hour bucket 0-23).
2. `_detect_tradeoff_preferences` — "prefers less setup over +€/day"
   based on KPI deltas in rejected_alternatives vs chosen.
3. `_detect_operator_affinities` — "phase X is always assigned to
   worker W" (for the rare cases when manager overrides the Hungarian).
4. `_detect_phase_threshold_rules` — "minimum N workers on phase X"
   derived from cases the manager rejected because he wanted more
   staff on a bottleneck.

Output rows are written with `status=detected`. The `/admin/learned-
rules` endpoint (frontend) flips them to `confirmed` / `rejected`.

Designed to run as a nightly job (see `src/shared/scheduler.py` —
Sprint C 2.3).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
)
from src.plan.cpo.commits import ScheduleCommit

logger = logging.getLogger(__name__)


DEFAULT_MIN_SAMPLES = 5
DEFAULT_MIN_CONFIDENCE = 0.7
# Tolerance for "metric deltas are equivalent" in tradeoff detection.
# 5% matches Blueprint §17 example ("when diferença < 5%").
DEFAULT_TRADEOFF_TOLERANCE_PCT = 0.05


class PreferenceRuleDetector:
    """Scan recent commits and emit PreferenceRule rows.

    Usage:
        detector = PreferenceRuleDetector(session, tenant_id)
        rules = await detector.scan(window_days=30)
        # rules are already persisted; the list is returned for logging.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        tradeoff_tolerance_pct: float = DEFAULT_TRADEOFF_TOLERANCE_PCT,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.min_samples = min_samples
        self.min_confidence = min_confidence
        self.tradeoff_tolerance_pct = tradeoff_tolerance_pct

    # ─── Public entry ──────────────────────────────────────────────────

    async def scan(self, window_days: int = 30) -> List[PreferenceRule]:
        """Fetch recent commits, run every sub-detector, persist rules.

        Sprint R.2 — anti-re-emit: candidates whose signature matches a
        previously REJECTED rule are skipped (so the operator doesn't
        keep dismissing the same noise every night). Skipped count is
        logged and surfaces via ``LearningMetricsService.rule_stats``
        as ``rules_re_emitted_count``.
        """
        commits = await self._fetch_commits_with_rejections(window_days)
        if not commits:
            logger.info(
                "PreferenceRuleDetector: no commits with rejections in "
                "the last %d days for tenant %s",
                window_days, self.tenant_id,
            )
            return []

        rejected_signatures = await self._collect_rejected_signatures()

        candidates: List[Dict[str, Any]] = []
        candidates += self._detect_temporal_patterns(commits)
        candidates += self._detect_tradeoff_preferences(commits)
        candidates += self._detect_operator_affinities(commits)
        candidates += self._detect_phase_threshold_rules(commits)

        persisted: List[PreferenceRule] = []
        re_emitted_skipped = 0
        for candidate in candidates:
            if candidate["confidence"] < self.min_confidence:
                continue
            sig = _predicate_signature(candidate["type"], candidate["predicate"])
            if sig in rejected_signatures:
                re_emitted_skipped += 1
                continue
            rule_id = uuid4()
            rule = PreferenceRule(
                id=rule_id,
                tenant_id=self.tenant_id,
                type=candidate["type"],
                description=candidate["description"],
                predicate=candidate["predicate"],
                confidence=Decimal(str(round(candidate["confidence"], 2))),
                status=PreferenceRuleStatus.DETECTED.value,
                detected_from_commits=candidate["commit_ids"],
            )
            self.session.add(rule)
            await audit_change(
                self.session,
                tenant_id=self.tenant_id,
                entity_type="preference_rule",
                entity_id=rule_id,
                action="INSERT",
                new_values={
                    "type": candidate["type"],
                    "status": PreferenceRuleStatus.DETECTED.value,
                    "confidence": float(candidate["confidence"]),
                    "sample_count": len(candidate["commit_ids"]),
                },
                actor_id=None,  # detector é job background, sem actor
                reason="detector aprendeu regra",
            )
            persisted.append(rule)

        await self.session.flush()
        logger.info(
            "PreferenceRuleDetector: %d rules persisted for tenant %s "
            "(scanned %d commits, window=%dd, re_emitted_skipped=%d)",
            len(persisted), self.tenant_id, len(commits), window_days,
            re_emitted_skipped,
        )
        return persisted

    async def _collect_rejected_signatures(self) -> set[str]:
        """Return signatures of rules the operator has already rejected.

        Tenant-scoped only — the same predicate can legitimately be
        rejected in tenant A and detected fresh in tenant B (different
        factory, different operator).
        """
        stmt = select(PreferenceRule).where(
            and_(
                PreferenceRule.tenant_id == self.tenant_id,
                PreferenceRule.status == PreferenceRuleStatus.REJECTED.value,
            )
        )
        rejected_rules = list((await self.session.execute(stmt)).scalars().all())
        return {
            _predicate_signature(rule.type, rule.predicate or {})
            for rule in rejected_rules
        }

    # ─── Data access ───────────────────────────────────────────────────

    async def _fetch_commits_with_rejections(
        self, window_days: int,
    ) -> List[ScheduleCommit]:
        since = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = (
            select(ScheduleCommit)
            .where(
                and_(
                    ScheduleCommit.tenant_id == self.tenant_id,
                    ScheduleCommit.created_at >= since,
                )
            )
            .order_by(ScheduleCommit.created_at.asc())
        )
        result = await self.session.execute(stmt)
        all_commits = list(result.scalars().all())
        # Keep only commits that actually carry a decision signal.
        return [
            c for c in all_commits
            if (c.rejected_alternatives or []) and (c.user_preference_signal or {})
        ]

    # ─── Detector 1 — temporal patterns ────────────────────────────────

    def _detect_temporal_patterns(
        self, commits: List[ScheduleCommit],
    ) -> List[Dict[str, Any]]:
        """"Rejects plans on weekday X" — counts (weekday, has_rejection)
        tuples and flags weekdays with unusually high rejection rates.
        """
        by_weekday_rejected: Counter = Counter()
        by_weekday_total: Counter = Counter()
        commits_by_weekday: Dict[int, List[str]] = defaultdict(list)

        for c in commits:
            sig = c.user_preference_signal or {}
            weekday = sig.get("weekday")
            if not isinstance(weekday, int) or not (1 <= weekday <= 7):
                continue
            by_weekday_total[weekday] += 1
            if c.rejected_alternatives:
                by_weekday_rejected[weekday] += 1
                commits_by_weekday[weekday].append(c.commit_sha256[:12])

        results: List[Dict[str, Any]] = []
        for weekday, rejected in by_weekday_rejected.items():
            if rejected < self.min_samples:
                continue
            total = by_weekday_total[weekday] or 1
            confidence = rejected / total
            if confidence < self.min_confidence:
                continue
            weekday_name = _WEEKDAY_NAMES.get(weekday, f"weekday-{weekday}")
            results.append({
                "type": PreferenceRuleType.TEMPORAL_BLOCK.value,
                "description": (
                    f"Gestor rejeita cenários frequentemente à "
                    f"{weekday_name} ({rejected}/{total} = {confidence:.0%})"
                ),
                "predicate": {
                    "weekday": weekday,
                    "rejected_count": rejected,
                    "total_count": total,
                },
                "confidence": confidence,
                "commit_ids": commits_by_weekday[weekday],
            })
        return results

    # ─── Detector 2 — tradeoff preferences ─────────────────────────────

    def _detect_tradeoff_preferences(
        self, commits: List[ScheduleCommit],
    ) -> List[Dict[str, Any]]:
        """For each pair of KPIs (A, B), count how often the chosen plan
        improved A at the cost of worsening B by less than the tolerance.
        If one direction dominates, surface it as a rule.
        """
        tradeoff_counts: Counter = Counter()
        tradeoff_commit_ids: Dict[tuple, List[str]] = defaultdict(list)

        # KPI pairs we actually care about — keeps the matrix small.
        kpi_pairs = [
            ("setups", "throughput_eur_day"),
            ("quality_risk_score", "makespan_hours"),
            ("total_idle_hours", "throughput_eur_day"),
        ]

        for c in commits:
            for rejected in c.rejected_alternatives or []:
                deltas = rejected.get("delta_vs_chosen") or {}
                if not isinstance(deltas, dict):
                    continue
                for kpi_improved, kpi_sacrificed in kpi_pairs:
                    improvement = deltas.get(kpi_improved)
                    sacrifice = deltas.get(kpi_sacrificed)
                    if not isinstance(improvement, (int, float)):
                        continue
                    if not isinstance(sacrifice, (int, float)):
                        continue
                    # "Chosen is better on A" means delta_vs_chosen[A]
                    # for the REJECTED alternative is positive (the
                    # rejected alt had MORE of the bad thing).
                    if improvement <= 0:
                        continue
                    # "Chosen is slightly worse on B" — the rejected
                    # alt had at most `tolerance × |chosen_B|` better B.
                    tolerance_abs = abs(sacrifice) * self.tradeoff_tolerance_pct
                    if abs(sacrifice) > tolerance_abs * 20:
                        continue  # way too big a sacrifice, not a tradeoff
                    tradeoff_counts[(kpi_improved, kpi_sacrificed)] += 1
                    tradeoff_commit_ids[(kpi_improved, kpi_sacrificed)].append(
                        c.commit_sha256[:12],
                    )

        results: List[Dict[str, Any]] = []
        total_decisions = sum(tradeoff_counts.values()) or 1
        for (improved, sacrificed), count in tradeoff_counts.items():
            if count < self.min_samples:
                continue
            confidence = count / total_decisions
            if confidence < self.min_confidence:
                continue
            results.append({
                "type": PreferenceRuleType.TRADEOFF_PREFERENCE.value,
                "description": (
                    f"Gestor prefere melhorar {improved} mesmo piorando "
                    f"{sacrificed} em pouco (<{self.tradeoff_tolerance_pct:.0%})"
                ),
                "predicate": {
                    "prefer": improved,
                    "sacrifice": sacrificed,
                    "tolerance_pct": self.tradeoff_tolerance_pct,
                    "sample_count": count,
                },
                "confidence": confidence,
                "commit_ids": tradeoff_commit_ids[(improved, sacrificed)],
            })
        return results

    # ─── Detector 3 — operator affinities ──────────────────────────────

    def _detect_operator_affinities(
        self, commits: List[ScheduleCommit],
    ) -> List[Dict[str, Any]]:
        """Look at the CHOSEN alternative's operations and count
        (phase, worker) pairs that appear in ≥ min_samples commits.
        This catches "manager manually re-assigned Paulo to K4 again".
        """
        phase_worker_counts: Counter = Counter()
        pair_commits: Dict[tuple, List[str]] = defaultdict(list)
        commits_total = 0

        for c in commits:
            commits_total += 1
            seen_pairs_this_commit = set()
            for op in c.operations or []:
                phase = op.get("phase_id")
                workers = op.get("workers") or []
                if not phase or not workers:
                    continue
                for worker in workers:
                    key = (str(phase), str(worker))
                    if key in seen_pairs_this_commit:
                        continue  # count each commit once per pair
                    seen_pairs_this_commit.add(key)
                    phase_worker_counts[key] += 1
                    pair_commits[key].append(c.commit_sha256[:12])

        if commits_total == 0:
            return []

        results: List[Dict[str, Any]] = []
        for (phase, worker), count in phase_worker_counts.items():
            if count < self.min_samples:
                continue
            confidence = count / commits_total
            if confidence < self.min_confidence:
                continue
            results.append({
                "type": PreferenceRuleType.OPERATOR_AFFINITY.value,
                "description": (
                    f"Worker {worker} atribuído à fase {phase} em "
                    f"{count}/{commits_total} commits ({confidence:.0%})"
                ),
                "predicate": {
                    "phase_id": phase,
                    "worker_id": worker,
                    "sample_count": count,
                    "of_total": commits_total,
                },
                "confidence": confidence,
                "commit_ids": pair_commits[(phase, worker)],
            })
        return results

    # ─── Detector 4 — phase threshold rules ────────────────────────────

    def _detect_phase_threshold_rules(
        self, commits: List[ScheduleCommit],
    ) -> List[Dict[str, Any]]:
        """For each phase, look at the team_size (len(workers)) used in
        the CHOSEN alternative across commits, find the minimum, and
        propose a floor when that minimum repeats ≥ min_samples times.
        """
        phase_min_sizes: Dict[str, List[int]] = defaultdict(list)
        phase_commits: Dict[str, List[str]] = defaultdict(list)

        for c in commits:
            seen_phases = set()
            for op in c.operations or []:
                phase = op.get("phase_id")
                if not phase:
                    continue
                size = len(op.get("workers") or [])
                if size <= 0 or phase in seen_phases:
                    continue
                seen_phases.add(phase)
                phase_min_sizes[str(phase)].append(size)
                phase_commits[str(phase)].append(c.commit_sha256[:12])

        results: List[Dict[str, Any]] = []
        for phase, sizes in phase_min_sizes.items():
            if len(sizes) < self.min_samples:
                continue
            observed_min = min(sizes)
            count_at_min = sum(1 for s in sizes if s == observed_min)
            confidence = count_at_min / len(sizes)
            if confidence < self.min_confidence:
                continue
            results.append({
                "type": PreferenceRuleType.PHASE_THRESHOLD.value,
                "description": (
                    f"Fase {phase} sempre com ≥{observed_min} workers "
                    f"({count_at_min}/{len(sizes)} commits = "
                    f"{confidence:.0%})"
                ),
                "predicate": {
                    "phase_id": phase,
                    "min_team_size": observed_min,
                    "sample_count": len(sizes),
                },
                "confidence": confidence,
                "commit_ids": phase_commits[phase][:10],
            })
        return results


_WEEKDAY_NAMES: Dict[int, str] = {
    1: "Segunda-feira",
    2: "Terça-feira",
    3: "Quarta-feira",
    4: "Quinta-feira",
    5: "Sexta-feira",
    6: "Sábado",
    7: "Domingo",
}


# ─── Sprint R.2 — anti-re-emit signature helper ──────────────────────────


# Per-type discriminating keys: only these participate in the signature
# so two candidates that differ only in counts (sample_count, of_total)
# still match a previously rejected rule.
_SIGNATURE_KEYS_BY_TYPE: Dict[str, tuple[str, ...]] = {
    PreferenceRuleType.TEMPORAL_BLOCK.value: ("weekday",),
    PreferenceRuleType.TRADEOFF_PREFERENCE.value: ("prefer", "sacrifice"),
    PreferenceRuleType.OPERATOR_AFFINITY.value: ("phase_id", "worker_id"),
    PreferenceRuleType.PHASE_THRESHOLD.value: ("phase_id", "min_workers"),
    PreferenceRuleType.WORKFORCE_OVERRIDE.value: ("employee_id", "field"),
}


def _predicate_signature(rule_type: str, predicate: Dict[str, Any]) -> str:
    """Canonical string signature for ``(type, predicate)``.

    Used to detect candidates the operator has already rejected. Two
    rules with the same signature describe the same behaviour even if
    auxiliary fields (counts, totals) drifted between scans.
    """
    import json

    keys = _SIGNATURE_KEYS_BY_TYPE.get(rule_type)
    if keys is None:
        # Unknown type: fall back to the raw predicate so we never
        # accidentally collapse two different rule types together.
        payload = {"_type": rule_type, **(predicate or {})}
    else:
        payload = {"_type": rule_type}
        for key in keys:
            payload[key] = (predicate or {}).get(key)
    return json.dumps(payload, sort_keys=True, default=str)
