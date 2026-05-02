"""Sprint F — LLM Causal reasoning stack.

Blueprint v2.0 §24–§31. This package is the substrate the Copilot uses
to answer *why* questions: a Python SCM of the NELO factory, a
Pydantic contract for structured answers, and a five-layer validator
that gates every LLM response.

Public surface:

* :mod:`.nelo_dag` — :func:`causal_query`, :data:`ALL_NODES`, graph
  traversal helpers.
* :mod:`.chain` — :class:`CausalChain`, :func:`verify_chain`.
* :mod:`.ablkit` — Sprint I.2 divergence tracking for DPO feedback.
"""

from .ablkit import (
    Divergence,
    DivergenceStore,
    detect_divergences,
    render_dpo_triplet,
)
from .chain import (
    AristotleAnnotation,
    AristotleCause,
    CausalChain,
    CausalClaim,
    CausalVerificationResult,
    COHERENCE_GATE,
    LayerVerdict,
    verify_chain,
    verify_chain_dict,
)
from .nelo_dag import (
    ALL_NODES,
    CausalNode,
    CausalQueryResult,
    NODES_BY_ID,
    NodeCategory,
    ancestors_of,
    causal_query,
    descendants_of,
    edge_exists,
    graph_summary,
    is_valid_node,
    topological_order,
)
from .runtime import record_causal_audit
from .world_model import (
    DRIFT_PROFILE,
    ForecastReport,
    STEP_UNIT,
    StepStats,
    forecast,
)

__all__ = [
    "record_causal_audit",
    # DAG
    "ALL_NODES",
    "CausalNode",
    "CausalQueryResult",
    "NODES_BY_ID",
    "NodeCategory",
    "ancestors_of",
    "causal_query",
    "descendants_of",
    "edge_exists",
    "graph_summary",
    "is_valid_node",
    "topological_order",
    # Chain
    "AristotleAnnotation",
    "AristotleCause",
    "CausalChain",
    "CausalClaim",
    "CausalVerificationResult",
    "COHERENCE_GATE",
    "LayerVerdict",
    "verify_chain",
    "verify_chain_dict",
    # ABLkit (Sprint I.2)
    "Divergence",
    "DivergenceStore",
    "detect_divergences",
    "render_dpo_triplet",
    # World model (Sprint F+++)
    "DRIFT_PROFILE",
    "ForecastReport",
    "STEP_UNIT",
    "StepStats",
    "forecast",
]
