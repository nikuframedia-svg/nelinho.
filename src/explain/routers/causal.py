"""Q.66.D.4c — Causal sub-router (extracted from `src.explain.api`).

Hosts the DoWhy-GCM attribution + PCMCI+ discovery endpoints:

* ``GET /v1/explain/attribution``
* ``GET /v1/explain/discover``

Engines (DoWhy, tigramite) are heavy and lazily imported inside the
handlers — keeps router import cheap, mirrors the pre-decomposition
behaviour that the characterization tests depend on (they patch the
engine modules directly, not the router-level import).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/explain", tags=["Explainability"])


# ═══════════════════════════════════════════════════════════════════════════
# Sprint I.3 — DoWhy-GCM attribution endpoint
# ═══════════════════════════════════════════════════════════════════════════


class AttributionNode(BaseModel):
    node: str
    share: float = Field(..., ge=0.0, le=1.0)
    direction: str
    absolute: float


class AttributionResponse(BaseModel):
    target: str
    status: str                            # ok / degraded / unavailable
    reason: Optional[str] = None
    engine: str
    sample_size: int
    baseline_mean: Optional[float] = None
    target_value: Optional[float] = None
    ranked: List[AttributionNode] = Field(default_factory=list)


@router.get("/attribution", response_model=AttributionResponse)
async def causal_attribution(
    target: str = Query(..., description="NELO_DAG node id, e.g. throughput_eur_day"),
    sample_size: int = Query(200, ge=50, le=2000),
    seed: int = Query(42, ge=0),
):
    """Return per-node contributions to the target's variance.

    Uses DoWhy-GCM's ``intrinsic_causal_influence`` on the NELO_DAG
    ancestors of ``target``. When DoWhy can't be imported (dev
    machine without the heavy deps) the response is
    ``status="unavailable"`` with a reason — the UI can fall back to
    the CausalChain narrative.

    For Sprint I.3 the sample is simulated from the DAG's functional
    forms (``status="degraded"``) because we don't have enough
    production telemetry yet. Sprint G + 3 months of real data will
    flip this to ``status="ok"`` without changing the endpoint.
    """
    from src.copilot.causal.attribution import attribution_analysis

    report = attribution_analysis(
        target=target, sample_size=sample_size, seed=seed,
    )
    return AttributionResponse(
        target=report.target,
        status=report.status,
        reason=report.reason,
        engine=report.engine,
        sample_size=report.sample_size,
        baseline_mean=report.baseline_mean,
        target_value=report.target_value,
        ranked=[AttributionNode(**a.__dict__) for a in report.ranked],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Sprint I.4 — PCMCI+ causal discovery endpoint
# ═══════════════════════════════════════════════════════════════════════════


class DiscoveredEdgeResponse(BaseModel):
    src: str
    dst: str
    lag: int
    strength: float
    pvalue: float
    is_new: bool
    direction: str


class DiscoveryResponse(BaseModel):
    status: str                               # ok / degraded / unavailable
    reason: Optional[str] = None
    engine: str
    sample_size: int
    tau_max: int
    nodes_examined: int
    candidate_edges: List[DiscoveredEdgeResponse] = Field(default_factory=list)


@router.get("/discover", response_model=DiscoveryResponse)
async def causal_discover(
    tau_max: int = Query(2, ge=0, le=5),
    alpha: float = Query(0.05, gt=0.0, lt=0.5),
    sample_size: int = Query(300, ge=50, le=5000),
    seed: int = Query(17, ge=0),
    restrict_to: Optional[str] = Query(
        default=None,
        description="Optional comma-separated list of DAG node ids to limit the scan.",
    ),
):
    """Run PCMCI+ over a time series and propose new DAG edges.

    The ``is_new`` flag tells ``/admin/causal-discoveries`` which
    edges extend :data:`NELO_DAG` vs. which merely confirm it. Only
    ``is_new`` rows need human review; the rest are a confidence
    signal for the existing graph.

    Like the attribution endpoint, this will run on simulated data
    (``status="degraded"``) until Sprint G+I produces enough real
    telemetry to feed the series directly.
    """
    from src.copilot.causal.discovery import discover_edges

    restrict_list: Optional[List[str]] = None
    if restrict_to:
        restrict_list = [s.strip() for s in restrict_to.split(",") if s.strip()]

    report = discover_edges(
        tau_max=tau_max,
        alpha=alpha,
        sample_size=sample_size,
        seed=seed,
        restrict_to=restrict_list,
    )
    return DiscoveryResponse(
        status=report.status,
        reason=report.reason,
        engine=report.engine,
        sample_size=report.sample_size,
        tau_max=report.tau_max,
        nodes_examined=report.nodes_examined,
        candidate_edges=[
            DiscoveredEdgeResponse(**edge.to_json())
            for edge in report.candidate_edges
        ],
    )
