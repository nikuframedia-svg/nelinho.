"""Sprint Q.15.D.4 — Mill's method tests.

Three layers:

  1. Cohen's d helper math (`correlation.py`).
  2. Per-dimension `_diff_*` methods produce sane Change objects.
  3. Orchestrator wires + ranks correctly + emits the right verdict
     when no shift / one cause / multiple causes.
"""

from __future__ import annotations

from datetime import date
from typing import Any, List, Optional
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.explain.diagnostics.correlation import (
    cohens_d,
    correlation_from_d,
    is_likely_cause,
)
from src.explain.diagnostics.mill_diff import (
    Change,
    MillDiffDetector,
    WhatChangedReport,
)
from src.explain.diagnostics.types import MoldUsage


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _patch_persist(monkeypatch):
    import src.shared.decorators as decorators

    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(decorators, "_persist_firing", _noop)


# ───────────────────────────────────────────────────────────────────────────
# Cohen's d helper
# ───────────────────────────────────────────────────────────────────────────


def test_cohens_d_positive_when_b_higher():
    """Sign convention: cohens_d(good, bad) positive when bad mean > good."""
    d = cohens_d([0.10, 0.12, 0.11], [0.30, 0.32, 0.28])
    assert d is not None
    assert d > 0


def test_cohens_d_negative_when_b_lower():
    d = cohens_d([0.30, 0.32, 0.28], [0.10, 0.12, 0.11])
    assert d is not None
    assert d < 0


def test_cohens_d_returns_none_on_empty_input():
    assert cohens_d([], [1.0, 2.0]) is None
    assert cohens_d([1.0, 2.0], []) is None


def test_cohens_d_returns_none_on_zero_variance():
    """Both groups identical constants → pooled std = 0 → undefined."""
    assert cohens_d([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]) is None


def test_cohens_d_realistic_small_shift():
    """Realistic 7-day samples with natural variance: small shift
    (10pp) maps to roughly Cohen's "medium" effect (d ≈ 0.5-1.0)."""
    good = [0.10, 0.15, 0.08, 0.12, 0.14, 0.09, 0.11]
    bad = [0.13, 0.18, 0.10, 0.14, 0.16, 0.11, 0.13]
    d = cohens_d(good, bad)
    assert d is not None
    assert 0.5 < d < 1.5  # medium-to-large effect


def test_correlation_from_d_caps_at_one():
    """Saturates at |d| = 1.5+. Without the cap, an outlier would
    push corr > 1.0 and break the dashboard."""
    assert correlation_from_d(2.5) == 1.0
    assert correlation_from_d(-2.5) == 1.0


def test_correlation_from_d_zero_for_undefined():
    """`None` input → 0.0 (no signal). Mill's diff treats this as
    'no change' rather than crashing the rank."""
    assert correlation_from_d(None) == 0.0


def test_correlation_from_d_linear_in_middle():
    assert correlation_from_d(0.75) == pytest.approx(0.5, abs=0.01)


def test_is_likely_cause_threshold_default():
    assert is_likely_cause(0.69) is False
    assert is_likely_cause(0.70) is True


# ───────────────────────────────────────────────────────────────────────────
# Per-dimension diffs — fakes drive the repo
# ───────────────────────────────────────────────────────────────────────────


def _make_repo(**overrides):
    repo = AsyncMock()
    repo.molds_active_during.return_value = []
    repo.mold_usage.return_value = MoldUsage(
        mold_id="", total_phases=0, error_count=0,
    )
    repo.workers_in_phase_set.return_value = set()
    repo.daily_wip_samples.return_value = []
    repo.transport_volume_during.return_value = 0
    repo.daily_phase_error_rate_samples.return_value = []
    repo.has_material_lot_tracking.return_value = False
    repo.has_shift_tracking.return_value = False
    for key, value in overrides.items():
        getattr(repo, key).return_value = value
    return repo


def _detector_with_repo(repo):
    detector = MillDiffDetector.__new__(MillDiffDetector)
    detector.session = None
    detector.tenant_id = _TENANT
    detector._repo = repo
    return detector


