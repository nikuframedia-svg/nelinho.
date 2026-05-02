"""Sprint R.1 — LearningMetricsService aggregations.

Covers the three aggregations the Aprendizagem panel calls:

* ``pair_stats`` — counts commits with rejections, total pairs and the
  ``eligible_for_dpo`` slice (commits with reason ≥ min_reason_len),
  plus 30/90 day windows and category/weekday breakdowns.
* ``rule_stats`` — counts ``PreferenceRule`` rows by status × type and
  surfaces the re-emit hint when a detected rule's type already has a
  rejected sibling.
* ``weight_stats`` — reads the last retrain payload from
  ``TenantConfigService`` and falls back cleanly when no row exists.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
)
from src.governance.preference_learning.learning_metrics_service import (
    DEFAULT_MIN_REASON_LEN,
    LearningMetricsService,
)
from src.plan.cpo.commits import ScheduleCommit


TENANT = UUID("33333333-3333-3333-3333-333333333333")


# ─── Test doubles ─────────────────────────────────────────────────────────


class _FakeSession:
    """Returns the queued rows on every ``execute()``.

    The service issues two distinct selects (commits + rules); we keep
    a queue of result lists so each call sees its own batch.
    """

    def __init__(self, *batches: List[Any]) -> None:
        self._batches: List[List[Any]] = [list(b) for b in batches]

    async def execute(self, _stmt):  # noqa: ANN001 — test stub
        rows = self._batches.pop(0) if self._batches else []

        class _R:
            def __init__(self, items: List[Any]) -> None:
                self._items = items

            def scalars(self):
                class _S:
                    def __init__(self, inner: List[Any]) -> None:
                        self._inner = inner

                    def all(self) -> List[Any]:
                        return list(self._inner)

                return _S(self._items)

        return _R(rows)


class _FakeTenantConfigService:
    """Stand-in that returns a payload from a class-level stash."""

    payload: Any = None

    def __init__(self, session: Any, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def get(self, category: str, key: str, default: Any = None) -> Any:
        return _FakeTenantConfigService.payload if _FakeTenantConfigService.payload is not None else default


def _commit(
    *,
    rejected: List[Dict[str, Any]] | None = None,
    signal: Dict[str, Any] | None = None,
    sha_suffix: str = "a",
    age_days: int = 1,
) -> ScheduleCommit:
    sha = (sha_suffix * 64)[:64]
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256=sha,
        author="test",
        message="",
        kpis={"makespan_hours": 180.0},
        operations=[],
        delta={},
        alternatives=[],
        cpo_meta={},
        rejected_alternatives=rejected or [],
        user_preference_signal=signal or {},
        evidence_refs=[],
        scenarios_tested=0,
        trust_index=0.9,
        operations_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )


def _rule(
    *,
    status: PreferenceRuleStatus,
    rule_type: PreferenceRuleType = PreferenceRuleType.TRADEOFF_PREFERENCE,
    age_days: int = 1,
) -> PreferenceRule:
    rule = PreferenceRule(
        id=uuid4(),
        tenant_id=TENANT,
        type=rule_type.value,
        description="test rule",
        predicate={"x": 1},
        confidence=0.85,
        status=status.value,
        detected_from_commits=[],
    )
    rule.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    rule.updated_at = rule.created_at
    return rule


# ─── pair_stats ───────────────────────────────────────────────────────────


def test_pair_stats_counts_eligible_only_when_reason_long_enough():
    eligible_signal = {
        "decided_by": "alice",
        "weekday": 3,
        "rejection_category": "QUALITY",
        "reason": "trade throughput for quality on Friday",
    }
    short_signal = {"decided_by": "bob", "weekday": 4, "reason": "no"}
    commits = [
        _commit(
            rejected=[
                {"alt_idx": 0, "kpis": {"makespan_hours": 200.0}},
                {"alt_idx": 1, "kpis": {"makespan_hours": 210.0}},
            ],
            signal=eligible_signal,
            sha_suffix="a",
            age_days=2,
        ),
        _commit(
            rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 195.0}}],
            signal=short_signal,
            sha_suffix="b",
            age_days=10,
        ),
    ]
    session = _FakeSession(commits)
    svc = LearningMetricsService(session, TENANT)

    stats = asyncio.run(svc.pair_stats(window_days=90, min_reason_len=10))

    assert stats.total_commits_with_rejection == 2
    assert stats.total_pairs == 3
    # Only the first commit has a long-enough reason — its 2 pairs count.
    assert stats.eligible_for_dpo == 2
    assert stats.by_category == {"QUALITY": 2}
    assert stats.by_weekday[3] == 2
    assert stats.by_weekday[4] == 1
    assert stats.last_30d["pairs"] == 3
    assert stats.last_30d["eligible"] == 2
    assert stats.min_reason_len == 10


def test_pair_stats_ignores_commits_without_rejections():
    commits = [
        _commit(rejected=[], signal={"reason": "irrelevant"}, sha_suffix="a"),
        _commit(
            rejected=[{"alt_idx": 0, "kpis": {}}],
            signal={"reason": "very long reason indeed"},
            sha_suffix="b",
        ),
    ]
    svc = LearningMetricsService(_FakeSession(commits), TENANT)
    stats = asyncio.run(svc.pair_stats())

    assert stats.total_commits_with_rejection == 1
    assert stats.total_pairs == 1
    assert stats.eligible_for_dpo == 1


def test_pair_stats_30d_vs_90d_windows():
    commits = [
        _commit(
            rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 200.0}}],
            signal={"reason": "recent reason for the choice"},
            age_days=5,
            sha_suffix="a",
        ),
        _commit(
            rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 220.0}}],
            signal={"reason": "older reason for the choice"},
            age_days=60,
            sha_suffix="b",
        ),
    ]
    svc = LearningMetricsService(_FakeSession(commits), TENANT)
    stats = asyncio.run(svc.pair_stats(window_days=120))

    # 30-day window only sees the recent commit.
    assert stats.last_30d["pairs"] == 1
    assert stats.last_30d["eligible"] == 1
    # 90-day window sees both.
    assert stats.last_90d["pairs"] == 2
    assert stats.last_90d["eligible"] == 2


# ─── rule_stats ───────────────────────────────────────────────────────────


def test_rule_stats_counts_by_status_and_type():
    rules = [
        _rule(status=PreferenceRuleStatus.DETECTED, rule_type=PreferenceRuleType.TRADEOFF_PREFERENCE),
        _rule(status=PreferenceRuleStatus.CONFIRMED, rule_type=PreferenceRuleType.TRADEOFF_PREFERENCE),
        _rule(status=PreferenceRuleStatus.CONFIRMED, rule_type=PreferenceRuleType.TEMPORAL_BLOCK),
        _rule(status=PreferenceRuleStatus.REJECTED, rule_type=PreferenceRuleType.OPERATOR_AFFINITY),
    ]
    svc = LearningMetricsService(_FakeSession(rules), TENANT)
    stats = asyncio.run(svc.rule_stats())

    assert stats.total == 4
    assert stats.by_status["detected"] == 1
    assert stats.by_status["confirmed"] == 2
    assert stats.by_status["rejected"] == 1
    assert stats.by_type["tradeoff_preference"] == 2
    assert stats.by_type["temporal_block"] == 1
    assert stats.by_type["operator_affinity"] == 1


def test_rule_stats_re_emit_count_when_detected_shares_rejected_type():
    rules = [
        _rule(status=PreferenceRuleStatus.REJECTED, rule_type=PreferenceRuleType.TRADEOFF_PREFERENCE),
        # Same type as the rejected one — should count toward the re-emit hint.
        _rule(status=PreferenceRuleStatus.DETECTED, rule_type=PreferenceRuleType.TRADEOFF_PREFERENCE),
        # Different type — should NOT count.
        _rule(status=PreferenceRuleStatus.DETECTED, rule_type=PreferenceRuleType.TEMPORAL_BLOCK),
    ]
    svc = LearningMetricsService(_FakeSession(rules), TENANT)
    stats = asyncio.run(svc.rule_stats())

    assert stats.rules_re_emitted_count == 1


def test_rule_stats_last_detector_run_at_picks_freshest_detected():
    rules = [
        _rule(status=PreferenceRuleStatus.DETECTED, age_days=10),
        _rule(status=PreferenceRuleStatus.DETECTED, age_days=2),
        _rule(status=PreferenceRuleStatus.CONFIRMED, age_days=1),  # newer but confirmed → ignored
    ]
    svc = LearningMetricsService(_FakeSession(rules), TENANT)
    stats = asyncio.run(svc.rule_stats())

    assert stats.last_detector_run_at is not None
    parsed = datetime.fromisoformat(stats.last_detector_run_at)
    age = (datetime.now(timezone.utc) - parsed).days
    # Fresh detected rule is 2 days old; tolerate some clock drift.
    assert age <= 3


def test_rule_stats_handles_empty_tenant():
    svc = LearningMetricsService(_FakeSession([]), TENANT)
    stats = asyncio.run(svc.rule_stats())

    assert stats.total == 0
    assert stats.by_status == {}
    assert stats.by_type == {}
    assert stats.last_detector_run_at is None
    assert stats.rules_re_emitted_count == 0


# ─── weight_stats ─────────────────────────────────────────────────────────


def test_weight_stats_returns_defaults_when_never_trained(monkeypatch):
    _FakeTenantConfigService.payload = None
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeTenantConfigService,
        raising=True,
    )
    svc = LearningMetricsService(_FakeSession(), TENANT)
    stats = asyncio.run(svc.weight_stats())

    assert stats.status == "never_trained"
    assert stats.current_weights == stats.default_weights
    assert all(m == 1.0 for m in stats.multipliers.values())
    assert stats.trained_at is None
    assert stats.pairs_used == 0


def test_weight_stats_reads_persisted_payload(monkeypatch):
    _FakeTenantConfigService.payload = {
        "status": "trained",
        "weights": {
            "w_makespan": 1.5,
            "w_tardiness": 12.0,
            "w_setups": 0.5,
            "w_quality_risk": 0.2,
        },
        "raw_learned": {},
        "coefficients": {},
        "pairs_used": 84,
        "commits_scanned": 30,
        "trained_at": "2026-04-19T02:00:00+00:00",
        "min_pairs": 50,
        "blend_learned_pct": 0.7,
    }
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeTenantConfigService,
        raising=True,
    )
    svc = LearningMetricsService(_FakeSession(), TENANT)
    stats = asyncio.run(svc.weight_stats())

    assert stats.status == "trained"
    assert stats.pairs_used == 84
    assert stats.commits_scanned == 30
    assert stats.trained_at == "2026-04-19T02:00:00+00:00"
    assert stats.current_weights["w_makespan"] == 1.5
    # Default w_makespan is 1.0; multiplier should be 1.5 / 1.0 = 1.5.
    assert stats.multipliers["w_makespan"] == 1.5
    # Default w_tardiness is 10.0; multiplier should be 12.0 / 10.0 = 1.2.
    assert stats.multipliers["w_tardiness"] == 1.2


def test_weight_stats_missing_keys_fall_back_to_defaults(monkeypatch):
    _FakeTenantConfigService.payload = {
        "status": "trained",
        "weights": {"w_makespan": 1.5},  # only one of four keys
        "pairs_used": 100,
    }
    monkeypatch.setattr(
        "src.core.services.tenant_config_service.TenantConfigService",
        _FakeTenantConfigService,
        raising=True,
    )
    svc = LearningMetricsService(_FakeSession(), TENANT)
    stats = asyncio.run(svc.weight_stats())

    assert stats.current_weights["w_makespan"] == 1.5
    # Missing keys fall back to defaults.
    assert stats.current_weights["w_tardiness"] == 10.0
    assert stats.current_weights["w_setups"] == 0.5
    assert stats.current_weights["w_quality_risk"] == 0.10
