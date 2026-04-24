"""
ProdPlan ONE — Causal attribution (Sprint I.3)
================================================

Wraps DoWhy-GCM's ``intrinsic_causal_influence`` so the Copilot can
answer questions like:

    "Porque desceu o throughput €/dia esta semana?"

The Blueprint v2.0 §28 target: produce a dict `{node: share_of_delta}`
that attributes each DAG node's contribution to the movement in a
target KPI between a baseline period and a recent period.

Data contract
-------------
``attribution_analysis(target, ...)`` expects either:

* A fully-parameterised :class:`pandas.DataFrame` with one row per
  observation (day / hour / commit). Columns must match NELO_DAG
  node ids.
* OR nothing — we fall back to a synthetic sample generated from the
  NELO_DAG functional forms with small Gaussian perturbations. That
  mode is useful for dev + for the first time the endpoint is called
  before observations accumulate.

Graceful degradation
--------------------
``dowhy`` is a heavy C-extension dep (numba, cvxpy). The Nelo on-prem
box installs it but a dev environment may not. When the import fails
at runtime, we return a ``"attribution_unavailable"`` payload with
the reason, so the caller can fall back to the Aristotle narrative.

The module itself imports ``dowhy`` lazily inside the function so
importing ``src.copilot.causal`` doesn't require dowhy to be present.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.copilot.causal.nelo_dag import (
    ALL_NODES,
    NODES_BY_ID,
    NodeCategory,
    causal_query,
    topological_order,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Response shape
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class NodeAttribution:
    """Contribution of one upstream node to the target's movement."""
    node: str
    share: float           # [0..1], the fraction of variance this node explains
    direction: str         # "positive" / "negative" / "neutral"
    absolute: float        # |contribution| in target's units, for ranking


