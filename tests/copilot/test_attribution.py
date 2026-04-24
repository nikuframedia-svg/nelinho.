"""Sprint I.3 — attribution_analysis smoke + contract tests.

These exercise the DoWhy-GCM pipeline end-to-end with a small seed
so they run in CI budget. We assert:

* Unknown target → status ``unavailable`` with reason.
* Well-known target with the simulated dataset → status ``degraded``,
  ranked list of contributions (non-empty), shares sum to ≤ 1.0.
* Ranked list is ordered by share, descending.

We do NOT assert specific numerical rankings — DoWhy uses stochastic
methods under the hood and noise makes strict equality brittle.
"""

from __future__ import annotations

import pytest

from src.copilot.causal.attribution import (
    AttributionReport,
    attribution_analysis,
)


def test_unknown_target_is_handled_cleanly():
    report = attribution_analysis("does-not-exist")
    assert isinstance(report, AttributionReport)
    assert report.status == "unavailable"
    assert report.reason and "unknown target" in report.reason
    assert report.ranked == []


def test_attribution_ranks_upstream_nodes_for_throughput():
    report = attribution_analysis(
        "throughput_eur_day", sample_size=120, seed=11,
    )
    # Either 'ok' (future: real data) or 'degraded' (now: simulated).
    assert report.status in {"ok", "degraded"}
    assert report.sample_size == 120
    assert len(report.ranked) > 0

    shares = [a.share for a in report.ranked]
    assert all(0.0 <= s <= 1.0 for s in shares)
    assert sum(shares) <= 1.0 + 1e-6

    # Sorted by share, descending.
    assert shares == sorted(shares, reverse=True)

    # None of the ranked entries are the target itself (that would be
    # a tautology; the adapter strips it).
    assert all(a.node != "throughput_eur_day" for a in report.ranked)


def test_attribution_works_for_makespan():
    report = attribution_analysis(
        "makespan_hours", sample_size=100, seed=23,
    )
    assert report.status in {"ok", "degraded"}
    assert len(report.ranked) >= 3
    # Each row has a direction tag from the expected vocab.
    assert all(a.direction in {"positive", "negative", "neutral"} for a in report.ranked)


def test_attribution_handles_leaf_with_no_ancestors():
    """Picking a root node (shift_mode) yields an empty graph for
    DoWhy — we expect an ``unavailable`` status, not a traceback."""
    report = attribution_analysis("shift_mode", sample_size=80)
    # Either reported as unavailable (no ancestors) or degraded with
    # an empty ranking — both are acceptable, just never a crash.
    if report.status == "unavailable":
        assert report.reason
    else:
        assert report.ranked == [] or all(
            a.node != "shift_mode" for a in report.ranked
        )
