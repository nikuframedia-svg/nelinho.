"""Sprint Q.15.D.2 — Reichenbach core tests.

Three layers:

  1. Each check (SharedMold, SharedWorkers, Cascade) trips when the
     evidence matches and stays clean otherwise.
  2. The orchestrator picks shared-resource hypotheses BEFORE cascade
     so a real shared mold doesn't get mis-classified as cascade.
  3. When no common cause is found, falls back to per-phase ERRO-TREE
     and returns verdict='independent' with those root_causes.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.explain.diagnostics.reichenbach import (
    CascadeCheck,
    CommonCauseResult,
    ReichenbachDetector,
    SharedMoldCheck,
    SharedWorkersCheck,
)
from src.explain.diagnostics.types import (
    DiagnosticResult,
    Hypothesis,
    MoldUsage,
    TriggerType,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _make_repo(**overrides):
    """Repository with all helpers stubbed to a no-op default."""
    repo = AsyncMock()
    repo.boats_through_phases.return_value = []
    repo.molds_used_by_boats.return_value = {}
    repo.workers_in_phase_set.return_value = set()
    repo.worker_hours_during.return_value = 0.0
    repo.mold_usage.side_effect = lambda mold_id, *a, **kw: MoldUsage(
        mold_id=mold_id, total_phases=0, error_count=0,
    )
    repo.phase_precedes.return_value = False
    repo.phase_error_rate.return_value = 0.0
    for key, value in overrides.items():
        attr = getattr(repo, key)
        if callable(value) or isinstance(value, type(lambda: None)):
            attr.side_effect = value
        else:
            attr.return_value = value
    return repo


def _patch_persist(monkeypatch):
    import src.shared.decorators as decorators

    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(decorators, "_persist_firing", _noop)


# ───────────────────────────────────────────────────────────────────────────
# SharedMoldCheck
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shared_mold_trips_when_mold_dominant_and_anomalous():
    """3 boats common to deviating phases all use M-7; recent error
    rate 30% vs historical 10% → hypothesis emitted."""
    repo = _make_repo()
    repo.boats_through_phases.return_value = ["OF-A", "OF-B", "OF-C"]
    repo.molds_used_by_boats.return_value = {"M-7": 6, "M-9": 1}

    # mold_usage called twice per mold candidate (recent + historical)
    usages = {
        ("M-7", "recent"): MoldUsage(mold_id="M-7", total_phases=20, error_count=6),
        ("M-7", "hist"): MoldUsage(mold_id="M-7", total_phases=200, error_count=20),
    }
    call_idx = {"i": 0}

    async def _usage(mold_id, *_a, **_kw):
        seq = ["recent", "hist"]
        out = usages[(mold_id, seq[call_idx["i"] % 2])]
        call_idx["i"] += 1
        return out

    repo.mold_usage = AsyncMock(side_effect=_usage)

    check = SharedMoldCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"],
        period_days=7,
    )
    assert h is not None
    assert h.type == "shared_mold"
    assert h.entity == "M-7"
    assert h.confidence >= 0.7


@pytest.mark.asyncio
async def test_shared_mold_skips_when_no_common_boats():
    repo = _make_repo()  # boats_through_phases returns []
    check = SharedMoldCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


@pytest.mark.asyncio
async def test_shared_mold_skips_below_share_threshold():
    """Mold appears in only 10% of common-boat phases — too sparse to
    be the shared cause."""
    repo = _make_repo()
    repo.boats_through_phases.return_value = ["OF-A", "OF-B"]
    repo.molds_used_by_boats.return_value = {
        "M-1": 1, "M-2": 1, "M-3": 1, "M-4": 1, "M-5": 1,
        "M-6": 1, "M-7": 1, "M-8": 1, "M-9": 1, "M-10": 1,
    }
    check = SharedMoldCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


@pytest.mark.asyncio
async def test_shared_mold_skips_when_not_anomalous():
    """Mold dominant but recent error rate matches historical — no signal."""
    repo = _make_repo()
    repo.boats_through_phases.return_value = ["OF-A", "OF-B"]
    repo.molds_used_by_boats.return_value = {"M-7": 5}

    async def _usage(mold_id, *_a, **_kw):
        # Same rate in both windows
        return MoldUsage(mold_id="M-7", total_phases=100, error_count=12)

    repo.mold_usage = AsyncMock(side_effect=_usage)

    check = SharedMoldCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# SharedWorkersCheck
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shared_workers_trips_when_overloaded_worker_in_all_phases():
    """w-pivot active in BOTH phases AND working 60h in 7d → hypothesis."""
    repo = _make_repo()
    repo.workers_in_phase_set.side_effect = [
        {"w-pivot", "w-other-A"},
        {"w-pivot", "w-other-B"},
    ]
    repo.worker_hours_during.return_value = 60.0  # > 45h/wk threshold

    check = SharedWorkersCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is not None
    assert h.type == "shared_workers"
    assert h.entity == "w-pivot"


@pytest.mark.asyncio
async def test_shared_workers_skips_when_no_intersection():
    """Phases have disjoint worker sets → no shared worker."""
    repo = _make_repo()
    repo.workers_in_phase_set.side_effect = [
        {"w-1", "w-2"},
        {"w-3", "w-4"},
    ]
    check = SharedWorkersCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


@pytest.mark.asyncio
async def test_shared_workers_skips_when_no_overload():
    """Shared worker exists but works normal hours — no hypothesis."""
    repo = _make_repo()
    repo.workers_in_phase_set.side_effect = [
        {"w-pivot"}, {"w-pivot"},
    ]
    repo.worker_hours_during.return_value = 35.0  # below 45h threshold
    check = SharedWorkersCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# CascadeCheck
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cascade_trips_when_upstream_phase_has_high_errors():
    """LAMINAGEM precedes DESMOLDE; LAMINAGEM has 25% error rate →
    cascade hypothesis pointing at LAMINAGEM."""
    repo = _make_repo()
    # Direction: A→B
    async def _precedes(a, b):
        return a == "LAMINAGEM" and b == "DESMOLDE"
    repo.phase_precedes = AsyncMock(side_effect=_precedes)

    async def _rate(phase, *a, **kw):
        return 0.25 if phase == "LAMINAGEM" else 0.05
    repo.phase_error_rate = AsyncMock(side_effect=_rate)

    check = CascadeCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "DESMOLDE"], period_days=7,
    )
    assert h is not None
    assert h.type == "cascade_effect"
    assert "LAMINAGEM" in h.entity and "DESMOLDE" in h.entity


@pytest.mark.asyncio
async def test_cascade_skips_when_phases_unrelated_in_routing():
    """No precedence relation → no cascade."""
    repo = _make_repo()  # phase_precedes returns False default
    check = CascadeCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "MONTAGEM"], period_days=7,
    )
    assert h is None


@pytest.mark.asyncio
async def test_cascade_skips_when_upstream_clean():
    """LAMINAGEM precedes DESMOLDE but LAMINAGEM error rate is normal →
    can't be the cause of DESMOLDE drift."""
    repo = _make_repo()
    async def _precedes(a, b):
        return a == "LAMINAGEM" and b == "DESMOLDE"
    repo.phase_precedes = AsyncMock(side_effect=_precedes)
    repo.phase_error_rate.return_value = 0.05  # below 15% floor

    check = CascadeCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "DESMOLDE"], period_days=7,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# Orchestrator