@dataclass
class AttributionReport:
    target: str
    status: str                     # "ok", "degraded", "unavailable"
    reason: Optional[str] = None
    ranked: List[NodeAttribution] = field(default_factory=list)
    baseline_mean: Optional[float] = None
    target_value: Optional[float] = None
    sample_size: int = 0
    engine: str = "dowhy-gcm"

    def to_json(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "status": self.status,
            "reason": self.reason,
            "ranked": [
                {
                    "node": a.node,
                    "share": a.share,
                    "direction": a.direction,
                    "absolute": a.absolute,
                }
                for a in self.ranked
            ],
            "baseline_mean": self.baseline_mean,
            "target_value": self.target_value,
            "sample_size": self.sample_size,
            "engine": self.engine,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Main entry
# ═══════════════════════════════════════════════════════════════════════════


def attribution_analysis(
    target: str,
    *,
    observations: Optional[Any] = None,    # pandas.DataFrame or None
    sample_size: int = 200,
    seed: int = 42,
) -> AttributionReport:
    """Return per-node shares of the explained variance in ``target``.

    Parameters
    ----------
    target:
        Target node id (must exist in NELO_DAG).
    observations:
        Optional DataFrame with one column per node. If omitted, the
        function simulates from the NELO_DAG functional forms —
        enough to satisfy DoWhy's API + to prove the pipeline works
        before real telemetry accumulates.
    sample_size:
        Number of synthetic rows when ``observations`` is None.
    seed:
        RNG seed for reproducibility.
    """
    if target not in NODES_BY_ID:
        return AttributionReport(
            target=target,
            status="unavailable",
            reason=f"unknown target node '{target}'",
        )

    # Lazy import so the rest of the causal package doesn't demand
    # DoWhy at import time.
    try:
        import numpy as np
        import pandas as pd
        import networkx as nx
        from dowhy import gcm
    except Exception as exc:  # pragma: no cover — degraded env
        logger.warning("attribution_analysis: dowhy import failed: %s", exc)
        return AttributionReport(
            target=target,
            status="unavailable",
            reason=f"dowhy not importable: {exc}",
        )

    # Build the sample.
    if observations is None:
        df = _simulate_dataset(sample_size=sample_size, seed=seed)
        report_status = "degraded"
        report_reason = "simulated data — live observations not yet wired"
    else:
        df = observations
        report_status = "ok"
        report_reason = None

    # Ensure the target column exists in the frame.
    if target not in df.columns:
        return AttributionReport(
            target=target,
            status="unavailable",
            reason=f"target {target!r} missing from observations",
            sample_size=len(df),
        )

    # Build the DoWhy causal model from NELO_DAG.
    graph = _build_nx_graph(target)
    if graph.number_of_nodes() == 0:
        return AttributionReport(
            target=target,
            status="unavailable",
            reason=f"no ancestors of {target} in DAG",
            sample_size=len(df),
        )

    scm = gcm.StructuralCausalModel(graph)
    # Auto-assign additive-noise models per node (works for continuous data).
    gcm.auto.assign_causal_mechanisms(scm, df)

    try:
        gcm.fit(scm, df)
    except Exception as exc:  # pragma: no cover — fit instability
        logger.warning("attribution_analysis: gcm.fit failed: %s", exc)
        return AttributionReport(
            target=target,
            status="unavailable",
            reason=f"gcm.fit failed: {exc}",
            sample_size=len(df),
        )

    try:
        contributions = gcm.intrinsic_causal_influence(
            scm, target_node=target, num_samples_randomization=max(50, sample_size // 2),
        )
    except Exception as exc:  # pragma: no cover — numerical
        logger.warning(
            "attribution_analysis: intrinsic_causal_influence failed: %s", exc,
        )
        return AttributionReport(
            target=target,
            status="unavailable",
            reason=f"intrinsic_causal_influence failed: {exc}",
            sample_size=len(df),
        )

    total = sum(abs(v) for v in contributions.values()) or 1.0
    ranked: List[NodeAttribution] = []
    for node_id, value in contributions.items():
        if node_id == target:
            continue
        share = abs(value) / total
        direction = (
            "positive" if value > 1e-9
            else "negative" if value < -1e-9
            else "neutral"
        )
        ranked.append(NodeAttribution(
            node=node_id,
            share=round(share, 4),
            direction=direction,
            absolute=round(float(value), 4),
        ))

    ranked.sort(key=lambda a: a.share, reverse=True)

    return AttributionReport(
        target=target,
        status=report_status,
        reason=report_reason,
        ranked=ranked,
        baseline_mean=float(df[target].mean()),
        target_value=float(df[target].iloc[-1]),
        sample_size=int(len(df)),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _build_nx_graph(target: str):
    """Build a directed NetworkX graph over the ancestors of ``target``.

    We restrict to upstream nodes so DoWhy doesn't burn cycles on
    unrelated parts of the DAG when the user asks about a single KPI.
    """
    import networkx as nx

    g = nx.DiGraph()
    # Walk ancestors + target itself.
    from src.copilot.causal.nelo_dag import ancestors_of

    nodes = ancestors_of(target) | {target}
    for node_id in nodes:
        g.add_node(node_id)
    for node_id in nodes:
        for parent in NODES_BY_ID[node_id].parents:
            if parent in nodes:
                g.add_edge(parent, node_id)
    return g


def _simulate_dataset(*, sample_size: int, seed: int):
    """Generate a synthetic dataset by forward-propagating each node
    through the NELO_DAG functional forms with additive Gaussian noise.

    Coefficient magnitudes match the baselines; noise is ~5 % of the
    baseline so the signal dominates but there's enough variance for
    DoWhy's structural models to fit.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    order = topological_order()
    columns: Dict[str, Any] = {}

    for node_id in order:
        node = NODES_BY_ID[node_id]
        baseline = float(node.baseline)
        noise_scale = max(abs(baseline) * 0.05, 1e-3)

        if node.category in (NodeCategory.INPUT, NodeCategory.CONFOUNDER):
            # Sample inputs / confounders as IID baseline + noise.
            columns[node_id] = baseline + rng.normal(0, noise_scale, size=sample_size)
            continue

        # For derived nodes, compute from the parent columns using the
        # same functional form `causal_query` uses. We simulate per-row.
        from src.copilot.causal.nelo_dag import _FUNCTIONS  # re-use

        fn = _FUNCTIONS.get(node_id)
        if fn is None:
            columns[node_id] = np.full(sample_size, baseline) + rng.normal(
                0, noise_scale, size=sample_size,
            )
            continue

        parent_ids = list(node.parents)
        parent_matrix = np.column_stack(
            [columns[p] for p in parent_ids]
        ) if parent_ids else np.zeros((sample_size, 0))
        values = np.empty(sample_size)
        for i in range(sample_size):
            row_parents = {
                pid: float(parent_matrix[i, j]) for j, pid in enumerate(parent_ids)
            }
            try:
                values[i] = float(fn(row_parents))
            except Exception:
                values[i] = baseline
        values = values + rng.normal(0, noise_scale, size=sample_size)
        columns[node_id] = values

    return pd.DataFrame(columns)


__all__ = [
    "AttributionReport",
    "NodeAttribution",
    "attribution_analysis",
]
