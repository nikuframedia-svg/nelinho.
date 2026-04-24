"""Sprint F — LLM Causal reasoning stack.

Blueprint v2.0 §24–§31. This package is the substrate the Copilot uses
to answer *why* questions: a Python SCM of the NELO factory, a
Pydantic contract for structured answers, and a five-layer validator
that gates every LLM response.

Public surface:

* :mod:`.nelo_dag` — :func:`causal_query`, :data:`ALL_NODES`, graph
  traversal helpers.
* :mod:`.chain` — :class:`CausalChain`, :func:`verify_chain`.
"""

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

__all__ = [
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
]
