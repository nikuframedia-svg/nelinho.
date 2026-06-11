"""Sprint Q.15.D.1 — ERRO-TREE detector tests.

Three layers:

  1. Each individual detector (Mold, Worker, Overload) trips when the
     evidence matches and stays clean otherwise.
  2. The orchestrator stops at the first detector with confidence >= 0.7
     and marks the rest SKIPPED.
  3. When no detector trips, returns a "no isolated cause" verdict
     with the steps_checked audit trail.

Each detector is tested with a stubbed DiagnosticsRepository so the
suite runs in <100ms and doesn't touch the DB.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Optional
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from src.explain.diagnostics.erro_tree import (
    ErroTreeDetector,
    MoldDetector,
    OverloadDetector,
    WorkerDetector,
)
from src.explain.diagnostics.types import (
    DiagnosticResult,
    Hypothesis,
    TriggerType,
    WorkerStats,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ───────────────────────────────────────────────────────────────────────────
# Fake repository — every method is an AsyncMock for fine-grained control.
# ───────────────────────────────────────────────────────────────────────────


def _make_fake_repo(**overrides):
    """Build a repo where each helper has a no-data default; pass
    overrides to inject specific test scenarios."""
    repo = AsyncMock()

    # Default: empty curated layer.
    repo.molds_active_during.return_value = []
    repo.mold_phase_count.return_value = 0
    repo.mold_error_count.return_value = 0
    repo.mold_error_types.return_value = Counter()
    repo.workers_active_in_phase.return_value = []
    repo.worker_phase_stats.return_value = WorkerStats(
        worker_id="", phase_id="", total_allocations=0, error_count=0,
    )
    repo.phase_error_rate.return_value = 0.0
    repo.current_wip.return_value = 0
    repo.avg_wip_during.return_value = 0.0

    for k, v in overrides.items():
        getattr(repo, k).return_value = v
    return repo


# ───────────────────────────────────────────────────────────────────────────
# MoldDetector
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mold_detector_trips_when_recent_rate_high_and_typed():
    """A mold with 30% recent error rate (vs 10% historical) AND
    >50% of errors mold-typed → hypothesis emitted."""
    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-7"]
    # Recent: 6 errors / 20 phases = 30%
    # Historical: 12 errors / 120 phases = 10%
    repo.mold_phase_count.side_effect = [20, 120]  # recent, historical
    repo.mold_error_count.side_effect = [6, 12]
    repo.mold_error_types.return_value = Counter({
        "interior enrugado": 4, "molde baço": 2,
    })

    det = MoldDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is not None
    assert h.type == "mold_degradation"
    assert h.entity == "M-7"
    assert h.confidence > 0.0


@pytest.mark.asyncio
async def test_mold_detector_skips_when_recent_rate_below_floor():
    """Recent rate 5% — below the 15% absolute floor → no hypothesis."""
    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-7"]
    repo.mold_phase_count.side_effect = [100, 100]
    repo.mold_error_count.side_effect = [5, 3]  # 5% / 3%
    repo.mold_error_types.return_value = Counter({"deformação": 5})

    det = MoldDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is None


@pytest.mark.asyncio
async def test_mold_detector_skips_when_no_baseline_history():
    """Brand-new mold (zero historical phases) → can't flag, abstain."""
    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-NEW"]
    repo.mold_phase_count.side_effect = [10, 0]  # zero historical
    repo.mold_error_count.side_effect = [3, 0]

    det = MoldDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is None


@pytest.mark.asyncio
async def test_mold_detector_skips_when_errors_not_mold_typed():
    """Recent rate high AND historical low, BUT errors are 'pintura
    com fios' / 'bolhas pequenas' (not mold-typed) → don't blame the mold."""
    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-7"]
    repo.mold_phase_count.side_effect = [20, 100]
    repo.mold_error_count.side_effect = [6, 5]
    # NB "bolha" IS mold-typed in our keyword list — use a definitively
    # non-mold-typed error type for this test.
    repo.mold_error_types.return_value = Counter({
        "pintura com fios": 5, "lixo na superficie": 1,
    })

    det = MoldDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is None


@pytest.mark.asyncio
async def test_mold_detector_clean_when_no_molds_active():
    repo = _make_fake_repo()  # default: molds_active_during returns []
    det = MoldDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# WorkerDetector
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_worker_detector_trips_when_outlier_rate():
    """Worker error rate 60% with phase avg 20% (3× outlier) → hypothesis."""
    repo = _make_fake_repo()
    repo.phase_error_rate.return_value = 0.20
    repo.workers_active_in_phase.return_value = [("w-bad", 10)]
    repo.worker_phase_stats.return_value = WorkerStats(
        worker_id="w-bad", phase_id="LAMINAGEM",
        total_allocations=10, error_count=6,  # 60%
    )

    det = WorkerDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP,
        period_days=7,
        phase_id="LAMINAGEM",
    )
    assert h is not None
    assert h.type == "worker_skill"
    assert h.entity == "w-bad"


