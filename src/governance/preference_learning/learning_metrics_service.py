"""
ProdPlan ONE — Learning Metrics Service (Sprint R.1)
======================================================

Read-only aggregator that powers the Aprendizagem panel in
``/admin/settings`` and any future learning dashboards. The service
inspects what every learning layer has produced — it never writes.

Three reports:

* ``pair_stats`` — counts the DPO/preference pairs sitting in
  ``ScheduleCommit.rejected_alternatives``. The "eligible_for_dpo"
  bucket only counts pairs where the operator wrote a reason ≥
  ``min_reason_len`` chars; that's the gate Camada 3 cares about.
* ``rule_stats`` — counts ``PreferenceRule`` rows by status and type.
  ``last_detector_run_at`` is derived from the most recent
  ``created_at`` (the nightly job inserts new rows every run, so the
  freshest row is a good proxy for the last successful pass).
  ``rules_re_emitted_count`` is a coarse signal today (rules with
  status=detected of a type that already has rejected rules); R.2
  promotes it to a true predicate-similarity count.
* ``weight_stats`` — last result of the weekly retrain (Camada 2),
  read from ``TenantConfig(governance, adaptive_fitness_weights)``.

The service is intentionally synchronous-shaped (no Kafka, no events)
because the panel re-fetches every 5 minutes and tenants typically
have a few thousand commits — Postgres handles this in <100ms.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
)
from src.governance.preference_learning.adaptive_weights import (
    DEFAULT_MIN_PAIRS,
    DEFAULT_WEIGHTS,
    BLEND_LEARNED_PCT,
    TENANT_CONFIG_CATEGORY,
    TENANT_CONFIG_KEY,
)
from src.plan.cpo.commits import ScheduleCommit

logger = logging.getLogger(__name__)


# Default reason length gate used by the panel. Mirrors the value R.2
# enforces at write-time so the dashboard and the validators agree.
DEFAULT_MIN_REASON_LEN = 10


@dataclass
class PairStats:
    """Volume of preference signal currently sitting in commits."""

    total_commits_with_rejection: int
    total_pairs: int
    eligible_for_dpo: int
    by_category: Dict[str, int]
    by_weekday: Dict[int, int]
    last_30d: Dict[str, int]
    last_90d: Dict[str, int]
    abl_pairs_today: int = 0  # populated when R.3 wires the ABL feedback job
    min_reason_len: int = DEFAULT_MIN_REASON_LEN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_commits_with_rejection": self.total_commits_with_rejection,
            "total_pairs": self.total_pairs,
            "eligible_for_dpo": self.eligible_for_dpo,
            "by_category": self.by_category,
            "by_weekday": {str(k): v for k, v in self.by_weekday.items()},
            "last_30d": self.last_30d,
            "last_90d": self.last_90d,
            "abl_pairs_today": self.abl_pairs_today,
            "min_reason_len": self.min_reason_len,
        }


@dataclass
class RuleStats:
    """Volume of explicit rules learned by Camada 1."""

    total: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    last_detector_run_at: Optional[str]
    rules_re_emitted_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "by_status": self.by_status,
            "by_type": self.by_type,
            "last_detector_run_at": self.last_detector_run_at,
            "rules_re_emitted_count": self.rules_re_emitted_count,
        }


@dataclass
class WeightStats:
    """Last result of the weekly Camada 2 retrain, with defaults for context."""

    status: str
    current_weights: Dict[str, float]
    default_weights: Dict[str, float]
    multipliers: Dict[str, float]
    pairs_used: int
    commits_scanned: int
    trained_at: Optional[str]
    blend_learned_pct: float
    min_pairs_threshold: int
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "current_weights": self.current_weights,
            "default_weights": self.default_weights,
            "multipliers": self.multipliers,
            "pairs_used": self.pairs_used,
            "commits_scanned": self.commits_scanned,
            "trained_at": self.trained_at,
            "blend_learned_pct": self.blend_learned_pct,
            "min_pairs_threshold": self.min_pairs_threshold,
            "reason": self.reason,
        }


class LearningMetricsService:
    """Aggregator that the ``/v1/governance/learning/*`` endpoints lean on."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─── pair_stats ────────────────────────────────────────────────────

    async def pair_stats(
        self,
        *,
        window_days: int = 90,
        min_reason_len: int = DEFAULT_MIN_REASON_LEN,
    ) -> PairStats:
        """Count pairs across all commits + last 30/90 days.

        Walks every commit in the window once; counts in Python
        because ``rejected_alternatives`` is JSONB and the per-tenant
        commit volume is small enough (~1-3k/tenant in the worst case)
        that a server-side aggregate doesn't pay for itself.
        """
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=max(1, window_days))

        commits = await self._fetch_commits_with_rejections(since)

        total_commits = 0
        total_pairs = 0
        eligible = 0
        by_category: Dict[str, int] = defaultdict(int)
        by_weekday: Dict[int, int] = defaultdict(int)

        last_30d_pairs = 0
        last_30d_commits = 0
        last_30d_eligible = 0
        last_90d_pairs = 0
        last_90d_commits = 0
        last_90d_eligible = 0

        cutoff_30 = now - timedelta(days=30)
        cutoff_90 = now - timedelta(days=90)

        for commit in commits:
            rejected = commit.rejected_alternatives or []
            if not rejected:
                continue
            total_commits += 1
            total_pairs += len(rejected)

            signal = commit.user_preference_signal or {}
            reason = signal.get("reason") if isinstance(signal, Mapping) else None
            commit_eligible = (
                isinstance(reason, str) and len(reason.strip()) >= min_reason_len
            )
            pairs_for_commit = len(rejected) if commit_eligible else 0
            eligible += pairs_for_commit

            # by_category prefers the commit-level category (set when the
            # operator decided), falls back to the per-alternative one.
            category = (
                signal.get("rejection_category")
                if isinstance(signal, Mapping) else None
            )
            if isinstance(category, str) and category:
                by_category[category] += len(rejected)
            else:
                for alt in rejected:
                    if isinstance(alt, Mapping):
                        cat = alt.get("rejection_category")
                        if isinstance(cat, str) and cat:
                            by_category[cat] += 1

            weekday = signal.get("weekday") if isinstance(signal, Mapping) else None
            if isinstance(weekday, int) and 0 <= weekday <= 6:
                by_weekday[weekday] += len(rejected)

            created_at = commit.created_at
            if created_at is not None:
                # Some test doubles use naive datetimes; normalise so the
                # comparison against tz-aware cutoffs doesn't blow up.
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if created_at >= cutoff_30:
                    last_30d_commits += 1
                    last_30d_pairs += len(rejected)
                    if commit_eligible:
                        last_30d_eligible += len(rejected)
                if created_at >= cutoff_90:
                    last_90d_commits += 1
                    last_90d_pairs += len(rejected)
                    if commit_eligible:
                        last_90d_eligible += len(rejected)

        abl_today = await self._count_abl_triplets_today(now)

        return PairStats(
            total_commits_with_rejection=total_commits,
            total_pairs=total_pairs,
            eligible_for_dpo=eligible,
            by_category=dict(by_category),
            by_weekday=dict(by_weekday),
            last_30d={
                "commits": last_30d_commits,
                "pairs": last_30d_pairs,
                "eligible": last_30d_eligible,
            },
            last_90d={
                "commits": last_90d_commits,
                "pairs": last_90d_pairs,
                "eligible": last_90d_eligible,
            },
            abl_pairs_today=abl_today,
            min_reason_len=min_reason_len,
        )

    async def _fetch_commits_with_rejections(
        self, since: datetime,
    ) -> List[ScheduleCommit]:
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
        rows = (await self.session.execute(stmt)).scalars().all()
        return [c for c in rows if (c.rejected_alternatives or [])]

    async def _count_abl_triplets_today(self, now: datetime) -> int:
        """Count ABL triplets written today by the R.3 feedback job.

        The store is JSONL files at ``data/learning/abl_triplets/{date}.jsonl``.
        Until R.3 lands the file simply doesn't exist and we report 0.
        Any I/O failure is treated as 0 (panel must never crash).
        """
        try:
            from pathlib import Path

            today = now.astimezone(timezone.utc).date().isoformat()
            path = Path("data/learning/abl_triplets") / f"{today}.jsonl"
            if not path.exists():
                return 0
            with path.open("r", encoding="utf-8") as fh:
                return sum(1 for line in fh if line.strip())
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("abl_today_count failed: %s", exc)
            return 0

    # ─── rule_stats ────────────────────────────────────────────────────

    async def rule_stats(self) -> RuleStats:
        """Count ``PreferenceRule`` rows by status × type, plus a re-emit hint."""
        stmt = select(PreferenceRule).where(
            PreferenceRule.tenant_id == self.tenant_id,
        )
        rules = list((await self.session.execute(stmt)).scalars().all())

        by_status: Dict[str, int] = defaultdict(int)
        by_type: Dict[str, int] = defaultdict(int)
        latest_detected_at: Optional[datetime] = None

        # Pre-compute the set of rule types the operator has previously
        # rejected — any new "detected" of the same type is a candidate
        # for the re-emit warning. Cheap heuristic; R.2 promotes it to
        # a real predicate-similarity match.
        rejected_types: set[str] = set()
        for rule in rules:
            if rule.status == PreferenceRuleStatus.REJECTED.value:
                rejected_types.add(rule.type)

        re_emitted = 0
        for rule in rules:
            by_status[rule.status] += 1
            by_type[rule.type] += 1
            if rule.status == PreferenceRuleStatus.DETECTED.value:
                if rule.type in rejected_types:
                    re_emitted += 1
                created = rule.created_at
                if created is not None:
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if latest_detected_at is None or created > latest_detected_at:
                        latest_detected_at = created

        return RuleStats(
            total=len(rules),
            by_status=dict(by_status),
            by_type=dict(by_type),
            last_detector_run_at=(
                latest_detected_at.isoformat() if latest_detected_at else None
            ),
            rules_re_emitted_count=re_emitted,
        )

    # ─── weight_stats ──────────────────────────────────────────────────

    async def weight_stats(self) -> WeightStats:
        """Return the last retrain payload (or defaults)."""
        from src.core.services.tenant_config_service import TenantConfigService

        try:
            svc = TenantConfigService(self.session, self.tenant_id)
            payload = await svc.get(
                TENANT_CONFIG_CATEGORY,
                TENANT_CONFIG_KEY,
                default=None,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "weight_stats: TenantConfigService read failed for tenant %s (%s)",
                self.tenant_id, exc,
            )
            payload = None

        if not isinstance(payload, dict):
            return WeightStats(
                status="never_trained",
                current_weights=dict(DEFAULT_WEIGHTS),
                default_weights=dict(DEFAULT_WEIGHTS),
                multipliers={k: 1.0 for k in DEFAULT_WEIGHTS},
                pairs_used=0,
                commits_scanned=0,
                trained_at=None,
                blend_learned_pct=BLEND_LEARNED_PCT,
                min_pairs_threshold=DEFAULT_MIN_PAIRS,
                reason="no_retrain_payload",
            )

        weights = payload.get("weights")
        if not isinstance(weights, dict):
            weights = {}
        current = dict(DEFAULT_WEIGHTS)
        for k, v in weights.items():
            if k in current and isinstance(v, (int, float)):
                current[k] = float(v)

        multipliers: Dict[str, float] = {}
        for k, default in DEFAULT_WEIGHTS.items():
            if default == 0:
                multipliers[k] = 1.0
            else:
                multipliers[k] = round(current[k] / default, 4)

        return WeightStats(
            status=str(payload.get("status") or "unknown"),
            current_weights=current,
            default_weights=dict(DEFAULT_WEIGHTS),
            multipliers=multipliers,
            pairs_used=int(payload.get("pairs_used") or 0),
            commits_scanned=int(payload.get("commits_scanned") or 0),
            trained_at=payload.get("trained_at"),
            blend_learned_pct=float(
                payload.get("blend_learned_pct") or BLEND_LEARNED_PCT
            ),
            min_pairs_threshold=int(
                payload.get("min_pairs") or DEFAULT_MIN_PAIRS
            ),
            reason=payload.get("reason"),
        )


    # ─── weight_history (Sprint R.4) ───────────────────────────────────

    async def weight_history(self, *, limit: int = 12) -> List[Dict[str, Any]]:
        """Return the last ``limit`` retrain payloads (newest first).

        Each entry exposes the fields the audit modal cares about:
        ``trained_at``, blended weights, multipliers vs default, the
        per-KPI explanations rendered by R.4, and any contradiction
        warnings R.2 captured. Older versions stay in TenantConfig
        history forever; the panel only asks for a window.
        """
        from src.core.services.tenant_config_service import TenantConfigService

        try:
            svc = TenantConfigService(self.session, self.tenant_id)
            rows = await svc.history(TENANT_CONFIG_CATEGORY, TENANT_CONFIG_KEY)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "weight_history: TenantConfigService read failed for tenant %s (%s)",
                self.tenant_id, exc,
            )
            return []

        out: List[Dict[str, Any]] = []
        for row in rows[: max(1, limit)]:
            payload = getattr(row, "value", None)
            if not isinstance(payload, dict):
                continue
            weights = payload.get("weights") if isinstance(payload.get("weights"), dict) else {}
            multipliers: Dict[str, float] = {}
            for k, default in DEFAULT_WEIGHTS.items():
                actual = weights.get(k)
                if isinstance(actual, (int, float)) and default:
                    multipliers[k] = round(actual / default, 4)
                else:
                    multipliers[k] = 1.0
            valid_from = getattr(row, "valid_from", None)
            out.append({
                "trained_at": payload.get("trained_at"),
                "valid_from": valid_from.isoformat() if valid_from else None,
                "status": payload.get("status"),
                "weights": weights,
                "multipliers": multipliers,
                "pairs_used": payload.get("pairs_used", 0),
                "explanations": payload.get("explanations") or [],
                "warnings": payload.get("warnings") or [],
            })
        return out


__all__ = [
    "LearningMetricsService",
    "PairStats",
    "RuleStats",
    "WeightStats",
    "DEFAULT_MIN_REASON_LEN",
]