# ───────────────────────────────────────────────────────────────────────────


def _make_detector_with_repo(repo):
    detector = ReichenbachDetector.__new__(ReichenbachDetector)
    detector.session = None
    detector.tenant_id = _TENANT
    detector._repo = repo
    detector._erro_tree = AsyncMock()  # not used in shared-cause path
    detector._checks = [
        SharedMoldCheck(repo),
        SharedWorkersCheck(repo),
        CascadeCheck(repo),
    ]
    return detector


@pytest.mark.asyncio
async def test_orchestrator_input_validation_rejects_one_phase(monkeypatch):
    """Caller must supply >= 2 phases; one phase isn't a Reichenbach
    case at all."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    detector = _make_detector_with_repo(repo)
    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM"], period_days=7,
    )
    assert isinstance(result, CommonCauseResult)
    assert result.verdict == "inconclusive"
    assert result.common_causes == []


@pytest.mark.asyncio
async def test_orchestrator_returns_common_cause_when_mold_check_trips(monkeypatch):
    _patch_persist(monkeypatch)
    repo = _make_repo()
    repo.boats_through_phases.return_value = ["OF-A", "OF-B"]
    repo.molds_used_by_boats.return_value = {"M-7": 6}

    async def _usage(mold_id, start, end):
        # Recent: high. Historical: low.
        if start.year == end.year and (end - start).days <= 7:
            return MoldUsage(mold_id=mold_id, total_phases=20, error_count=6)
        return MoldUsage(mold_id=mold_id, total_phases=200, error_count=20)
    repo.mold_usage = AsyncMock(side_effect=_usage)

    detector = _make_detector_with_repo(repo)
    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert result.verdict == "common_cause"
    assert len(result.common_causes) == 1
    assert result.common_causes[0].type == "shared_mold"


@pytest.mark.asyncio
async def test_orchestrator_falls_back_to_independent_when_no_common_cause(monkeypatch):
    """All 3 checks clean → run ERRO-TREE per phase. Result has
    `independent_causes` + verdict 'independent'."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    detector = _make_detector_with_repo(repo)

    # ERRO-TREE returns a different hypothesis per phase.
    h_lam = Hypothesis(
        type="mold_degradation", entity="M-1",
        alpha=8, beta=2, evidence=["per-phase mold"],
    )
    h_pin = Hypothesis(
        type="worker_skill", entity="w-bad",
        alpha=6, beta=2, evidence=["per-phase worker"],
    )

    async def _investigate(*, trigger, period_days, phase_id):
        if phase_id == "LAMINAGEM":
            return DiagnosticResult(
                root_cause=h_lam, chain=[], steps_checked=[], recommendation={},
            )
        return DiagnosticResult(
            root_cause=h_pin, chain=[], steps_checked=[], recommendation={},
        )

    detector._erro_tree.investigate = AsyncMock(side_effect=_investigate)

    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert result.verdict == "independent"
    assert len(result.independent_causes) == 2
    types = {h.type for h in result.independent_causes}
    assert types == {"mold_degradation", "worker_skill"}


