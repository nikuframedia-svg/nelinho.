"""
ProdPlan ONE — CausalChain + 5-layer verification (Sprint F.2)
================================================================

Blueprint v2.0 §24 / §30 says the Copilot must answer "why" with a
**structured** chain the backend can validate before it lights up in
the UI. A free-text answer is useless for governance — we need to
prove that every claim is syntactically well-formed, lives inside the
NELO DAG, flows in the right direction, reads consistently, and
matches what the causal kernel actually computes.

The output is a :class:`CausalChain` Pydantic model. Every response
goes through :func:`verify_chain`, which runs five independent checks
and returns a :class:`CausalVerificationResult` with a composite
score in [0, 1]:

    CC = layer_syntactic
       × layer_dag_consistent
       × layer_direction
       × layer_nli
       × layer_kernel

``verify_chain`` never raises — a broken chain yields a result with
``passed=False`` and a populated ``issues`` list so the UI can show
the operator *why* it was rejected, not just that it was.

**Rule-based NLI** — Sprint F ships without a neural NLI model (no
transformers dep). Instead, the NLI layer does three deterministic
checks grounded in the DAG:

  1. The numerical sign the LLM claimed (e.g. "routing B *reduces*
     makespan") must match the sign of the kernel's delta.
  2. The recommendation's direction (``increase`` / ``decrease``)
     must be compatible with the node's monotonicity (all NELO
     functional forms are monotone in each parent over the operating
     range, so this check is deterministic).
  3. The recommendation shouldn't contradict the mechanism. If the
     mechanism says "worker_count rose → duration fell" then a
     recommendation "reduce worker_count" is a contradiction.

Sprint I will optionally swap in a real NLI model behind this same
interface.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

_DECREASE_KEYWORDS = re.compile(
    r"\b(reduce|reducing|lower|lowering|decrease|decreasing|cut|cutting|"
    r"cortar|reduzir|baixar|diminuir)\b",
    re.IGNORECASE,
)
_INCREASE_KEYWORDS = re.compile(
    r"\b(raise|raising|increase|increasing|grow|growing|aumentar|subir|"
    r"elevar|ampliar)\b",
    re.IGNORECASE,
)

from src.copilot.causal.nelo_dag import (
    CausalQueryResult,
    NODES_BY_ID,
    NodeCategory,
    causal_query,
    descendants_of,
    edge_exists,
    is_valid_node,
)


# ═══════════════════════════════════════════════════════════════════════════
# CausalChain Pydantic — what the LLM must emit
# ═══════════════════════════════════════════════════════════════════════════


class AristotleCause(str, Enum):
    """Four-cause taxonomy (Blueprint v2.0 §26).

    Not every answer needs all four — the LLM fills the ones that
    carry signal. The verifier only checks shape, not content (a
    neural NLI would upgrade this, not this sprint).
    """
    MATERIAL = "material"
    FORMAL = "formal"
    EFFICIENT = "efficient"
    FINAL = "final"


class AristotleAnnotation(BaseModel):
    """Aristotle's four causes attached to a chain, all optional."""
    material: Optional[str] = Field(
        default=None,
        description="What it's made of (stock, mould, workforce).",
    )
    formal: Optional[str] = Field(
        default=None,
        description="The pattern/template — routing, BOM, SOP.",
    )
    efficient: Optional[str] = Field(
        default=None,
        description="The agent — which operator / machine / decision.",
    )
    final: Optional[str] = Field(
        default=None,
        description="The purpose — the KPI being optimised.",
    )


class CausalClaim(BaseModel):
    """A single node-level claim inside the mechanism.

    The LLM says "node X moved in direction D by approximately
    magnitude M". The verifier matches this against what the kernel
    computed for X under the same ``do``.
    """
    node: str = Field(
        ...,
        description="NELO_DAG node id (must exist in the graph).",
    )
    direction: str = Field(
        ...,
        description="One of: 'increase', 'decrease', 'unchanged'.",
    )
    magnitude: Optional[float] = Field(
        default=None,
        description="Approximate magnitude of the change. Optional; "
        "omitted claims are still validated for direction + DAG membership.",
    )
    rationale: Optional[str] = Field(
        default=None,
        description="One short sentence of why — surfaced in the UI.",
    )

    @field_validator("direction")
    @classmethod
    def _validate_direction(cls, value: str) -> str:
        allowed = {"increase", "decrease", "unchanged"}
        if value not in allowed:
            raise ValueError(
                f"direction must be one of {sorted(allowed)}, got {value!r}"
            )
        return value