@pytest.mark.asyncio
async def test_worker_detector_skips_without_phase_id():
    """Phase-less calls return None — too expensive to scan all phases.
    The cascade caller passes phase_id when known."""
    repo = _make_fake_repo()
    det = WorkerDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is None


@pytest.mark.asyncio
async def test_worker_detector_skips_tiny_sample():
    """Worker with only 2 allocations — too small a sample to flag."""
    repo = _make_fake_repo()
    repo.phase_error_rate.return_value = 0.20
    repo.workers_active_in_phase.return_value = [("w-new", 2)]
    repo.worker_phase_stats.return_value = WorkerStats(
        worker_id="w-new", phase_id="LAMINAGEM",
        total_allocations=2, error_count=2,  # 100% but n=2
    )

    det = WorkerDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP,
        period_days=7,
        phase_id="LAMINAGEM",
    )
    assert h is None


@pytest.mark.asyncio
async def test_worker_detector_skips_within_phase_normal():
    """Worker rate 25% with phase avg 20% (1.25× — below 2× outlier) → clean."""
    repo = _make_fake_repo()
    repo.phase_error_rate.return_value = 0.20
    repo.workers_active_in_phase.return_value = [("w-normal", 20)]
    repo.worker_phase_stats.return_value = WorkerStats(
        worker_id="w-normal", phase_id="LAMINAGEM",
        total_allocations=20, error_count=5,
    )

    det = WorkerDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP,
        period_days=7,
        phase_id="LAMINAGEM",
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# OverloadDetector
# ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_overload_detector_trips_when_wip_high():
    """WIP 600 vs avg 350 → ratio 1.71× (> 1.3 threshold) → hypothesis."""
    repo = _make_fake_repo()
    repo.current_wip.return_value = 600
    repo.avg_wip_during.return_value = 350.0

    det = OverloadDetector(repo)
    h = await det.check(
        trigger=TriggerType.THROUGHPUT_DROP,
        period_days=7, phase_id=None,
    )
    assert h is not None
    assert h.type == "overload"


@pytest.mark.asyncio
async def test_overload_detector_clean_when_wip_normal():
    """WIP 400 vs avg 350 → ratio 1.14× (< 1.3) → clean."""
    repo = _make_fake_repo()
    repo.current_wip.return_value = 400
    repo.avg_wip_during.return_value = 350.0

    det = OverloadDetector(repo)
    h = await det.check(
        trigger=TriggerType.THROUGHPUT_DROP,
        period_days=7, phase_id=None,
    )
    assert h is None


@pytest.mark.asyncio
async def test_overload_detector_skips_when_no_wip_data():
    repo = _make_fake_repo()  # all zeros
    det = OverloadDetector(repo)
    h = await det.check(
        trigger=TriggerType.THROUGHPUT_DROP,
        period_days=7, phase_id=None,
    )
    assert h is None


# ───────────────────────────────────────────────────────────────────────────
# ErroTreeDetector orchestration — uses a fake DB session
# ───────────────────────────────────────────────────────────────────────────


def _make_orchestrator_with_repo(repo):
    """Build an ErroTreeDetector that uses our fake repo by patching
    the repo attr after construction (skips real DB session)."""
    # Bypass __init__ which would try to instantiate a real repo
    detector = ErroTreeDetector.__new__(ErroTreeDetector)
    detector.session = None
    detector.tenant_id = _TENANT
    detector._repo = repo
    detector._detectors = [
        MoldDetector(repo),
        WorkerDetector(repo),
        OverloadDetector(repo),
    ]
    return detector


def _patch_persist(monkeypatch):
    """Stub out the @record_rule_firing persist path so the orchestrator
    runs without a DB."""
    import src.shared.decorators as decorators

    async def _noop_persist(*a, **kw):
        return None

    monkeypatch.setattr(decorators, "_persist_firing", _noop_persist)


@pytest.mark.asyncio
async def test_orchestrator_stops_at_mold_when_trips(monkeypatch):
    _patch_persist(monkeypatch)

    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-7"]
    repo.mold_phase_count.side_effect = [20, 120]
    repo.mold_error_count.side_effect = [6, 12]
    repo.mold_error_types.return_value = Counter({"interior enrugado": 6})

    detector = _make_orchestrator_with_repo(repo)
    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP, period_days=7,
    )

    assert isinstance(result, DiagnosticResult)
    assert result.root_cause is not None
    assert result.root_cause.type == "mold_degradation"
    # Step trace: moldes FOUND, others SKIPPED.
    steps = {s["step"]: s["result"] for s in result.steps_checked}
    assert steps["moldes"] == "FOUND"
    assert steps["operadores"] == "SKIPPED"
    assert steps["sobrecarga"] == "SKIPPED"


