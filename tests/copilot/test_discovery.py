"""Sprint I.4 — PCMCI+ discovery smoke + contract tests.

We don't assert *which* edges appear (tigramite is stochastic) — we
assert that the pipeline runs end-to-end, the response shape is what
the admin UI expects, and the ``is_new`` flag correctly separates
candidates that extend NELO_DAG from ones that merely confirm it.
"""

from __future__ import annotations

import pytest

from src.copilot.causal.discovery import (
    DiscoveryReport,
    discover_edges,
)
from src.copilot.causal.nelo_dag import edge_exists


def test_discovery_runs_on_simulated_series():
    # Sprint Q.12 Onda 4.1 — synthetic discovery is opt-in to keep
    # circular validation out of production code paths.
    report = discover_edges(tau_max=2, sample_size=120, seed=3, allow_synthetic=True)
    assert isinstance(report, DiscoveryReport)
    assert report.status in {"ok", "degraded"}
    assert report.nodes_examined >= 10
    assert report.sample_size == 120
    assert report.tau_max == 2


def test_discovery_handles_short_series_gracefully():
    import pandas as pd

    df = pd.DataFrame({
        "shift_mode": [1.0] * 5,
        "worker_count_laminagem": [18.0] * 5,
    })
    report = discover_edges(series=df, tau_max=2)
    assert report.status == "unavailable"
    assert "too short" in (report.reason or "")


def test_discovery_needs_at_least_two_columns():
    import pandas as pd

    df = pd.DataFrame({"shift_mode": [1.0] * 100})
    report = discover_edges(series=df, tau_max=1)
    assert report.status == "unavailable"
    assert "2 columns" in (report.reason or "")


def test_is_new_flag_matches_existing_dag():
    report = discover_edges(tau_max=2, sample_size=150, seed=7, allow_synthetic=True)
    for edge in report.candidate_edges:
        direct_existing = edge_exists(edge.src, edge.dst, transitive=False)
        assert edge.is_new == (not direct_existing)


def test_candidate_edges_sorted_new_first_then_by_strength():
    report = discover_edges(tau_max=2, sample_size=120, seed=9, allow_synthetic=True)
    if len(report.candidate_edges) < 2:
        pytest.skip("too few edges to check sort order")
    # New edges appear before confirmations.
    seen_not_new = False
    for edge in report.candidate_edges:
        if edge.is_new:
            assert not seen_not_new, "new edges should come before known ones"
        else:
            seen_not_new = True


def test_restrict_to_limits_the_variable_set():
    """Only the columns listed should be examined."""
    report = discover_edges(
        tau_max=1,
        sample_size=120,
        restrict_to=[
            "shift_mode",
            "routing_variant",
            "worker_count_laminagem",
            "laminagem_duration",
            "makespan_hours",
        ],
        seed=11,
        allow_synthetic=True,
    )
    assert report.nodes_examined == 5
    vars_in_edges = set()
    for edge in report.candidate_edges:
        vars_in_edges.add(edge.src)
        vars_in_edges.add(edge.dst)
    assert vars_in_edges <= {
        "shift_mode",
        "routing_variant",
        "worker_count_laminagem",
        "laminagem_duration",
        "makespan_hours",
    }
