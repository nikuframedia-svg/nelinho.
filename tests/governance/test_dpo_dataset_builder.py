"""Sprint I.1 — DPODatasetBuilder: extract DPO triplets from ScheduleCommit.

Covers:
* ``build_prompt`` renders a consistent, KPI-ordered prompt.
* ``DPODatasetBuilder.build_to_list`` emits N triplets per commit with
  N rejected_alternatives.
* Commits with no rejection are skipped; missing KPIs are skipped.
* ``min_reason_len`` filter gates on the operator's written reason.
* ``build`` writes valid JSONL when ``output_path`` is supplied.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from src.governance.preference_learning.dpo_dataset_builder import (
    DPOBuildReport,
    DPODatasetBuilder,
    DPOTriplet,
    build_prompt,
)
from src.plan.cpo.commits import ScheduleCommit
from tests.conftest import FakeSession


TENANT = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ─── Test doubles ─────────────────────────────────────────────────────────


def _commit(
    *,
    kpis: Dict[str, Any] | None = None,
    rejected: List[Dict[str, Any]] | None = None,
    signal: Dict[str, Any] | None = None,
    sha_suffix: str = "a",
    created_at: datetime | None = None,
) -> ScheduleCommit:
    sha = (sha_suffix * 64)[:64]
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=None,
        commit_sha256=sha,
        author="test",
        message="",
        kpis=kpis or {
            "makespan_hours": 180.0,
            "total_tardiness_hours": 12.0,
            "setups": 4,
            "throughput_eur_day": 31_000.0,
        },
        operations=[],
        delta={},
        alternatives=[],
        cpo_meta={},
        rejected_alternatives=rejected or [],
        user_preference_signal=signal or {
            # Sprint R.2 — default reason ≥10 chars so the new
            # min_reason_len=10 default doesn't filter every fixture.
            "decided_by": "alice",
            "weekday": 3,
            "reason": "default test rationale",
        },
        evidence_refs=[],
        scenarios_tested=0,
        trust_index=0.9,
        operations_count=0,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _session_with_commits(commits: List[ScheduleCommit]) -> FakeSession:
    """Q.68.3.3 — Canonical FakeSession with commits queued for ``execute().scalars().all()``."""
    session = FakeSession()
    session.queue_scalars(list(commits))
    return session


# ─── build_prompt ─────────────────────────────────────────────────────────


def test_build_prompt_renders_both_plans_in_order():
    chosen = {"makespan_hours": 180.0, "setups": 3, "throughput_eur_day": 31000}
    rejected = {"makespan_hours": 170.0, "setups": 7, "throughput_eur_day": 32000}
    prompt = build_prompt(chosen, rejected)
    # Headline sections present
    assert "Plano A" in prompt
    assert "Plano B" in prompt
    # Chosen KPIs appear before rejected KPIs
    assert prompt.index("180.0") < prompt.index("170.0")
    # Labels translated to PT
    assert "makespan (h)" in prompt
    assert "setups" in prompt


def test_build_prompt_omits_missing_kpis_silently():
    prompt = build_prompt({"makespan_hours": 200.0}, {})
    assert "makespan" in prompt
    # Empty plan B should show the fallback marker.
    assert "sem KPIs registados" in prompt


# ─── DPODatasetBuilder.build_to_list ──────────────────────────────────────


def test_emits_one_triplet_per_rejected_alternative():
    commits = [
        _commit(rejected=[
            {"alt_idx": 0, "kpis": {"makespan_hours": 200.0, "setups": 6}},
            {"alt_idx": 1, "kpis": {"makespan_hours": 210.0, "setups": 8}},
        ], sha_suffix="a"),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT)
    triplets = asyncio.run(builder.build_to_list())
    assert len(triplets) == 2
    assert all(isinstance(t, DPOTriplet) for t in triplets)
    assert triplets[0].meta["alt_idx"] == 0
    assert triplets[1].meta["alt_idx"] == 1


def test_skips_commits_without_rejection():
    commits = [
        _commit(rejected=[], sha_suffix="a"),
        _commit(rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 200.0}}], sha_suffix="b"),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT)
    triplets = asyncio.run(builder.build_to_list())
    assert len(triplets) == 1


def test_skips_rejected_alt_without_kpis():
    commits = [
        _commit(rejected=[
            {"alt_idx": 0},  # missing kpis key
            {"alt_idx": 1, "kpis": {}},  # empty kpis
            {"alt_idx": 2, "kpis": {"makespan_hours": 195.0}},
        ], sha_suffix="c"),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT)
    triplets = asyncio.run(builder.build_to_list())
    assert len(triplets) == 1
    assert triplets[0].meta["alt_idx"] == 2


def test_min_reason_len_filters_commits_without_written_rationale():
    commits = [
        _commit(
            rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 200.0}}],
            signal={"decided_by": "bob"},  # no reason
            sha_suffix="d",
        ),
        _commit(
            rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 200.0}}],
            signal={"decided_by": "bob", "reason": "trade throughput for quality"},
            sha_suffix="e",
        ),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT, min_reason_len=8)
    triplets = asyncio.run(builder.build_to_list())
    assert len(triplets) == 1
    assert "trade throughput" in triplets[0].chosen.lower()


def test_meta_copies_signal_and_commit_fields():
    commits = [
        _commit(
            rejected=[{"alt_idx": 3, "kpis": {"makespan_hours": 205.0}}],
            signal={"decided_by": "alice", "weekday": 5, "reason": "sexta sem Laminagem"},
            sha_suffix="f",
        ),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT)
    triplets = asyncio.run(builder.build_to_list())
    meta = triplets[0].meta
    assert meta["decided_by"] == "alice"
    assert meta["weekday"] == 5
    assert meta["alt_idx"] == 3
    assert "sexta" in meta["reason"].lower()
    assert len(meta["commit_sha"]) == 12


def test_build_writes_valid_jsonl(tmp_path: Path):
    commits = [
        _commit(rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 190.0}}], sha_suffix="g"),
        _commit(rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 215.0}}], sha_suffix="h"),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT)
    output = tmp_path / "dpo.jsonl"
    report: DPOBuildReport = asyncio.run(builder.build(output_path=output))

    assert report.triplets_emitted == 2
    assert report.output_path == str(output)
    # File contains 2 lines, each parseable as JSON.
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        payload = json.loads(line)
        assert set(payload.keys()) == {"prompt", "chosen", "rejected", "meta"}


def test_build_report_counts_scanned_and_used():
    commits = [
        _commit(rejected=[], sha_suffix="i"),  # skipped
        _commit(rejected=[{"alt_idx": 0, "kpis": {"makespan_hours": 200.0}}], sha_suffix="j"),
        _commit(rejected=[
            {"alt_idx": 0, "kpis": {"makespan_hours": 210.0}},
            {"alt_idx": 1, "kpis": {}},  # kpi-less, skipped within the commit
        ], sha_suffix="k"),
    ]
    builder = DPODatasetBuilder(_session_with_commits(commits), TENANT)
    report = asyncio.run(builder.build(output_path=None))
    assert report.commits_scanned == 3
    assert report.commits_used == 2
    assert report.triplets_emitted == 2
    assert report.skipped_empty_rejections == 1
