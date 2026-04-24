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


class _FakeSession:
    def __init__(self, commits: List[ScheduleCommit]) -> None:
        self._commits = commits
        self.added: List[Any] = []
        self.flush_calls = 0

    async def execute(self, _stmt):
        # Return a mock result whose .scalars().all() yields our commits.
        class _R:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                class _S:
                    def __init__(self, rows):
                        self._rows = rows

                    def all(self):
                        return list(self._rows)

                return _S(self._rows)

        return _R(self._commits)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flush_calls += 1


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
