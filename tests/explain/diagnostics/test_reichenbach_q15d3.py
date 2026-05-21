"""Sprint Q.15.D.3 — Reichenbach completion tests.

Three new checks (material/transport/shift) + the scheduler hook for
the 30-min multivariate drift monitor.

Pin:
  * `SharedTransportCheck` trips at >= 75 boats upcoming, scales by ratio.
  * `SharedMaterialCheck` honestly returns None when no lot data
    (current NELO state) and the orchestrator records DATA_UNAVAILABLE.
  * `SharedShiftCheck` likewise — graceful no-data.
  * The orchestrator's audit trail distinguishes CLEAR from DATA_UNAVAILABLE.
"""

from __future__ import annotations

from datetime import date
from typing import Any, List, Optional
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.explain.diagnostics.reichenbach import (
    CommonCauseResult,
    ReichenbachDetector,
    SharedMaterialCheck,
    SharedShiftCheck,
    SharedTransportCheck,
)
from tests.conftest import FakeSession


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _make_repo(**overrides):
    repo = AsyncMock()
    # D.2 helpers default no-data
    repo.boats_through_phases.return_value = []
    repo.molds_used_by_boats.return_value = {}
    repo.workers_in_phase_set.return_value = set()
    repo.worker_hours_during.return_value = 0.0
    repo.phase_precedes.return_value = False
    repo.phase_error_rate.return_value = 0.0
    # D.3 helpers default no-data
    repo.upcoming_transport_volume.return_value = 0
    repo.has_material_lot_tracking.return_value = False
    repo.has_shift_tracking.return_value = False
    for key, value in overrides.items():
        getattr(repo, key).return_value = value
    return repo


def _patch_persist(monkeypatch):
    import src.shared.decorators as decorators

    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(decorators, "_persist_firing", _noop)


# ───────────────────────────────────────────────────────────────────────────
# SharedTransportCheck — REAL implementation
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shared_transport_trips_when_upcoming_volume_high():
    """120 barcos próximos 7 dias > 75 floor → hypothesis emitted."""
    repo = _make_repo(upcoming_transport_volume=120)
    check = SharedTransportCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is not None
    assert h.type == "shared_transport_pressure"
    assert "120 barcos" in h.entity
    assert h.confidence >= 0.7


@pytest.mark.asyncio
async def test_shared_transport_skips_when_below_floor():
    """50 barcos < 75 floor → no signal."""
    repo = _make_repo(upcoming_transport_volume=50)
    check = SharedTransportCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


@pytest.mark.asyncio
async def test_shared_transport_confidence_scales_with_volume():
    """Higher volume → higher confidence."""
    repo_low = _make_repo(upcoming_transport_volume=80)
    repo_high = _make_repo(upcoming_transport_volume=200)
    h_low = await SharedTransportCheck(repo_low).check(
        deviating_phases=["A", "B"], period_days=7,
    )
    h_high = await SharedTransportCheck(repo_high).check(
        deviating_phases=["A", "B"], period_days=7,
    )
    assert h_low is not None and h_high is not None
    assert h_high.confidence > h_low.confidence


@pytest.mark.asyncio
async def test_shared_transport_skips_single_phase():
    """1 phase isn't a Reichenbach case at all."""
    repo = _make_repo(upcoming_transport_volume=200)
    check = SharedTransportCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM"], period_days=7,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# SharedMaterialCheck — graceful no-data
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shared_material_returns_none_when_no_lot_tracking():
    repo = _make_repo()  # has_material_lot_tracking → False (default)
    check = SharedMaterialCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None  # honest no-data, NOT a fabricated hypothesis


@pytest.mark.asyncio
async def test_shared_material_skips_single_phase():
    repo = _make_repo(has_material_lot_tracking=True)
    check = SharedMaterialCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM"], period_days=7,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# SharedShiftCheck — graceful no-data
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shared_shift_returns_none_when_no_shift_tracking():
    repo = _make_repo()  # has_shift_tracking → False (default)
    check = SharedShiftCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    assert h is None