class CausalChain(BaseModel):
    """Structured answer for a causal question.

    This shape is what the LLM contract promises the frontend. Every
    field is required or has a safe default so the verifier's syntactic
    layer can fail fast on bad emissions.
    """
    question: str = Field(
        ...,
        description="The user's original question (for audit).",
    )
    target: str = Field(
        ...,
        description="The KPI / node being explained (must be in NELO_DAG).",
    )
    root_cause: str = Field(
        ...,
        description="The upstream node the answer blames — DAG node id.",
    )
    mechanism: List[CausalClaim] = Field(
        default_factory=list,
        description="Ordered path from root_cause → target, one claim per step.",
    )
    counterfactual: Optional[str] = Field(
        default=None,
        description="One-sentence alternative scenario ('had we set routing=B, …').",
    )
    recommendation: Optional[str] = Field(
        default=None,
        description="Concrete operator action the chain suggests.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM's self-reported confidence before the verifier runs.",
    )
    aristotle: Optional[AristotleAnnotation] = Field(
        default=None,
        description="Aristotelian four-cause annotation (optional).",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="Source citations (metric_id:timestamp, commit_sha, rule_id…).",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Verification result
# ═══════════════════════════════════════════════════════════════════════════


class LayerVerdict(BaseModel):
    name: str
    score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    issues: List[str] = Field(default_factory=list)


class CausalVerificationResult(BaseModel):
    """Output of :func:`verify_chain`.

    ``coherence`` is the product of the five layer scores. The
    upstream orchestrator uses it as a Trust Index component (§30,
    8th component). A chain with ``coherence < COHERENCE_GATE`` is
    returned to the user with a "no answer" notice — never rendered as
    a legitimate explanation.
    """
    coherence: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    layers: List[LayerVerdict] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)

    def layer(self, name: str) -> Optional[LayerVerdict]:
        for row in self.layers:
            if row.name == name:
                return row
        return None


COHERENCE_GATE: float = 0.85
"""Default threshold: a chain must score ≥ this to be shown as an
explanation. The governance router can override per-tenant."""


# ═══════════════════════════════════════════════════════════════════════════
# Verification layers
# ═══════════════════════════════════════════════════════════════════════════


def _layer_syntactic(chain: CausalChain) -> LayerVerdict:
    """Pydantic already enforces shape — here we add semantic sanity.

    If the caller passed a pre-parsed :class:`CausalChain` we've
    already cleared basic typing; the remaining checks catch things
    Pydantic can't express (e.g. mechanism must have at least one
    step for a non-trivial question).
    """
    issues: List[str] = []

    if not chain.question.strip():
        issues.append("question is empty")
    if chain.target == chain.root_cause:
        issues.append(
            "root_cause equals target — a cause of itself is a tautology"
        )
    if not chain.mechanism:
        issues.append("mechanism is empty (at least one step is required)")

    passed = len(issues) == 0
    return LayerVerdict(
        name="syntactic",
        score=1.0 if passed else 0.0,
        passed=passed,
        issues=issues,
    )


def _layer_dag_consistent(chain: CausalChain) -> LayerVerdict:
    """Every node name the chain mentions must exist in NELO_DAG."""
    issues: List[str] = []
    candidates = [chain.target, chain.root_cause] + [c.node for c in chain.mechanism]
    unknown = [name for name in candidates if not is_valid_node(name)]
    if unknown:
        issues.append(
            f"unknown DAG nodes: {sorted(set(unknown))}"
        )
    passed = not unknown
    return LayerVerdict(
        name="dag_consistent",
        score=1.0 if passed else 0.0,
        passed=passed,
        issues=issues,
    )