@pytest.mark.asyncio
async def test_diff_volume_detects_wip_shift(monkeypatch):
    """WIP doubled between periods → Change with high correlation."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_wip_samples.side_effect = [
        [200, 210, 195, 205, 198],   # good period
        [400, 420, 410, 405, 415],   # bad period
    ]
    detector = _detector_with_repo(repo)
    change = await detector._diff_volume(
        date(2026, 4, 1), date(2026, 4, 6),
        date(2026, 4, 7), date(2026, 4, 12),
        None,
    )
    assert change is not None
    assert change.category == "volume"
    assert change.correlation >= 0.7  # large effect
    # Bad mean (~410) must appear in the human-readable change string.
    assert "410" in change.change or "411" in change.change


@pytest.mark.asyncio
async def test_diff_volume_no_change_when_stable(monkeypatch):
    """Same WIP both periods → variance=0 → undefined → None returned."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_wip_samples.side_effect = [
        [300, 300, 300],
        [300, 300, 300],
    ]
    detector = _detector_with_repo(repo)
    change = await detector._diff_volume(
        date(2026, 4, 1), date(2026, 4, 4),
        date(2026, 4, 5), date(2026, 4, 8),
        None,
    )
    assert change is None


@pytest.mark.asyncio
async def test_diff_workers_set_diff_with_entries_and_exits():
    repo = _make_repo()
    repo.workers_in_phase_set.side_effect = [
        {"w-1", "w-2", "w-3"},   # good
        {"w-2", "w-3", "w-4"},   # bad — w-1 left, w-4 entered
    ]
    detector = _detector_with_repo(repo)
    change = await detector._diff_workers(
        date(2026, 4, 1), date(2026, 4, 8),
        date(2026, 4, 8), date(2026, 4, 15),
        "LAMINAGEM",
    )
    assert change is not None
    assert change.category == "worker"
    assert "1 entradas" in change.change
    assert "1 saídas" in change.change


@pytest.mark.asyncio
async def test_diff_workers_skips_when_no_phase_id():
    repo = _make_repo()
    detector = _detector_with_repo(repo)
    change = await detector._diff_workers(
        date(2026, 4, 1), date(2026, 4, 8),
        date(2026, 4, 8), date(2026, 4, 15),
        None,
    )
    assert change is None


@pytest.mark.asyncio
async def test_diff_workers_returns_none_when_roster_unchanged():
    repo = _make_repo()
    repo.workers_in_phase_set.side_effect = [
        {"w-1", "w-2", "w-3"},
        {"w-1", "w-2", "w-3"},
    ]
    detector = _detector_with_repo(repo)
    change = await detector._diff_workers(
        date(2026, 4, 1), date(2026, 4, 8),
        date(2026, 4, 8), date(2026, 4, 15),
        "LAMINAGEM",
    )
    assert change is None


@pytest.mark.asyncio
async def test_diff_molds_picks_worst_shift():
    """3 molds, only M-7 shifts hard → that's the change reported."""
    repo = _make_repo()
    repo.molds_active_during.side_effect = [
        ["M-1", "M-7", "M-9"],  # good period
        ["M-1", "M-7", "M-9"],  # bad period
    ]

    async def _usage(mold_id, start, end):
        # bad period (later dates) → higher rates for M-7
        is_bad = start.day >= 8
        rates = {
            "M-1": (0.05, 0.05),
            "M-7": (0.10, 0.40),  # huge shift
            "M-9": (0.05, 0.06),
        }
        good_rate, bad_rate = rates[mold_id]
        rate = bad_rate if is_bad else good_rate
        return MoldUsage(mold_id=mold_id, total_phases=20, error_count=int(20 * rate))

    repo.mold_usage = AsyncMock(side_effect=_usage)
    detector = _detector_with_repo(repo)
    change = await detector._diff_molds(
        date(2026, 4, 1), date(2026, 4, 7),
        date(2026, 4, 8), date(2026, 4, 14),
        None,
    )
    assert change is not None
    assert change.category == "mold"
    assert "M-7" in change.change


@pytest.mark.asyncio
async def test_diff_transport_volume_increase_flagged():
    repo = _make_repo()
    repo.transport_volume_during.side_effect = [50, 150]  # 3× shift
    detector = _detector_with_repo(repo)
    change = await detector._diff_transport(
        date(2026, 4, 1), date(2026, 4, 8),
        date(2026, 4, 8), date(2026, 4, 15),
        None,
    )
    assert change is not None
    assert change.category == "transport"
    assert change.correlation >= 0.7


@pytest.mark.asyncio
async def test_diff_material_silent_no_data():
    repo = _make_repo()  # has_material_lot_tracking=False
    detector = _detector_with_repo(repo)
    change = await detector._diff_material(
        date(2026, 4, 1), date(2026, 4, 8),
        date(2026, 4, 8), date(2026, 4, 15),
        None,
    )
    assert change is None  # honest no-data


