"""Sprint C 2.2 — PreferenceRuleDetector nightly scan.

Covers:
* No commits with rejections → zero rules (quiet)
* Temporal pattern: 6 Friday rejections + 0 rejections other days → 1
  rule with type=temporal_block
* Tradeoff pattern: 5 commits where chosen improved `setups` by >0 and
  worsened `throughput_eur_day` by <5% → 1 rule tradeoff_preference
* Operator affinity: 7 commits where Paulo worked LAMINAGEM → 1 rule
* Phase threshold: 6 commits where PINTURA had exactly 3 workers → 1 rule
* Sub-threshold confidence doesn't persist a rule
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.governance.models import (
    PreferenceRule,
    PreferenceRuleStatus,
    PreferenceRuleType,
)
from src.governance.preference_learning import PreferenceRuleDetector
from src.plan.cpo.commits import ScheduleCommit
from tests.conftest import FakeSession


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _make_commit(
    *,
    weekday: int = 1,
    rejected: List[Dict[str, Any]] | None = None,
    operations: List[Dict[str, Any]] | None = None,
    sha_suffix: str = "a",
) -> ScheduleCommit:
    # Pad the suffix to 64 chars so commit_sha256 is valid.
    sha = (sha_suffix * 64)[:64]
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256=sha,
        author="test",
        message="",
        kpis={},
        operations=operations or [],
        delta={},
        alternatives=[],
        cpo_meta={},
        rejected_alternatives=rejected or [],
        user_preference_signal={"weekday": weekday, "decided_by": "alice"},
        evidence_refs=[],
        scenarios_tested=0,
        trust_index=0.9,
        operations_count=len(operations or []),
        created_at=datetime.now(timezone.utc),
    )


class _FakeSession(FakeSession):
    """Q.68.3.4 — subclasse local sobre o canónico.

    O detector emite 2 SELECTs distintos (ScheduleCommit + opcionalmente
    PreferenceRule para anti-re-emit). Dispatchamos por
    ``column_descriptions[0]["entity"]``.
    """

    def __init__(
        self,
        commits: List[ScheduleCommit],
        *,
        rejected_rules: List[PreferenceRule] | None = None,
    ) -> None:
        super().__init__()
        self._commits = commits
        # Sprint R.2 — detector now also queries PreferenceRule(status=REJECTED)
        # to suppress re-emits. Default empty so existing tests stay green.
        self._rejected_rules = list(rejected_rules or [])

    async def execute(self, stmt: Any):  # type: ignore[override]
        rows: List[Any] = self._commits
        try:
            entity = stmt.column_descriptions[0].get("entity")
            if entity is PreferenceRule:
                rows = self._rejected_rules
        except Exception:
            pass
        self.queue_scalars(rows)
        return await super().execute(stmt)


# ---------------------------------------------------------------------------
# Empty + quiet paths
# ---------------------------------------------------------------------------


def test_scan_with_no_commits_returns_empty():
    session = _FakeSession([])
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())
    assert rules == []
    assert session.added == []


def test_scan_skips_commits_without_rejection_signal():
    """A commit without `rejected_alternatives` is noise — the detector
    must not surface temporal rules based on it."""
    commits = [
        _make_commit(weekday=5, rejected=[], sha_suffix=chr(ord("a") + i))
        for i in range(10)
    ]
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())
    assert rules == []


# ---------------------------------------------------------------------------
# Temporal pattern detection
# ---------------------------------------------------------------------------


def test_scan_detects_temporal_pattern_when_friday_has_six_rejections():
    # 6 Friday (weekday=5) commits all with ≥1 rejection → confidence 1.0
    commits = [
        _make_commit(
            weekday=5,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            sha_suffix=chr(ord("a") + i),
        )
        for i in range(6)
    ]
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())

    temporal = [r for r in rules if r.type == PreferenceRuleType.TEMPORAL_BLOCK.value]
    assert len(temporal) == 1
    rule = temporal[0]
    assert rule.predicate["weekday"] == 5
    assert rule.predicate["rejected_count"] == 6
    assert rule.status == PreferenceRuleStatus.DETECTED.value
    assert rule.confidence == 1.0


def test_temporal_pattern_below_min_samples_is_ignored():
    # Only 4 Friday rejections — under the default min_samples=5.
    commits = [
        _make_commit(
            weekday=5,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            sha_suffix=chr(ord("a") + i),
        )
        for i in range(4)
    ]
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())
    assert all(r.type != PreferenceRuleType.TEMPORAL_BLOCK.value for r in rules)


# ---------------------------------------------------------------------------
# Tradeoff preference detection
# ---------------------------------------------------------------------------


def test_tradeoff_preference_detected_for_setups_vs_throughput():
    """5 commits where the rejected alt had more setups but ~same
    throughput → chosen trades throughput for fewer setups."""
    commits = []
    for i in range(5):
        commits.append(_make_commit(
            weekday=3,
            rejected=[{
                "alt_idx": 0,
                "kpis": {"setups": 10, "throughput_eur_day": 28000},
                "delta_vs_chosen": {
                    "setups": 3,  # rejected has MORE setups (bad)
                    "throughput_eur_day": 100,  # tiny sacrifice vs 28000
                },
            }],
            sha_suffix=chr(ord("a") + i),
        ))
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())

    tradeoffs = [r for r in rules if r.type == PreferenceRuleType.TRADEOFF_PREFERENCE.value]
    assert len(tradeoffs) >= 1
    rule = tradeoffs[0]
    assert rule.predicate["prefer"] == "setups"
    assert rule.predicate["sacrifice"] == "throughput_eur_day"
    assert rule.predicate["sample_count"] == 5


# ---------------------------------------------------------------------------
# Operator affinity detection
# ---------------------------------------------------------------------------


def test_operator_affinity_detected_when_paulo_always_on_laminagem():
    commits = []
    for i in range(7):
        commits.append(_make_commit(
            weekday=2,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            operations=[
                {
                    "operation_id": f"O{i}",
                    "phase_id": "LAMINAGEM",
                    "workers": ["paulo"],
                },
            ],
            sha_suffix=chr(ord("a") + i),
        ))
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())

    affinities = [r for r in rules if r.type == PreferenceRuleType.OPERATOR_AFFINITY.value]
    assert len(affinities) == 1
    rule = affinities[0]
    assert rule.predicate["phase_id"] == "LAMINAGEM"
    assert rule.predicate["worker_id"] == "paulo"


# ---------------------------------------------------------------------------
# Phase threshold detection
# ---------------------------------------------------------------------------


def test_phase_threshold_detected_when_team_size_is_constant():
    commits = []
    for i in range(6):
        commits.append(_make_commit(
            weekday=2,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            operations=[{
                "operation_id": f"O{i}",
                "phase_id": "PINTURA_ACABAMENTO",
                "workers": ["w1", "w2", "w3"],  # team size = 3
            }],
            sha_suffix=chr(ord("a") + i),
        ))
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())

    thresholds = [r for r in rules if r.type == PreferenceRuleType.PHASE_THRESHOLD.value]
    assert len(thresholds) == 1
    rule = thresholds[0]
    assert rule.predicate["phase_id"] == "PINTURA_ACABAMENTO"
    assert rule.predicate["min_team_size"] == 3


# ---------------------------------------------------------------------------
# Persistence side-effects
# ---------------------------------------------------------------------------


def test_detected_rules_are_added_to_session_and_flushed():
    commits = [
        _make_commit(
            weekday=5,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            sha_suffix=chr(ord("a") + i),
        )
        for i in range(6)
    ]
    session = _FakeSession(commits)
    detector = PreferenceRuleDetector(session, TENANT)
    rules = asyncio.run(detector.scan())

    assert all(r in session.added for r in rules)
    assert session.flush_calls == 1
    # All persisted rules start as DETECTED — operator must confirm.
    assert all(
        r.status == PreferenceRuleStatus.DETECTED.value for r in rules
    )


# ---------------------------------------------------------------------------
# Sprint R.2 — anti-re-emit suppression
# ---------------------------------------------------------------------------


def _rejected_temporal_rule(weekday: int) -> PreferenceRule:
    rule = PreferenceRule(
        id=uuid4(),
        tenant_id=TENANT,
        type=PreferenceRuleType.TEMPORAL_BLOCK.value,
        description=f"manager rejected weekday {weekday} pattern",
        predicate={"weekday": weekday},
        confidence=0.85,
        status=PreferenceRuleStatus.REJECTED.value,
        detected_from_commits=[],
    )
    return rule


def test_anti_re_emit_suppresses_candidate_with_rejected_signature():
    """A previously REJECTED rule for the same (type, predicate) signature
    must not be re-emitted, even when the data still supports it."""
    commits = [
        _make_commit(
            weekday=5,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            sha_suffix=chr(ord("a") + i),
        )
        for i in range(6)
    ]
    rejected = [_rejected_temporal_rule(weekday=5)]
    session = _FakeSession(commits, rejected_rules=rejected)
    detector = PreferenceRuleDetector(session, TENANT)

    rules = asyncio.run(detector.scan())

    # Six Friday commits would normally produce one TEMPORAL_BLOCK rule —
    # but the operator has already rejected that exact signature.
    assert all(
        r.type != PreferenceRuleType.TEMPORAL_BLOCK.value for r in rules
    )


def test_anti_re_emit_does_not_block_different_signature():
    """A REJECTED rule for weekday=4 must NOT suppress a fresh
    weekday=5 candidate — different signature, different rule."""
    commits = [
        _make_commit(
            weekday=5,
            rejected=[{"alt_idx": 0, "kpis": {}}],
            sha_suffix=chr(ord("a") + i),
        )
        for i in range(6)
    ]
    rejected = [_rejected_temporal_rule(weekday=4)]  # different weekday
    session = _FakeSession(commits, rejected_rules=rejected)
    detector = PreferenceRuleDetector(session, TENANT)

    rules = asyncio.run(detector.scan())
    temporal = [
        r for r in rules
        if r.type == PreferenceRuleType.TEMPORAL_BLOCK.value
    ]
    assert len(temporal) == 1
    assert temporal[0].predicate["weekday"] == 5