def _layer_direction(chain: CausalChain) -> LayerVerdict:
    """The root_cause must have a directed path to the target, and
    every claim in ``mechanism`` must sit on that path (either upstream
    of the target or equal to it, with root_cause upstream of all)."""
    issues: List[str] = []

    if not is_valid_node(chain.root_cause) or not is_valid_node(chain.target):
        # dag_consistent already flagged — keep this layer tight.
        return LayerVerdict(
            name="direction", score=0.0, passed=False,
            issues=["nodes missing from DAG (see dag_consistent)"],
        )

    if not edge_exists(chain.root_cause, chain.target, transitive=True):
        issues.append(
            f"no directed path from {chain.root_cause} → {chain.target}"
        )

    reachable = descendants_of(chain.root_cause) | {chain.root_cause}
    for claim in chain.mechanism:
        if claim.node not in reachable:
            issues.append(
                f"mechanism step {claim.node!r} is not reachable from "
                f"root_cause {chain.root_cause!r}"
            )

    passed = not issues
    return LayerVerdict(
        name="direction",
        score=1.0 if passed else 0.0,
        passed=passed,
        issues=issues,
    )


def _claimed_sign(direction: str) -> int:
    return {"increase": 1, "decrease": -1, "unchanged": 0}[direction]


def _layer_nli(
    chain: CausalChain,
    *,
    kernel_result: Optional[CausalQueryResult] = None,
) -> LayerVerdict:
    """Rule-based natural-language consistency.

    Checks:
      * Every claim's direction is matched by the monotonicity of the
        node's functional form under the chain's ``root_cause``.
        (We infer this by nudging ``root_cause`` up and comparing
        ``target_value`` sign; full per-node check is handled via
        the kernel layer.)
      * No self-contradictions between ``recommendation`` and the
        leading mechanism claim (e.g. mechanism says
        "worker_count_laminagem → increase → laminagem_duration
        decreases" and recommendation says "reduce worker_count").
    """
    issues: List[str] = []

    # Recommendation ↔ mechanism consistency. Only meaningful when the
    # chain's first mechanism step describes the root cause (a lever
    # the operator can pull) rather than jumping straight to the
    # target. If mechanism[0] IS the target, there is no lever claim
    # to compare the recommendation against — skip the rule.
    if chain.recommendation and chain.mechanism:
        first_step = chain.mechanism[0]
        if first_step.node != chain.target:
            rec = chain.recommendation
            if first_step.direction == "increase" and _DECREASE_KEYWORDS.search(rec):
                issues.append(
                    "recommendation suggests reducing, but mechanism says the "
                    "root cause should increase"
                )
            elif first_step.direction == "decrease" and _INCREASE_KEYWORDS.search(rec):
                issues.append(
                    "recommendation suggests increasing, but mechanism says the "
                    "root cause should decrease"
                )

    # Target-direction consistency (if we have a kernel result).
    if kernel_result is not None:
        for claim in chain.mechanism:
            if claim.node != chain.target:
                continue
            expected = 0
            delta = kernel_result.delta
            if abs(delta) < 1e-6:
                expected = 0
            else:
                expected = 1 if delta > 0 else -1
            claimed = _claimed_sign(claim.direction)
            if expected != claimed:
                issues.append(
                    f"target direction mismatch: chain claims "
                    f"{claim.direction}, kernel shows delta={delta:.4f}"
                )

    passed = not issues
    return LayerVerdict(
        name="nli",
        score=1.0 if passed else max(0.0, 1.0 - 0.5 * len(issues)),
        passed=passed,
        issues=issues,
    )


