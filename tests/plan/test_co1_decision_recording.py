"""Sprint B CO1 — rejected_alternatives + user_preference_signal.

Covers:
* `CommitsService.record_decision` serialises each rejected alternative
  with its KPIs, delta vs chosen and the weekday/hour of the decision.
* Out-of-range / contradictory indices raise ValueError (fail loud).
* `to_dict` exposes the new fields so the Timeline UI can read them.
* `_build_rejected_record` computes delta_vs_chosen only for numeric
  KPIs present on both sides.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.commits import (
    CommitsService,
    ScheduleCommit,
    _build_rejected_record,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _make_commit_with_alternatives(alternatives: List[Dict[str, Any]]) -> ScheduleCommit:
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256="a" * 64,
        author="system",
        message="",
        kpis={"makespan_hours": 100.0, "throughput_eur_day": 28000.0},
        operations=[],
        delta={},
        alternatives=alternatives,
        cpo_meta={},
        rejected_alternatives=[],
        user_preference_signal={},
        evidence_refs=[],
        scenarios_tested=0,
        trust_index=0.8,
        operations_count=0,
    )


class _FakeSession:
    """Minimal async session that returns a pre-seeded commit on .get()."""

    def __init__(self, commit: ScheduleCommit) -> None:
        self._commit = commit
        self.flush_calls = 0

    async def get(self, _model, _id):
        return self._commit

    async def flush(self):
        self.flush_calls += 1


# ---------------------------------------------------------------------------
# _build_rejected_record — pure helper
# ---------------------------------------------------------------------------


def test_build_rejected_record_computes_numeric_delta():
    chosen = {"kpis": {"makespan_hours": 100.0, "throughput_eur_day": 28000.0}}
    alt = {
        "kpis": {"makespan_hours": 105.0, "throughput_eur_day": 27000.0},
        "mapelites_cell": [0.8, 0.1, 0.2],
    }
    rec = _build_rejected_record(
        alt=alt, chosen=chosen, reason=None,
        rejected_at=datetime(2026, 4, 22, 14, 30), alt_idx=3,
    )
    assert rec["alt_idx"] == 3
    assert rec["kpis"]["makespan_hours"] == 105.0
    # Alt is 5h slower and 1000€/day lower than chosen.
    assert rec["delta_vs_chosen"]["makespan_hours"] == 5.0
    assert rec["delta_vs_chosen"]["throughput_eur_day"] == -1000.0
    assert rec["mapelites_cell"] == [0.8, 0.1, 0.2]


def test_build_rejected_record_handles_missing_chosen():
    """When chosen is None, delta_vs_chosen stays empty but KPIs are still kept."""
    alt = {"kpis": {"makespan_hours": 110.0}}
    rec = _build_rejected_record(
        alt=alt, chosen=None, reason="too slow",
        rejected_at=datetime(2026, 4, 22, 10, 0), alt_idx=0,
    )
    assert rec["kpis"]["makespan_hours"] == 110.0
    assert rec["delta_vs_chosen"] == {}
    assert rec["rejection_reason"] == "too slow"


def test_build_rejected_record_skips_non_numeric_deltas():
    """Non-numeric KPIs (strings) must not crash the delta computation."""
    chosen = {"kpis": {"makespan_hours": 100.0, "status": "ok"}}
    alt = {"kpis": {"makespan_hours": 105.0, "status": "warn"}}
    rec = _build_rejected_record(
        alt=alt, chosen=chosen, reason=None,
        rejected_at=datetime.utcnow(), alt_idx=1,
    )
    assert "makespan_hours" in rec["delta_vs_chosen"]
    assert "status" not in rec["delta_vs_chosen"]


# ---------------------------------------------------------------------------
# record_decision — integration with a commit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_decision_writes_kpis_and_preference_signal():
    alternatives = [
        {"kpis": {"makespan_hours": 100.0, "throughput_eur_day": 28000.0}},  # chosen
        {"kpis": {"makespan_hours": 90.0, "throughput_eur_day": 26000.0}},   # rejected
        {"kpis": {"makespan_hours": 105.0, "throughput_eur_day": 30000.0}},  # rejected
    ]
    commit = _make_commit_with_alternatives(alternatives)
    session = _FakeSession(commit)
    svc = CommitsService(session, TENANT)

    decided_at = datetime(2026, 4, 24, 15, 45)  # Friday, 15:45
    await svc.record_decision(
        commit_id=commit.id,
        chosen_alt_idx=0,
        rejected_alt_idxs=[1, 2],
        decided_by="alice",
        decided_at=decided_at,
        reason="too aggressive on throughput",
    )

    assert len(commit.rejected_alternatives) == 2
    r1, r2 = commit.rejected_alternatives
    assert r1["alt_idx"] == 1
    assert r1["delta_vs_chosen"]["makespan_hours"] == -10.0
    assert r2["alt_idx"] == 2
    assert r2["delta_vs_chosen"]["throughput_eur_day"] == 2000.0

    sig = commit.user_preference_signal
    assert sig["chose_alt_idx"] == 0
    assert sig["rejected_alt_idxs"] == [1, 2]
    assert sig["decided_by"] == "alice"
    assert sig["weekday"] == 5  # Friday
    assert sig["hour"] == 15
    assert sig["reason"] == "too aggressive on throughput"

    assert session.flush_calls == 1


@pytest.mark.asyncio
async def test_record_decision_raises_on_out_of_range_chosen():
    commit = _make_commit_with_alternatives([{"kpis": {"makespan_hours": 100.0}}])
    svc = CommitsService(_FakeSession(commit), TENANT)

    with pytest.raises(ValueError, match="chosen_alt_idx"):
        await svc.record_decision(
            commit_id=commit.id,
            chosen_alt_idx=5,
            rejected_alt_idxs=[],
            decided_by="alice",
        )


@pytest.mark.asyncio
async def test_record_decision_raises_on_out_of_range_rejected():
    commit = _make_commit_with_alternatives([{"kpis": {"makespan_hours": 100.0}}])
    svc = CommitsService(_FakeSession(commit), TENANT)

    with pytest.raises(ValueError, match="rejected_alt_idx"):
        await svc.record_decision(
            commit_id=commit.id,
            chosen_alt_idx=0,
            rejected_alt_idxs=[0, 99],
            decided_by="alice",
        )


@pytest.mark.asyncio
async def test_record_decision_raises_when_chosen_also_in_rejected():
    commit = _make_commit_with_alternatives([
        {"kpis": {"makespan_hours": 100.0}},
        {"kpis": {"makespan_hours": 110.0}},
    ])
    svc = CommitsService(_FakeSession(commit), TENANT)

    with pytest.raises(ValueError, match="cannot appear"):
        await svc.record_decision(
            commit_id=commit.id,
            chosen_alt_idx=1,
            rejected_alt_idxs=[1],
            decided_by="alice",
        )


@pytest.mark.asyncio
async def test_record_decision_accepts_chosen_none():
    """When the operator accepts the primary commit without ranking, the
    rejected list still captures what they looked at — a valid signal
    for Camada 1 ("they considered but discarded these")."""
    alternatives = [
        {"kpis": {"makespan_hours": 100.0}},
        {"kpis": {"makespan_hours": 110.0}},
    ]
    commit = _make_commit_with_alternatives(alternatives)
    svc = CommitsService(_FakeSession(commit), TENANT)

    await svc.record_decision(
        commit_id=commit.id,
        chosen_alt_idx=None,
        rejected_alt_idxs=[0, 1],
        decided_by="bob",
        decided_at=datetime(2026, 4, 22, 9, 0),
    )

    assert commit.user_preference_signal["chose_alt_idx"] is None
    assert len(commit.rejected_alternatives) == 2
    # delta_vs_chosen is empty because there's no chosen baseline.
    for rec in commit.rejected_alternatives:
        assert rec["delta_vs_chosen"] == {}


# ---------------------------------------------------------------------------
# to_dict exposure of the new fields
# ---------------------------------------------------------------------------


def test_to_dict_surfaces_learning_fields():
    commit = _make_commit_with_alternatives([{"kpis": {"makespan_hours": 100.0}}])
    commit.rejected_alternatives = [{"alt_idx": 0, "kpis": {}}]
    commit.user_preference_signal = {"chose_alt_idx": 0, "decided_by": "alice"}
    commit.evidence_refs = [{"event_id": "e1"}]
    commit.scenarios_tested = 42

    d = CommitsService.to_dict(commit)
    assert d["rejected_alternatives"] == [{"alt_idx": 0, "kpis": {}}]
    assert d["user_preference_signal"] == {"chose_alt_idx": 0, "decided_by": "alice"}
    assert d["evidence_refs"] == [{"event_id": "e1"}]
    assert d["scenarios_tested"] == 42
