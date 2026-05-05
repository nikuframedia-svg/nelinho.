"""Sprint Q.15.D.0 — types unit tests.

Pin the contract that downstream handlers depend on:
  * Hypothesis.confidence is the Beta posterior mean.
  * credible_interval is in [0, 1] and stays valid for tiny / huge counters.
  * MoldUsage / WorkerStats compute error_rate + helpers correctly.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.explain.diagnostics.types import (
    BoatJourney,
    DiagnosticResult,
    Hypothesis,
    MoldUsage,
    TriggerType,
    WorkerStats,
)


# ───────────────────────────────────────────────────────────────────────────
# Hypothesis
# ───────────────────────────────────────────────────────────────────────────


def test_hypothesis_confidence_is_beta_posterior_mean():
    h = Hypothesis(type="x", entity="e", alpha=8, beta=2, evidence=[])
    assert h.confidence == pytest.approx(0.8)


def test_hypothesis_confidence_balanced_prior():
    """alpha = beta = 1 (uniform prior, no evidence) → 0.5."""
    h = Hypothesis(type="x", entity="e", alpha=1, beta=1, evidence=[])
    assert h.confidence == pytest.approx(0.5)


def test_hypothesis_credible_interval_contains_mean():
    h = Hypothesis(type="x", entity="e", alpha=10, beta=5, evidence=[])
    low, high = h.credible_interval(level=0.95)
    assert 0.0 <= low <= h.confidence <= high <= 1.0


def test_hypothesis_credible_interval_narrows_with_more_evidence():
    sparse = Hypothesis(type="x", entity="e", alpha=2, beta=1, evidence=[])
    dense = Hypothesis(type="x", entity="e", alpha=200, beta=100, evidence=[])
    sparse_lo, sparse_hi = sparse.credible_interval(0.95)
    dense_lo, dense_hi = dense.credible_interval(0.95)
    assert (dense_hi - dense_lo) < (sparse_hi - sparse_lo)


def test_hypothesis_evidence_is_immutable_via_frozen():
    """Hypothesis is frozen — assigning to a field raises."""
    h = Hypothesis(type="x", entity="e", alpha=1, beta=1, evidence=["e1"])
    with pytest.raises(Exception):
        h.alpha = 99  # type: ignore[misc]


# ───────────────────────────────────────────────────────────────────────────
# MoldUsage
# ───────────────────────────────────────────────────────────────────────────


def test_mold_usage_error_rate_computes():
    m = MoldUsage(mold_id="M-7", total_phases=20, error_count=5)
    assert m.error_rate == pytest.approx(0.25)


def test_mold_usage_error_rate_handles_zero_phases():
    """Defensive: divide-by-zero guard returns 0.0, not exception."""
    m = MoldUsage(mold_id="M-empty", total_phases=0, error_count=0)
    assert m.error_rate == 0.0


# ───────────────────────────────────────────────────────────────────────────
# WorkerStats
# ───────────────────────────────────────────────────────────────────────────


def test_worker_stats_error_rate():
    w = WorkerStats(
        worker_id="w-1", phase_id="LAMINAGEM",
        total_allocations=10, error_count=3,
    )
    assert w.error_rate == pytest.approx(0.3)


def test_worker_stats_first_last_seen():
    w = WorkerStats(
        worker_id="w-1", phase_id="x",
        total_allocations=3, error_count=0,
        allocation_dates=[date(2026, 4, 5), date(2026, 5, 1), date(2026, 4, 20)],
    )
    assert w.first_seen == date(2026, 4, 5)
    assert w.last_seen == date(2026, 5, 1)


def test_worker_stats_first_seen_none_when_empty():
    w = WorkerStats(
        worker_id="w-1", phase_id="x",
        total_allocations=0, error_count=0,
    )
    assert w.first_seen is None
    assert w.last_seen is None


# ───────────────────────────────────────────────────────────────────────────
# TriggerType / DiagnosticResult / BoatJourney — shape checks
# ───────────────────────────────────────────────────────────────────────────


def test_trigger_type_values_stable():
    """The string values are persisted in the audit log — renaming
    would break audit history. Pin them explicitly."""
    assert TriggerType.QUALITY_DROP.value == "quality_drop"
    assert TriggerType.THROUGHPUT_DROP.value == "throughput_drop"
    assert TriggerType.DELAY_SPIKE.value == "delay_spike"


def test_diagnostic_result_with_no_root_cause():
    """When all detectors return None, root_cause is None and chain
    contains the 'no isolated cause' narration."""
    r = DiagnosticResult(
        root_cause=None,
        chain=["Nenhuma causa isolada", "Possível combinação"],
        steps_checked=[
            {"step": "moldes", "result": "CLEAR"},
            {"step": "operadores", "result": "CLEAR"},
        ],
        recommendation={"action": "Investigação manual"},
    )
    assert r.root_cause is None


def test_boat_journey_carries_phase_path():
    j = BoatJourney(
        of_id="OF-100",
        phase_ids=["LAMINAGEM", "DESMOLDE", "LIXAGEM"],
        mold_id="M-7",
    )
    assert j.phase_ids == ["LAMINAGEM", "DESMOLDE", "LIXAGEM"]