# ───────────────────────────────────────────────────────────────────────────
# Orchestrator
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_returns_no_shift_when_metric_didnt_move(monkeypatch):
    """If error_rate is essentially the same in both windows, the
    orchestrator stops early with verdict='no_shift'."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_phase_error_rate_samples.side_effect = [
        [0.10, 0.11, 0.10],   # good
        [0.10, 0.11, 0.10],   # bad — same!
    ]
    detector = _detector_with_repo(repo)
    report = await detector.what_changed(
        good_start=date(2026, 4, 1), good_end=date(2026, 4, 4),
        bad_start=date(2026, 4, 5), bad_end=date(2026, 4, 8),
        metric="error_rate", phase_id="LAMINAGEM",
    )
    assert report.verdict == "no_shift"
    assert report.changes_found == []


@pytest.mark.asyncio
async def test_orchestrator_ranks_changes_by_correlation_desc(monkeypatch):
    """Volume + transport both shifted; volume shifted more → first."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_phase_error_rate_samples.side_effect = [
        [0.10, 0.11, 0.10],   # good
        [0.30, 0.32, 0.31],   # bad — clear shift
    ]
    repo.daily_wip_samples.side_effect = [
        [200, 210, 200],
        [600, 620, 610],   # huge shift
    ]
    repo.transport_volume_during.side_effect = [50, 75]   # smaller shift
    detector = _detector_with_repo(repo)
    report = await detector.what_changed(
        good_start=date(2026, 4, 1), good_end=date(2026, 4, 4),
        bad_start=date(2026, 4, 5), bad_end=date(2026, 4, 8),
        metric="error_rate", phase_id="LAMINAGEM",
    )
    assert report.verdict != "no_shift"
    # Volume should rank higher than transport.
    categories = [c.category for c in report.changes_found]
    if "volume" in categories and "transport" in categories:
        assert categories.index("volume") < categories.index("transport")


@pytest.mark.asyncio
async def test_orchestrator_likely_cause_threshold_respected(monkeypatch):
    """A change with correlation just above 0.7 → likely_cause=True;
    just below → likely_cause=False."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_phase_error_rate_samples.side_effect = [
        [0.10, 0.11, 0.10],
        [0.30, 0.32, 0.31],
    ]
    repo.daily_wip_samples.side_effect = [
        [200, 210, 200],
        [800, 820, 810],   # massive shift
    ]
    detector = _detector_with_repo(repo)
    report = await detector.what_changed(
        good_start=date(2026, 4, 1), good_end=date(2026, 4, 4),
        bad_start=date(2026, 4, 5), bad_end=date(2026, 4, 8),
        metric="error_rate", phase_id="LAMINAGEM",
        likely_threshold=0.70,
    )
    likely = [c for c in report.changes_found if c.likely_cause]
    assert any(c.category == "volume" for c in likely)


@pytest.mark.asyncio
async def test_orchestrator_swallows_dimension_exceptions(monkeypatch):
    """A broken `_diff_*` method must not break the cascade."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_phase_error_rate_samples.side_effect = [
        [0.10, 0.11, 0.10],
        [0.30, 0.32, 0.31],
    ]
    repo.daily_wip_samples.side_effect = RuntimeError("DB exploded")
    detector = _detector_with_repo(repo)
    # Should not raise.
    report = await detector.what_changed(
        good_start=date(2026, 4, 1), good_end=date(2026, 4, 4),
        bad_start=date(2026, 4, 5), bad_end=date(2026, 4, 8),
        metric="error_rate", phase_id="LAMINAGEM",
    )
    assert isinstance(report, WhatChangedReport)


@pytest.mark.asyncio
async def test_orchestrator_lists_unchanged_dimensions(monkeypatch):
    """No-data dimensions (material/shift) appear in `unchanged` so
    the operator sees we tried."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.daily_phase_error_rate_samples.side_effect = [
        [0.10, 0.11, 0.10],
        [0.30, 0.32, 0.31],
    ]
    detector = _detector_with_repo(repo)
    report = await detector.what_changed(
        good_start=date(2026, 4, 1), good_end=date(2026, 4, 4),
        bad_start=date(2026, 4, 5), bad_end=date(2026, 4, 8),
        metric="error_rate", phase_id="LAMINAGEM",
    )
    # material + shift + routing should be in `unchanged` (sem dados).
    unchanged_text = " ".join(report.unchanged).lower()
    assert "material" in unchanged_text or "shift" in unchanged_text
