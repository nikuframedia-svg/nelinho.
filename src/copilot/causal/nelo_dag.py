"""
ProdPlan ONE — NELO_DAG (Sprint F.1)
======================================

A structural causal model (SCM) of the NELO factory, expressed as a
Python directed acyclic graph. The DAG is the substrate Sprint F
reasoning sits on: the LLM can ask "what happens to ``throughput_
eur_day`` if I set ``routing`` to B?" and the SCM answers by
propagating the intervention through the graph's functional form.

Design choices
--------------
* **Pure Python** — no tigramite / DoWhy / pgmpy. Those land in Sprint I
  once we have ≥3 months of real data. For today, hand-coded lambdas
  give us auditable, unit-testable, deterministic causal reasoning.
* **22 nodes + 3 confounders**, matching the Blueprint v2.0 §24 target.
  Nodes fall into six buckets:
    - **inputs**       — operator-facing knobs (shift_mode, routing, …)
    - **process_time** — how long each phase takes
    - **process_flow** — phase start times (cascade)
    - **quality**      — risk/rework indicators
    - **outputs**      — KPIs the CEO cares about
    - **confounders**  — unobserved-but-modelled causes
      (operator_experience, mold_age, external_temperature)
* **Every edge is a lambda** accepting the parent values it needs. The
  helper :func:`causal_query` walks from an intervention (``do(x=v)``)
  forward to a target node, applying each lambda in topological order.
  Missing parents fall back to baseline values so the DAG is
  interrogable with partial evidence — the LLM can ask "what if
  routing=B and everything else is typical?" without filling 20
  fields.

The file is intentionally dense with constants rather than reading
from the DB. Baselines are copied from the NELO curated sample
(median rows, 2024 H2). A tenant that diverges materially will see
it in the Sprint I PCMCI+ discovery job before this file rots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════
# Node catalogue
# ═══════════════════════════════════════════════════════════════════════════


class NodeCategory(str, Enum):
    INPUT = "input"
    PROCESS_TIME = "process_time"
    PROCESS_FLOW = "process_flow"
    QUALITY = "quality"
    OUTPUT = "output"
    CONFOUNDER = "confounder"


@dataclass(frozen=True)
class CausalNode:
    """A single node in the NELO SCM.

    ``baseline`` is the typical value used when the node is missing
    from the evidence dict (the LLM forgot to mention it, or it's an
    unobserved confounder). ``parents`` lists the node ids the
    functional form depends on — the DAG-consistency check in F.2
    reads this list.
    """
    id: str
    category: NodeCategory
    description: str
    unit: str
    baseline: float
    parents: Tuple[str, ...] = ()


# ─── Confounders (unobserved — fixed baselines) ──────────────────────────

_CONFOUNDERS: Tuple[CausalNode, ...] = (
    CausalNode(
        id="operator_experience",
        category=NodeCategory.CONFOUNDER,
        description="Median years of factory experience across active workers.",
        unit="years",
        baseline=8.0,
    ),
    CausalNode(
        id="mold_age",
        category=NodeCategory.CONFOUNDER,
        description="Fleet-weighted mean age of in-use moulds.",
        unit="years",
        baseline=3.5,
    ),
    CausalNode(
        id="external_temperature",
        category=NodeCategory.CONFOUNDER,
        description="Ambient temperature affecting resin cure time.",
        unit="celsius",
        baseline=19.0,
    ),
)


# ─── Input knobs ─────────────────────────────────────────────────────────

_INPUTS: Tuple[CausalNode, ...] = (
    CausalNode(
        id="shift_mode",
        category=NodeCategory.INPUT,
        description="1 = single shift (8h); 2 = double shift (16h).",
        unit="shifts",
        baseline=1.0,
    ),
    CausalNode(
        id="routing_variant",
        category=NodeCategory.INPUT,
        description="0 = primary template; 1 = alternative route (B).",
        unit="enum",
        baseline=0.0,
    ),
    CausalNode(
        id="worker_count_laminagem",
        category=NodeCategory.INPUT,
        description="Crew size on the Laminagem line.",
        unit="workers",
        baseline=18.0,
    ),
    CausalNode(
        id="worker_count_pintura",
        category=NodeCategory.INPUT,
        description="Crew size on the Pintura line.",
        unit="workers",
        baseline=6.0,
    ),
    CausalNode(
        id="mold_availability_pct",
        category=NodeCategory.INPUT,
        description="Fraction of the mould fleet currently production-ready.",
        unit="0..1",
        baseline=0.85,
    ),
    CausalNode(
        id="material_availability_pct",
        category=NodeCategory.INPUT,
        description="Fraction of the BOM covered by on-hand + in-transit stock.",
        unit="0..1",
        baseline=0.92,
    ),
)


# ─── Process timings (hours per average op) ──────────────────────────────

_PROCESS_TIMES: Tuple[CausalNode, ...] = (
    CausalNode(
        id="mold_setup_time",
        category=NodeCategory.PROCESS_TIME,
        description="Mean setup time before a laminagem op starts.",
        unit="hours",
        baseline=0.75,
        parents=("mold_age", "mold_availability_pct"),
    ),
    CausalNode(
        id="laminagem_duration",
        category=NodeCategory.PROCESS_TIME,
        description="Mean duration of a laminagem op end-to-end.",
        unit="hours",
        baseline=4.0,
        parents=("worker_count_laminagem", "operator_experience", "routing_variant"),
    ),
    CausalNode(
        id="curing_time",
        category=NodeCategory.PROCESS_TIME,
        description="Resin cure waiting time before desmolde.",
        unit="hours",
        baseline=15.0,
        parents=("external_temperature",),
    ),
    CausalNode(
        id="desmolde_qc_time",
        category=NodeCategory.PROCESS_TIME,
        description="Inspection time on demould.",
        unit="hours",
        baseline=0.5,
        parents=("operator_experience",),
    ),
    CausalNode(
        id="pintura_duration",
        category=NodeCategory.PROCESS_TIME,
        description="Mean paint cycle duration per op.",
        unit="hours",
        baseline=3.5,
        parents=("worker_count_pintura", "routing_variant"),
    ),
)


# ─── Flow (queue / bottleneck indicators) ────────────────────────────────

_PROCESS_FLOW: Tuple[CausalNode, ...] = (
    CausalNode(
        id="laminagem_queue_hours",
        category=NodeCategory.PROCESS_FLOW,
        description="Expected wait ahead of the laminagem line.",
        unit="hours",
        baseline=6.0,
        parents=("laminagem_duration", "worker_count_laminagem"),
    ),
    CausalNode(
        id="pintura_queue_hours",
        category=NodeCategory.PROCESS_FLOW,
        description="Expected wait ahead of the pintura line.",
        unit="hours",
        baseline=2.0,
        parents=("pintura_duration", "worker_count_pintura"),
    ),
)


# ─── Quality ─────────────────────────────────────────────────────────────

_QUALITY: Tuple[CausalNode, ...] = (
    CausalNode(
        id="quality_risk_score",
        category=NodeCategory.QUALITY,
        description="Probability the op will need rework (0..1).",
        unit="0..1",
        baseline=0.08,
        parents=("operator_experience", "external_temperature", "mold_age"),
    ),
    CausalNode(
        id="rework_rate",
        category=NodeCategory.QUALITY,
        description="Observed rework rate over the horizon.",
        unit="0..1",
        baseline=0.06,
        parents=("quality_risk_score", "worker_count_laminagem"),
    ),
)


# ─── Outputs (KPIs) ──────────────────────────────────────────────────────

_OUTPUTS: Tuple[CausalNode, ...] = (
    CausalNode(
        id="makespan_hours",
        category=NodeCategory.OUTPUT,
        description="Horizon length from first start to last end.",
        unit="hours",
        baseline=240.0,
        parents=(
            "mold_setup_time",
            "laminagem_duration",
            "curing_time",
            "pintura_duration",
            "laminagem_queue_hours",
            "pintura_queue_hours",
        ),
    ),
    CausalNode(
        id="total_tardiness_hours",
        category=NodeCategory.OUTPUT,
        description="Aggregate lateness across all orders.",
        unit="hours",
        baseline=18.0,
        parents=(
            "makespan_hours",
            "material_availability_pct",
            "rework_rate",
        ),
    ),
    CausalNode(
        id="throughput_eur_day",
        category=NodeCategory.OUTPUT,
        description="Revenue produced per working day.",
        unit="EUR/day",
        baseline=28_000.0,
        parents=(
            "makespan_hours",
            "shift_mode",
            "material_availability_pct",
            "rework_rate",
        ),
    ),
    CausalNode(
        id="on_time_delivery_pct",
        category=NodeCategory.OUTPUT,
        description="Share of orders shipped on or before the promised date.",
        unit="0..1",
        baseline=0.84,
        parents=("total_tardiness_hours",),
    ),
    CausalNode(
        id="setup_count",
        category=NodeCategory.OUTPUT,
        description="Number of distinct setups in the horizon.",
        unit="count",
        baseline=14.0,
        parents=("mold_availability_pct", "routing_variant"),
    ),
)


ALL_NODES: Tuple[CausalNode, ...] = (
    _CONFOUNDERS + _INPUTS + _PROCESS_TIMES + _PROCESS_FLOW + _QUALITY + _OUTPUTS
)

NODES_BY_ID: Dict[str, CausalNode] = {n.id: n for n in ALL_NODES}


# ═══════════════════════════════════════════════════════════════════════════
# Functional forms — one lambda per non-input node
# ═══════════════════════════════════════════════════════════════════════════
#
# Each function receives a parents-value dict and returns the node
# value. The formulas are deliberately linear (or gently non-linear) so
# they're easy to reason about. The absolute numbers are secondary —
# what matters is the SIGN and ROUGH MAGNITUDE of each coefficient,
# because those are what the LLM's causal chain will cite.

def _fn_mold_setup_time(p: Dict[str, float]) -> float:
    return max(
        0.0,
        0.5 + 0.10 * p["mold_age"] - 0.40 * (p["mold_availability_pct"] - 0.85),
    )


def _fn_laminagem_duration(p: Dict[str, float]) -> float:
    # More workers → shorter duration. More experience → shorter. Variant B is 8 % faster.
    base = 4.0 - 0.08 * (p["worker_count_laminagem"] - 18) \
        - 0.04 * (p["operator_experience"] - 8)
    if p["routing_variant"] >= 0.5:
        base *= 0.92
    return max(1.0, base)


def _fn_curing_time(p: Dict[str, float]) -> float:
    # Cooler ambient → slower cure (each °C below 19 adds 0.4 h).
    return max(6.0, 15.0 - 0.4 * (p["external_temperature"] - 19.0))


def _fn_desmolde_qc_time(p: Dict[str, float]) -> float:
    return max(0.25, 0.5 - 0.02 * (p["operator_experience"] - 8))


def _fn_pintura_duration(p: Dict[str, float]) -> float:
    base = 3.5 - 0.15 * (p["worker_count_pintura"] - 6)
    if p["routing_variant"] >= 0.5:
        base *= 0.95
    return max(1.5, base)


def _fn_laminagem_queue_hours(p: Dict[str, float]) -> float:
    # Slower op + smaller crew → deeper queue.
    return max(
        0.0,
        p["laminagem_duration"] * 1.5 - 0.25 * (p["worker_count_laminagem"] - 18),
    )


def _fn_pintura_queue_hours(p: Dict[str, float]) -> float:
    return max(
        0.0,
        p["pintura_duration"] * 0.6 - 0.3 * (p["worker_count_pintura"] - 6),
    )


def _fn_quality_risk_score(p: Dict[str, float]) -> float:
    # Experience hurts risk, temperature far from 19 °C helps it grow.
    delta_temp = abs(p["external_temperature"] - 19.0)
    return max(
        0.0,
        min(
            1.0,
            0.08 - 0.006 * (p["operator_experience"] - 8)
            + 0.015 * delta_temp + 0.008 * p["mold_age"],
        ),
    )


def _fn_rework_rate(p: Dict[str, float]) -> float:
    return max(
        0.0,
        min(
            1.0,
            0.9 * p["quality_risk_score"]
            - 0.002 * (p["worker_count_laminagem"] - 18),
        ),
    )


def _fn_makespan_hours(p: Dict[str, float]) -> float:
    setups = 14.0  # carried via setup_count indirectly; keep simple here.
    return (
        p["mold_setup_time"] * setups
        + p["laminagem_duration"] * 25
        + p["curing_time"] * 6
        + p["pintura_duration"] * 20
        + p["laminagem_queue_hours"]
        + p["pintura_queue_hours"]
    )


def _fn_total_tardiness_hours(p: Dict[str, float]) -> float:
    # Late when makespan exceeds 240 h OR material shortage OR rework spike.
    excess = max(0.0, p["makespan_hours"] - 240.0)
    material_penalty = max(0.0, (0.95 - p["material_availability_pct"]) * 120.0)
    rework_penalty = p["rework_rate"] * 60.0
    return excess + material_penalty + rework_penalty


def _fn_throughput_eur_day(p: Dict[str, float]) -> float:
    # Base throughput per single shift, scaled by shift_mode + materials - rework loss.
    base = 28_000.0 * p["shift_mode"]
    material_factor = 0.5 + 0.5 * p["material_availability_pct"]
    rework_loss = p["rework_rate"] * 4_000.0
    # Makespan overrun reduces effective working days.
    makespan_factor = max(0.6, 1.0 - max(0.0, p["makespan_hours"] - 240.0) / 2400.0)
    return max(0.0, base * material_factor * makespan_factor - rework_loss)


def _fn_on_time_delivery_pct(p: Dict[str, float]) -> float:
    # Every extra hour of tardiness knocks 1 pp off OTD, floor at 0.3.
    return max(0.30, min(1.0, 0.95 - 0.01 * p["total_tardiness_hours"]))


def _fn_setup_count(p: Dict[str, float]) -> float:
    # Higher availability + routing variant = fewer setups.
    base = 14.0 - 10.0 * (p["mold_availability_pct"] - 0.85)
    if p["routing_variant"] >= 0.5:
        base -= 2.0
    return max(1.0, base)


_FUNCTIONS: Dict[str, Callable[[Dict[str, float]], float]] = {
    "mold_setup_time": _fn_mold_setup_time,
    "laminagem_duration": _fn_laminagem_duration,
    "curing_time": _fn_curing_time,
    "desmolde_qc_time": _fn_desmolde_qc_time,
    "pintura_duration": _fn_pintura_duration,
    "laminagem_queue_hours": _fn_laminagem_queue_hours,
    "pintura_queue_hours": _fn_pintura_queue_hours,
    "quality_risk_score": _fn_quality_risk_score,
    "rework_rate": _fn_rework_rate,
    "makespan_hours": _fn_makespan_hours,
    "total_tardiness_hours": _fn_total_tardiness_hours,
    "throughput_eur_day": _fn_throughput_eur_day,
    "on_time_delivery_pct": _fn_on_time_delivery_pct,
    "setup_count": _fn_setup_count,
}


# ═══════════════════════════════════════════════════════════════════════════
# Traversal primitives
# ═══════════════════════════════════════════════════════════════════════════


def topological_order() -> List[str]:
    """Stable topological sort of all node ids.

    Uses Kahn's algorithm over the parent-list encoded in each
    :class:`CausalNode`. Ties break on insertion order into
    ``ALL_NODES``, so the output is deterministic run-to-run.
    """
    remaining: Dict[str, Set[str]] = {
        n.id: set(n.parents) for n in ALL_NODES
    }
    order: List[str] = []
    while remaining:
        ready = [nid for nid, parents in remaining.items() if not parents]
        if not ready:
            raise RuntimeError(
                "NELO_DAG has a cycle: " + ", ".join(sorted(remaining))
            )
        # Preserve declaration order among ready nodes.
        ready.sort(key=lambda nid: next(
            i for i, n in enumerate(ALL_NODES) if n.id == nid
        ))
        for nid in ready:
            order.append(nid)
            remaining.pop(nid)
            for others in remaining.values():
                others.discard(nid)
    return order


def descendants_of(node_id: str) -> Set[str]:
    """Return every node reachable from ``node_id`` (exclusive)."""
    if node_id not in NODES_BY_ID:
        raise KeyError(f"Unknown node: {node_id}")
    children: Dict[str, List[str]] = {n.id: [] for n in ALL_NODES}
    for n in ALL_NODES:
        for p in n.parents:
            children[p].append(n.id)
    seen: Set[str] = set()
    stack: List[str] = list(children[node_id])
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(children[cur])
    return seen


def ancestors_of(node_id: str) -> Set[str]:
    """Return every node that transitively feeds into ``node_id``."""
    if node_id not in NODES_BY_ID:
        raise KeyError(f"Unknown node: {node_id}")
    seen: Set[str] = set()
    stack: List[str] = list(NODES_BY_ID[node_id].parents)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(NODES_BY_ID[cur].parents)
    return seen


# ═══════════════════════════════════════════════════════════════════════════
# causal_query — do-operator + observation
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CausalQueryResult:
    """Output of :func:`causal_query`.

    * ``target_value`` — value computed under the current evidence
      (the ``do`` + ``observe`` passed to the query).
    * ``baseline_value`` — the value the graph computes with *no*
      intervention and *no* observations, i.e. every node at its
      declared baseline. This is the honest "reference scenario"
      most causal questions are asked against.
    * ``delta`` — ``target_value - baseline_value``. Positive → the
      intervention pushes the KPI up; negative → down.

    ``values`` holds the computed value for every downstream node in
    topological order (useful for the LLM to inspect intermediate
    steps). ``path`` is the explicit ancestor→target chain — the
    "mechanism" we surface in ``CausalChain.mechanism``.
    """
    target: str
    target_value: float
    baseline_value: float
    delta: float
    values: Dict[str, float] = field(default_factory=dict)
    path: List[str] = field(default_factory=list)


def causal_query(
    target: str,
    *,
    do: Optional[Dict[str, float]] = None,
    observe: Optional[Dict[str, float]] = None,
) -> CausalQueryResult:
    """Compute ``target`` under an intervention + observations.

    Semantics
    ---------
    * ``do={x: v}`` — Pearl's do-operator. ``x`` is fixed to ``v`` and
      its own parents are **ignored** (a hard intervention). Downstream
      nodes propagate this fixed value.
    * ``observe={y: w}`` — soft evidence. ``y`` is set to ``w`` but its
      parent effect is NOT severed; if ``y`` had a functional form and
      more parents propagate forward, this ``w`` is simply the current
      reading.
    * Any node neither intervened on nor observed and not in the DAG's
      recursion falls back to its ``baseline``.

    Returns
    -------
    :class:`CausalQueryResult` with ``delta = target_value -
    baseline_target``. A positive delta means the intervention
    **raises** the KPI; a negative delta lowers it.
    """
    if target not in NODES_BY_ID:
        raise KeyError(f"Unknown target node: {target}")
    do = dict(do or {})
    observe = dict(observe or {})

    for nid in list(do) + list(observe):
        if nid not in NODES_BY_ID:
            raise KeyError(f"Unknown node in intervention/observation: {nid}")

    values = _propagate(do=do, observe=observe)
    target_value = values[target]

    # The "reference scenario" is everything at its declared baseline
    # with no intervention. We recompute it instead of reading the
    # declared baseline because declared baselines are domain anchors,
    # not mechanistically consistent (e.g. makespan's declared 240 h
    # came from observed data; the forward-propagated natural baseline
    # may be different). The honest delta compares like-with-like.
    if do or observe:
        reference_values = _propagate(do={}, observe={})
        baseline_value = reference_values[target]
    else:
        baseline_value = target_value

    # Build the causal path as "intervention nodes → target".
    anc = ancestors_of(target)
    path_nodes = [
        nid for nid in topological_order()
        if nid == target or nid in anc or nid in do
    ]

    return CausalQueryResult(
        target=target,
        target_value=target_value,
        baseline_value=baseline_value,
        delta=target_value - baseline_value,
        values=values,
        path=path_nodes,
    )


def _propagate(
    *,
    do: Dict[str, float],
    observe: Dict[str, float],
) -> Dict[str, float]:
    """Forward pass in topological order with evidence + intervention
    overlaid. Shared by the main query and the reference-scenario
    recompute."""
    values: Dict[str, float] = {n.id: float(n.baseline) for n in ALL_NODES}
    values.update(observe)
    values.update(do)

    for nid in topological_order():
        if nid in do or nid in observe:
            continue
        fn = _FUNCTIONS.get(nid)
        if fn is None:
            continue  # input / confounder — keep baseline
        node = NODES_BY_ID[nid]
        try:
            values[nid] = float(fn({p: values[p] for p in node.parents}))
        except KeyError as exc:
            raise KeyError(
                f"Missing parent {exc} while computing {nid}"
            ) from exc
    return values


# ═══════════════════════════════════════════════════════════════════════════
# Public helpers for CausalChain validation (used by F.2)
# ═══════════════════════════════════════════════════════════════════════════


def is_valid_node(name: str) -> bool:
    """Does ``name`` exist in the NELO DAG? Used by the syntactic +
    DAG-consistency validator layers."""
    return name in NODES_BY_ID


def edge_exists(src: str, dst: str, *, transitive: bool = True) -> bool:
    """Is there a (direct or transitive) directed path from ``src`` to ``dst``?"""
    if src not in NODES_BY_ID or dst not in NODES_BY_ID:
        return False
    if transitive:
        return dst in descendants_of(src)
    return src in NODES_BY_ID[dst].parents


def graph_summary() -> Dict[str, Any]:
    """Serializable description of the DAG — handy for ``/v1/causal/
    graph`` endpoints and the system prompt."""
    return {
        "nodes": [
            {
                "id": n.id,
                "category": n.category.value,
                "description": n.description,
                "unit": n.unit,
                "baseline": n.baseline,
                "parents": list(n.parents),
            }
            for n in ALL_NODES
        ],
        "node_count": len(ALL_NODES),
        "confounder_count": sum(
            1 for n in ALL_NODES if n.category == NodeCategory.CONFOUNDER
        ),
    }
