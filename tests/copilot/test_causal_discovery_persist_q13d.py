"""Sprint Q.13.D D.2 — `persist_discovery_report` test.

The discovery side of Camada 4 hinges on PCMCI+ output landing in
``governance.causal_discovery_report`` so an operator can review it
before any edge touches the SCM (`NELO_DAG`). Without these tests,
a future refactor could:

  * Persist with the wrong shape (e.g. drop `candidate_edges`).
  * Skip the review-status default (rows would auto-promote silently).
  * Swallow the run reason (operators lose the "why unavailable?" hint).
  * Break the production guard in `discover_edges`: passing
    ``series=None`` in production must still return
    ``status="unavailable"`` — a circular self-validation against the
    simulator is the bug the production guard exists to prevent.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from src.copilot.causal.discovery import (
    DiscoveredEdge,
    DiscoveryReport,
    discover_edges,
    persist_discovery_report,
)
from src.governance.models import (
    CausalDiscoveryReport,
    CausalDiscoveryStatus,
)


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _FakeSession:
    """Tiny `AsyncSession` stand-in: only `add(...)` is exercised."""

    def __init__(self) -> None:
        self.staged: list = []

    def add(self, instance: Any) -> None:
        self.staged.append(instance)


@pytest.mark.asyncio
async def test_persist_discovery_report_round_trip():
    """A representative `DiscoveryReport` materialises into a typed
    ORM row whose columns mirror the dataclass field-by-field."""
    edges = [
        DiscoveredEdge(
            src="mold_age", dst="mold_setup_time", lag=1,
            strength=0.42, pvalue=0.0021, is_new=True, direction="positive",
        ),
        DiscoveredEdge(
            src="operator_skill", dst="quality_risk", lag=0,
            strength=0.28, pvalue=0.013, is_new=False, direction="negative",
        ),
    ]
    report = DiscoveryReport(
        status="ok",
        reason=None,
        engine="tigramite-pcmci+",
        sample_size=512,
        tau_max=2,
        nodes_examined=27,
        candidate_edges=edges,
    )
    session = _FakeSession()
    row = await persist_discovery_report(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        report=report,
    )
    assert isinstance(row, CausalDiscoveryReport)
    assert row.tenant_id == _TENANT
    assert row.run_status == "ok"
    assert row.engine == "tigramite-pcmci+"
    assert row.sample_size == 512
    assert row.tau_max == 2
    assert row.nodes_examined == 27
    assert row.review_status == CausalDiscoveryStatus.PENDING.value
    # JSONB list mirrors the dataclass `to_json()` output.
    assert isinstance(row.candidate_edges, list)
    assert len(row.candidate_edges) == 2
    first = row.candidate_edges[0]
    assert first["src"] == "mold_age"
    assert first["dst"] == "mold_setup_time"
    assert first["is_new"] is True
    assert first["direction"] == "positive"
    # The session captured the staged row.
    assert session.staged == [row]


@pytest.mark.asyncio
async def test_persist_discovery_report_unavailable_carries_reason():
    """When PCMCI+ couldn't run (missing dep, no telemetry), the reason
    must survive into the audit row so operators see *why* the daily
    log line says "0 candidates"."""
    report = DiscoveryReport(
        status="unavailable",
        reason="tigramite not importable: ModuleNotFoundError(...)",
        sample_size=0,
        tau_max=0,
        nodes_examined=0,
        candidate_edges=[],
    )
    session = _FakeSession()
    row = await persist_discovery_report(
        session=session,  # type: ignore[arg-type]
        tenant_id=_TENANT,
        report=report,
    )
    assert row.run_status == "unavailable"
    assert row.reason and "tigramite" in row.reason
    assert row.candidate_edges == []
    assert row.review_status == CausalDiscoveryStatus.PENDING.value


def test_discover_edges_refuses_synthetic_without_opt_in():
    """Sprint Q.12 Onda 4.1 — production must NEVER discover edges from
    data we just simulated. The default ``allow_synthetic=False``
    surface returns `unavailable` even off-prod."""
    report = discover_edges(series=None)  # no series, no opt-in
    assert report.status == "unavailable"
    assert report.reason and "allow_synthetic" in report.reason
    assert report.candidate_edges == []