@pytest.mark.asyncio
async def test_orchestrator_cascades_when_first_detector_clean(monkeypatch):
    """Mold detector clean → cascade falls through to worker."""
    _patch_persist(monkeypatch)

    repo = _make_fake_repo()
    # Mold: no molds active → clean
    # Worker: outlier
    repo.phase_error_rate.return_value = 0.20
    repo.workers_active_in_phase.return_value = [("w-bad", 10)]
    repo.worker_phase_stats.return_value = WorkerStats(
        worker_id="w-bad", phase_id="LAMINAGEM",
        total_allocations=10, error_count=6,
    )

    detector = _make_orchestrator_with_repo(repo)
    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP,
        period_days=7,
        phase_id="LAMINAGEM",
    )

    assert result.root_cause is not None
    assert result.root_cause.type == "worker_skill"
    steps = {s["step"]: s["result"] for s in result.steps_checked}
    assert steps["moldes"] == "CLEAR"
    assert steps["operadores"] == "FOUND"
    assert steps["sobrecarga"] == "SKIPPED"


@pytest.mark.asyncio
async def test_orchestrator_no_isolated_cause_when_all_clean(monkeypatch):
    _patch_persist(monkeypatch)

    repo = _make_fake_repo()  # all defaults → all clean
    detector = _make_orchestrator_with_repo(repo)
    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP, period_days=7,
    )

    assert result.root_cause is None
    assert any("Nenhuma causa" in line for line in result.chain)
    # All 3 steps marked CLEAR (none SKIPPED, since cascade ran in full).
    steps = {s["step"]: s["result"] for s in result.steps_checked}
    assert steps == {"moldes": "CLEAR", "operadores": "CLEAR", "sobrecarga": "CLEAR"}


@pytest.mark.asyncio
async def test_orchestrator_swallows_detector_exception(monkeypatch):
    """If a detector raises, the cascade logs + continues. No-crash
    guarantee."""
    _patch_persist(monkeypatch)

    repo = _make_fake_repo()
    # Make mold_phase_count blow up to force an exception path inside
    # the mold detector.
    repo.molds_active_during.return_value = ["M-broken"]
    repo.mold_phase_count.side_effect = RuntimeError("DB exploded")

    detector = _make_orchestrator_with_repo(repo)
    # Should not raise.
    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP, period_days=7,
    )
    # Mold detector treated as CLEAR after the exception.
    steps = {s["step"]: s["result"] for s in result.steps_checked}
    assert steps["moldes"] == "CLEAR"


@pytest.mark.asyncio
async def test_orchestrator_returns_recommendation_for_each_hypothesis_type(monkeypatch):
    _patch_persist(monkeypatch)

    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-7"]
    repo.mold_phase_count.side_effect = [20, 120]
    repo.mold_error_count.side_effect = [6, 12]
    repo.mold_error_types.return_value = Counter({"deformação": 6})

    detector = _make_orchestrator_with_repo(repo)
    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP, period_days=7,
    )

    assert result.recommendation is not None
    assert "Manutenção" in result.recommendation["action"]
    # Q.173.I — sem €/horas inventados (invariante #8): a recomendação é
    # qualitativa e declara explicitamente que não há estimativa medida.
    assert "cost_estimate_eur" not in result.recommendation
    assert "downtime_hours" not in result.recommendation
    assert "sem estimativa" in result.recommendation["estimate"]


@pytest.mark.asyncio
async def test_orchestrator_chain_uses_canonical_template(monkeypatch):
    """For mold_degradation the chain should follow the §10.1 NELO
    canonical 5-step path."""
    _patch_persist(monkeypatch)

    repo = _make_fake_repo()
    repo.molds_active_during.return_value = ["M-7"]
    repo.mold_phase_count.side_effect = [20, 120]
    repo.mold_error_count.side_effect = [6, 12]
    repo.mold_error_types.return_value = Counter({"interior enrugado": 6})

    detector = _make_orchestrator_with_repo(repo)
    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP, period_days=7,
    )

    chain_text = " ".join(result.chain)
    assert "Molde" in chain_text
    assert "Laminagem" in chain_text
    assert "Desmolde" in chain_text
    assert "Lixagem" in chain_text or "retrabalho" in chain_text.lower()