@pytest.mark.asyncio
async def test_shared_shift_skips_single_phase():
    repo = _make_repo(has_shift_tracking=True)
    check = SharedShiftCheck(repo)
    h = await check.check(
        deviating_phases=["LAMINAGEM"], period_days=7,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# Orchestrator — DATA_UNAVAILABLE audit trail
# ───────────────────────────────────────────────────────────────────────────


def _make_detector_with_repo(repo):
    from src.explain.diagnostics.reichenbach import (
        CascadeCheck,
        SharedMoldCheck,
        SharedWorkersCheck,
    )
    detector = ReichenbachDetector.__new__(ReichenbachDetector)
    detector.session = None
    detector.tenant_id = _TENANT
    detector._repo = repo
    detector._erro_tree = AsyncMock()
    detector._checks = [
        SharedMoldCheck(repo),
        SharedWorkersCheck(repo),
        SharedTransportCheck(repo),
        SharedMaterialCheck(repo),
        SharedShiftCheck(repo),
        CascadeCheck(repo),
    ]
    return detector


@pytest.mark.asyncio
async def test_orchestrator_marks_material_check_data_unavailable(monkeypatch):
    """When the curated layer has no lot data, the audit shows
    `DATA_UNAVAILABLE` for the material check, not CLEAR. That's the
    honest signal to the operator that we tried but couldn't."""
    from src.explain.diagnostics.types import DiagnosticResult

    _patch_persist(monkeypatch)
    repo = _make_repo()  # all D.3 helpers return no-data
    detector = _make_detector_with_repo(repo)
    detector._erro_tree.investigate = AsyncMock(return_value=DiagnosticResult(
        root_cause=None, chain=[], steps_checked=[], recommendation={},
    ))

    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    by_step = {s["step"]: s["result"] for s in result.checks_run}
    assert by_step["shared_material"] == "DATA_UNAVAILABLE"
    assert by_step["shared_shift"] == "DATA_UNAVAILABLE"
    # Mold + Workers + Cascade are CLEAR (real checks ran, no signal).
    assert by_step["shared_mold"] == "CLEAR"


@pytest.mark.asyncio
async def test_orchestrator_includes_transport_check_in_cascade(monkeypatch):
    """Transport check is wired in the cascade — ran even when other
    checks clean."""
    from src.explain.diagnostics.types import DiagnosticResult

    _patch_persist(monkeypatch)
    repo = _make_repo(upcoming_transport_volume=200)
    detector = _make_detector_with_repo(repo)
    detector._erro_tree.investigate = AsyncMock(return_value=DiagnosticResult(
        root_cause=None, chain=[], steps_checked=[], recommendation={},
    ))

    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    # Transport hypothesis should trip, becoming a common cause.
    assert result.verdict == "common_cause"
    assert any(
        h.type == "shared_transport_pressure" for h in result.common_causes
    )


@pytest.mark.asyncio
async def test_orchestrator_six_check_steps_in_audit(monkeypatch):
    """Audit trail records all 6 checks in order, even when most are
    CLEAR / DATA_UNAVAILABLE — operator sees the full investigation."""
    from src.explain.diagnostics.types import DiagnosticResult

    _patch_persist(monkeypatch)
    repo = _make_repo()
    detector = _make_detector_with_repo(repo)
    detector._erro_tree.investigate = AsyncMock(return_value=DiagnosticResult(
        root_cause=None, chain=[], steps_checked=[], recommendation={},
    ))

    result = await detector.find_common_cause(
        deviating_phases=["LAMINAGEM", "PINTURA"], period_days=7,
    )
    # 6 cascade checks + 1 erro_tree_fallback step = 7 total.
    step_names = [s["step"] for s in result.checks_run]
    assert "shared_mold" in step_names
    assert "shared_workers" in step_names
    assert "shared_transport" in step_names
    assert "shared_material" in step_names
    assert "shared_shift" in step_names
    assert "cascade" in step_names
    assert "erro_tree_fallback" in step_names


# ───────────────────────────────────────────────────────────────────────────
# Repository helpers (D.3-specific)
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_repo_upcoming_transport_volume_returns_zero_on_empty():
    """No batches → 0, not exception."""
    from src.explain.diagnostics.repository import DiagnosticsRepository

    session = FakeSession()
    session.queue_scalar(0)  # next execute().scalar() → 0
    repo = DiagnosticsRepository(session, _TENANT)
    out = await repo.upcoming_transport_volume(days_ahead=7)
    assert out == 0


@pytest.mark.asyncio
async def test_repo_has_material_lot_tracking_false_today():
    """Without `CuratedMaterialLot` ORM, returns False — honest signal."""
    from src.explain.diagnostics.repository import DiagnosticsRepository

    session = FakeSession()
    session.raise_on_execute = True  # repo must short-circuit before query
    repo = DiagnosticsRepository(session, _TENANT)
    assert await repo.has_material_lot_tracking() is False


@pytest.mark.asyncio
async def test_repo_has_shift_tracking_false_today():
    from src.explain.diagnostics.repository import DiagnosticsRepository

    session = FakeSession()
    session.raise_on_execute = True
    repo = DiagnosticsRepository(session, _TENANT)
    assert await repo.has_shift_tracking() is False