@pytest.mark.asyncio
async def test_orchestrator_returns_inconclusive_when_no_common_cause_and_no_independent(monkeypatch):
    """All checks clean AND ERRO-TREE produces no hypothesis per phase."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    detector = _make_detector_with_repo(repo)

    detector._erro_tree.investigate = AsyncMock(return_value=DiagnosticResult(
        root_cause=None, chain=["nothing"], steps_checked=[], recommendation={},
    ))

    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert result.verdict == "inconclusive"
    assert result.common_causes == []
    assert result.independent_causes == []


@pytest.mark.asyncio
async def test_orchestrator_swallows_check_exceptions(monkeypatch):
    """A check raising must NOT crash the cascade."""
    _patch_persist(monkeypatch)
    repo = _make_repo()
    detector = _make_detector_with_repo(repo)
    # Force the mold check to blow up.
    repo.boats_through_phases.side_effect = RuntimeError("DB exploded")
    detector._erro_tree.investigate = AsyncMock(return_value=DiagnosticResult(
        root_cause=None, chain=[], steps_checked=[], recommendation={},
    ))

    # Should NOT raise.
    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    # And the failed check is reported as CLEAR in the audit.
    mold_step = next(s for s in result.checks_run if s["step"] == "shared_mold")
    assert mold_step["result"] == "CLEAR"
