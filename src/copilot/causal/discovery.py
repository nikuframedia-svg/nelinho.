"""
ProdPlan ONE — Causal discovery (Sprint I.4, PCMCI+)
======================================================

Blueprint v2.0 §29 — weekly pass over the factory time series to
*propose* new directed edges for :data:`NELO_DAG`. This is NOT an
autonomous editor. Every candidate edge goes through
``/admin/causal-discoveries`` for human review before it changes the
SCM: the `PreferenceRule` pattern, applied to the DAG itself.

Why a human-in-the-loop
-----------------------
PCMCI+ infers conditional independences from lagged time series
(Runge 2020). It is a statistical procedure — confident edges on
real data are likely real, but confounders we haven't named yet can
fabricate edges. Signing them off keeps the DAG an engineering
artefact, not a stats lottery.

Data contract
-------------
``discover_edges`` consumes a ``pandas.DataFrame`` whose columns are
NELO_DAG node ids and whose rows are time-indexed observations. The
index order is the temporal order; lag depth ``tau_max`` is a caller
knob.

Graceful degradation
--------------------
``tigramite`` is a heavy numerical stack. When the import fails, the
module returns a ``DiscoveryReport(status="unavailable", ...)``.
Imports are lazy so just touching the module doesn't pay the cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.copilot.causal.nelo_dag import (
    ALL_NODES,
    NODES_BY_ID,
    edge_exists,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Response shape
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class DiscoveredEdge:
    """One proposed addition / confirmation of a DAG edge."""
    src: str
    dst: str
    lag: int                      # 0 = contemporaneous, >0 = time-lagged
    strength: float               # partial-correlation magnitude
    pvalue: float
    is_new: bool                  # True if NELO_DAG doesn't already contain it
    direction: str                # "positive" / "negative"

    def to_json(self) -> Dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "lag": self.lag,
            "strength": round(self.strength, 4),
            "pvalue": round(self.pvalue, 6),
            "is_new": self.is_new,
            "direction": self.direction,
        }


@dataclass
class DiscoveryReport:
    status: str                          # "ok" / "degraded" / "unavailable"
    reason: Optional[str] = None
    engine: str = "tigramite-pcmci+"
    sample_size: int = 0
    tau_max: int = 0
    nodes_examined: int = 0
    candidate_edges: List[DiscoveredEdge] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "engine": self.engine,
            "sample_size": self.sample_size,
            "tau_max": self.tau_max,
            "nodes_examined": self.nodes_examined,
            "candidate_edges": [e.to_json() for e in self.candidate_edges],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════════════════════════


def discover_edges(
    series: Any = None,                      # pandas.DataFrame or None → simulate
    *,
    tau_max: int = 2,
    alpha: float = 0.05,
    restrict_to: Optional[List[str]] = None,
    sample_size: int = 200,
    seed: int = 17,
) -> DiscoveryReport:
    """Run PCMCI+ on a time series and return edge candidates.

    Parameters
    ----------
    series:
        ``pandas.DataFrame`` with one column per NELO_DAG node and one
        row per time step. ``None`` → synthesise from the DAG's
        functional forms (``status="degraded"``).
    tau_max:
        Maximum lag to consider. ``2`` works for hourly / daily
        schedule data on the NELO scale.
    alpha:
        Significance threshold — edges with p-values ≥ alpha are
        dropped. ``0.05`` is the PCMCI default.
    restrict_to:
        Optional whitelist of node ids. Helpful when the caller only
        wants discovery on a subset (e.g. quality-related nodes).
    sample_size:
        Number of synthetic rows when ``series`` is None.
    seed:
        RNG seed — applied both to the simulator and to tigramite's
        internal random state.
    """
    # Lazy imports — keep the rest of the package usable on boxes
    # without tigramite.
    try:
        import numpy as np
        import pandas as pd
        from tigramite.independence_tests.parcorr import ParCorr
        from tigramite.pcmci import PCMCI
        from tigramite import data_processing as pp
    except Exception as exc:  # pragma: no cover — missing dep
        logger.warning("discover_edges: tigramite import failed: %s", exc)
        return DiscoveryReport(
            status="unavailable",
            reason=f"tigramite not importable: {exc}",
        )

    # Materialise a frame.
    if series is None:
        df = _simulate_series(
            sample_size=sample_size, seed=seed, restrict_to=restrict_to,
        )
        status = "degraded"
        reason = "simulated series — plug in real telemetry once Sprint G lands"
    else:
        df = series
        if restrict_to:
            df = df[[c for c in restrict_to if c in df.columns]]
        status = "ok"
        reason = None

    if df.shape[1] < 2:
        return DiscoveryReport(
            status="unavailable",
            reason=f"need ≥ 2 columns for PCMCI, got {df.shape[1]}",
            sample_size=int(df.shape[0]),
        )
    if df.shape[0] <= tau_max + 10:
        return DiscoveryReport(
            status="unavailable",
            reason=f"series too short ({df.shape[0]} rows) for tau_max={tau_max}",
            sample_size=int(df.shape[0]),
            tau_max=tau_max,
        )

    # Build tigramite dataframe.
    var_names = list(df.columns)
    data_array = df.to_numpy(dtype=float)
    dataframe = pp.DataFrame(
        data_array,
        var_names=var_names,
        datatime={0: np.arange(len(data_array))},
    )

    pcmci = PCMCI(dataframe=dataframe, cond_ind_test=ParCorr())
    # `run_pcmciplus` is the contemporaneous + lagged variant (Runge 2020).
    try:
        results = pcmci.run_pcmciplus(
            tau_min=0, tau_max=tau_max, pc_alpha=alpha,
        )
    except Exception as exc:  # pragma: no cover — numerical failure
        logger.warning("discover_edges: PCMCI+ failed: %s", exc)
        return DiscoveryReport(
            status="unavailable",
            reason=f"PCMCI+ failed: {exc}",
            sample_size=int(df.shape[0]),
            tau_max=tau_max,
        )

    p_matrix = results["p_matrix"]        # shape (N, N, tau_max+1)
    val_matrix = results["val_matrix"]    # same shape

    candidates: List[DiscoveredEdge] = []
    n_vars = len(var_names)
    for i in range(n_vars):
        for j in range(n_vars):
            if i == j:
                continue
            for lag in range(tau_max + 1):
                p = float(p_matrix[i, j, lag])
                if p >= alpha:
                    continue
                strength = float(val_matrix[i, j, lag])
                if abs(strength) < 1e-6:
                    continue
                src = var_names[i]
                dst = var_names[j]
                is_new = not edge_exists(src, dst, transitive=False)
                candidates.append(DiscoveredEdge(
                    src=src,
                    dst=dst,
                    lag=lag,
                    strength=abs(strength),
                    pvalue=p,
                    is_new=is_new,
                    direction=("positive" if strength > 0 else "negative"),
                ))

    candidates.sort(key=lambda c: (not c.is_new, -c.strength))

    return DiscoveryReport(
        status=status,
        reason=reason,
        sample_size=int(df.shape[0]),
        tau_max=tau_max,
        nodes_examined=n_vars,
        candidate_edges=candidates,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Simulator — shared with attribution.py but simpler (time-series flavour)
# ═══════════════════════════════════════════════════════════════════════════


def _simulate_series(
    *,
    sample_size: int,
    seed: int,
    restrict_to: Optional[List[str]] = None,
):
    """Generate a simulated multivariate time series by running the
    NELO_DAG forward with autocorrelated noise on inputs.

    Not a physics simulation — just enough structure for PCMCI+ to
    surface plausible edges.
    """
    import numpy as np
    import pandas as pd

    from src.copilot.causal.nelo_dag import _FUNCTIONS, topological_order

    rng = np.random.default_rng(seed)
    order = topological_order()
    allowed = set(restrict_to) if restrict_to else set(n.id for n in ALL_NODES)

    columns: Dict[str, Any] = {}
    for node_id in order:
        if node_id not in allowed:
            continue
        node = NODES_BY_ID[node_id]
        baseline = float(node.baseline)
        noise = max(abs(baseline) * 0.03, 1e-3)
        if not node.parents:
            # Random-walk-ish autocorrelated column.
            noise_steps = rng.normal(0, noise, size=sample_size)
            column = np.cumsum(noise_steps) * 0.1 + baseline
            columns[node_id] = column
            continue

        parent_ids = list(node.parents)
        fn = _FUNCTIONS.get(node_id)
        if fn is None:
            columns[node_id] = np.full(sample_size, baseline) + rng.normal(
                0, noise, size=sample_size,
            )
            continue
        values = np.empty(sample_size)
        for t in range(sample_size):
            row_parents = {
                p: float(columns.get(p, [baseline] * sample_size)[t])
                for p in parent_ids
            }
            try:
                values[t] = float(fn(row_parents)) + rng.normal(0, noise)
            except Exception:
                values[t] = baseline
        columns[node_id] = values

    return pd.DataFrame(columns)


__all__ = [
    "DiscoveredEdge",
    "DiscoveryReport",
    "discover_edges",
]