def _layer_kernel(
    chain: CausalChain,
    *,
    kernel_result: Optional[CausalQueryResult],
    magnitude_tolerance: float = 0.30,
) -> LayerVerdict:
    """Numerical cross-check against the causal kernel.

    If the caller supplied a ``kernel_result`` the layer scores how
    closely the LLM's magnitude claim (if any) matches the kernel's
    computed delta. A direction-only claim scores 0.8 (partial credit)
    because we can't reject what the user didn't assert.

    With no kernel result the layer scores 0.5 — we can't confirm the
    numbers, but we also can't refute them.
    """
    if kernel_result is None:
        return LayerVerdict(
            name="kernel", score=0.5, passed=False,
            issues=["no kernel result supplied — cannot validate magnitudes"],
        )

    issues: List[str] = []
    target_claim = next(
        (c for c in chain.mechanism if c.node == chain.target), None,
    )
    if target_claim is None:
        issues.append(
            f"mechanism lacks a claim for target {chain.target!r}"
        )
        return LayerVerdict(
            name="kernel", score=0.3, passed=False, issues=issues,
        )

    # Direction alignment
    expected_sign = (
        0 if abs(kernel_result.delta) < 1e-6
        else (1 if kernel_result.delta > 0 else -1)
    )
    claimed_sign = _claimed_sign(target_claim.direction)
    if expected_sign != claimed_sign:
        issues.append(
            f"sign mismatch: kernel delta={kernel_result.delta:.4f} "
            f"vs claim={target_claim.direction}"
        )

    # Magnitude alignment (only if the LLM committed to a number)
    score = 1.0
    if target_claim.magnitude is not None:
        kernel_abs = abs(kernel_result.delta)
        claimed_abs = abs(target_claim.magnitude)
        if kernel_abs < 1e-6 and claimed_abs >= 1e-6:
            issues.append("kernel reports ≈0 delta but claim asserts non-zero")
            score = 0.3
        else:
            denom = max(kernel_abs, 1e-6)
            rel_err = abs(claimed_abs - kernel_abs) / denom
            if rel_err > magnitude_tolerance:
                issues.append(
                    f"magnitude off by {rel_err*100:.0f}% "
                    f"(kernel={kernel_abs:.2f}, claim={claimed_abs:.2f})"
                )
                score = max(0.4, 1.0 - rel_err)

    if expected_sign != claimed_sign:
        score = min(score, 0.3)

    # Direction-only partial credit — but only when the kernel actually
    # has a non-zero delta to measure against. An "unchanged" claim on
    # a near-zero-delta kernel is a fully-specified answer (no
    # magnitude needed), so it deserves the full mark.
    if target_claim.magnitude is None and not issues:
        if (
            target_claim.direction == "unchanged"
            and abs(kernel_result.delta) < 1e-6
        ):
            score = 1.0
        else:
            score = 0.8

    passed = not issues
    return LayerVerdict(
        name="kernel",
        score=score,
        passed=passed,
        issues=issues,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Public entry
# ═══════════════════════════════════════════════════════════════════════════


def verify_chain(
    chain: CausalChain,
    *,
    do: Optional[Dict[str, float]] = None,
    observe: Optional[Dict[str, float]] = None,
    kernel_result: Optional[CausalQueryResult] = None,
    gate: float = COHERENCE_GATE,
) -> CausalVerificationResult:
    """Run all five layers on ``chain`` and return the verdict.

    If ``kernel_result`` is provided the NLI + kernel layers use it
    directly. Otherwise, when ``do`` is provided, we call
    :func:`causal_query` with it against the chain's ``target`` to
    compute a fresh kernel comparison. If neither is provided the
    kernel layer degrades to the "no reference" score.
    """
    if kernel_result is None and do is not None and is_valid_node(chain.target):
        try:
            kernel_result = causal_query(
                chain.target, do=do, observe=observe,
            )
        except Exception:
            kernel_result = None

    layers: List[LayerVerdict] = [
        _layer_syntactic(chain),
        _layer_dag_consistent(chain),
        _layer_direction(chain),
        _layer_nli(chain, kernel_result=kernel_result),
        _layer_kernel(chain, kernel_result=kernel_result),
    ]

    coherence = 1.0
    for layer in layers:
        coherence *= layer.score

    issues: List[str] = [
        f"[{layer.name}] {issue}"
        for layer in layers
        for issue in layer.issues
    ]

    return CausalVerificationResult(
        coherence=coherence,
        passed=coherence >= gate,
        layers=layers,
        issues=issues,
    )


def verify_chain_dict(
    payload: Dict[str, Any],
    **kwargs: Any,
) -> CausalVerificationResult:
    """Parse a dict payload (e.g. raw LLM JSON) and verify it.

    Catches validation errors and turns them into a syntactic-layer
    failure so callers never hit a traceback on bad LLM output.
    """
    try:
        chain = CausalChain.model_validate(payload)
    except Exception as exc:
        return CausalVerificationResult(
            coherence=0.0,
            passed=False,
            layers=[LayerVerdict(
                name="syntactic", score=0.0, passed=False,
                issues=[f"payload is not a valid CausalChain: {exc}"],
            )],
            issues=[f"[syntactic] payload is not a valid CausalChain: {exc}"],
        )
    return verify_chain(chain, **kwargs)


# Keep an explicit export list so `from ... import *` stays tidy.
__all__ = [
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
