"""
ProdPlan ONE — ABLkit (Sprint I.2, Camada 4)
===============================================

Abducible Learning Kit: every time the Copilot produces a
``CausalChain`` and the NELO kernel disagrees with it, we log the
pair. Each pair becomes a training sample "LLM said X, the truth was
Y" that the next DPO fine-tune (Camada 3) consumes — the LLM's next
release is strictly more reliable than its predecessor on the
divergences it historically made.

Why kernel-backed ground truth
------------------------------
For a factory DAG the kernel is *authoritative*. It's pure Python,
fully reproducible, and grounded in the Blueprint's causal model.
When the LLM claims "routing B lowers makespan by 40 h" and
``causal_query`` returns −12 h, the kernel wins by definition.

This file is *not* a full ABL implementation (no logic programming,
no first-order rules). It's the minimum viable tracking surface:

* ``DivergenceDetector`` compares a chain vs its verification result
  and extracts structured divergences.
* ``DivergenceStore`` persists them as JSONL so the DPO builder can
  read them side-by-side with the ``ScheduleCommit``-derived
  triplets.
* ``render_dpo_triplet`` emits the same ``{prompt, chosen, rejected}``
  shape as ``DPODatasetBuilder`` so the fine-tuner ingests both
  sources uniformly.

No new dependencies. Zero runtime cost unless a chain actually
fails verification.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import UUID

from src.copilot.causal.chain import (
    CausalChain,
    CausalVerificationResult,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Divergence record
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Divergence:
    """One structured disagreement between the LLM and the kernel.

    Stored as JSON alongside the DPO triplets so the fine-tuner can
    ingest it without special-casing. ``layer`` tells us which
    verification layer caught the error — the training objective then
    targets that failure mode.
    """

    question: str
    target: str
    claimed: Dict[str, Any]
    kernel: Dict[str, Any]
    layer: str                 # "kernel", "nli", "direction", "dag_consistent"
    severity: str              # "minor", "major", "contradiction"
    description: str
    coherence: float
    tenant_id: Optional[str] = None
    commit_sha: Optional[str] = None
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
# Detector
# ═══════════════════════════════════════════════════════════════════════════


_MAJOR_LAYERS = {"kernel", "direction"}
_MINOR_LAYERS = {"nli", "syntactic"}


def _severity_for(result: CausalVerificationResult) -> str:
    """Pick a severity from the failed layers. A hard direction/kernel
    failure is more actionable for fine-tuning than an NLI
    disagreement, which often flags stylistic issues."""
    failed_layers = {layer.name for layer in result.layers if not layer.passed}
    if not failed_layers:
        return "minor"
    if failed_layers & {"dag_consistent"}:
        return "contradiction"
    if failed_layers & _MAJOR_LAYERS:
        return "major"
    if failed_layers & _MINOR_LAYERS:
        return "minor"
    return "minor"


def _summary_for_layer(
    name: str,
    result: CausalVerificationResult,
) -> str:
    """Join the issues from a given layer into one human line."""
    layer = result.layer(name)
    if layer is None or layer.passed:
        return ""
    return "; ".join(layer.issues)


def _claim_for_target(chain: CausalChain) -> Dict[str, Any]:
    """Extract the chain's claim about the target node — the one the
    kernel can validate directly."""
    for c in chain.mechanism:
        if c.node == chain.target:
            return {
                "direction": c.direction,
                "magnitude": c.magnitude,
                "rationale": c.rationale,
            }
    # Fallback — the chain never named the target explicitly.
    return {"direction": None, "magnitude": None, "rationale": None}


def detect_divergences(
    chain: CausalChain,
    result: CausalVerificationResult,
    *,
    kernel_delta: Optional[float] = None,
    tenant_id: Optional[UUID] = None,
    commit_sha: Optional[str] = None,
) -> List[Divergence]:
    """Produce zero or more :class:`Divergence` rows from a verified
    chain.

    ``kernel_delta`` is the numerical delta from :func:`causal_query`
    for the target under the chain's intervention — the verifier
    already consumed it, but we record it here so the DPO trainer
    can see the gap in numbers, not just sentences.
    """
    if result.passed:
        return []

    severity = _severity_for(result)
    failed_layers = [layer.name for layer in result.layers if not layer.passed]
    claim = _claim_for_target(chain)
    kernel = {"delta": kernel_delta} if kernel_delta is not None else {}

    divergences: List[Divergence] = []
    for layer_name in failed_layers:
        divergences.append(
            Divergence(
                question=chain.question,
                target=chain.target,
                claimed=claim,
                kernel=kernel,
                layer=layer_name,
                severity=severity,
                description=_summary_for_layer(layer_name, result),
                coherence=result.coherence,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                commit_sha=commit_sha,
            )
        )
    return divergences


# ═══════════════════════════════════════════════════════════════════════════
# DPO triplet rendering
# ═══════════════════════════════════════════════════════════════════════════


def _direction_pt(direction: Optional[str]) -> str:
    return {
        "increase": "sobe",
        "decrease": "desce",
        "unchanged": "fica estável",
    }.get(direction or "", "sem direcção")


def render_dpo_triplet(div: Divergence) -> Dict[str, Any]:
    """Turn one divergence into the same (prompt, chosen, rejected)
    shape as :func:`DPODatasetBuilder`.

    * **prompt** — the operator's question plus the kernel evidence
      the LLM failed to respect.
    * **chosen** — what the kernel says (the ground truth we want
      the LLM to converge on).
    * **rejected** — what the LLM claimed. The fine-tuner penalises
      regenerating the rejected side on this prompt.
    """
    kernel_delta = div.kernel.get("delta") if isinstance(div.kernel, Mapping) else None
    claim_dir = div.claimed.get("direction")
    claim_mag = div.claimed.get("magnitude")

    prompt_lines = [
        f"Pergunta: {div.question.strip()}",
        f"KPI alvo: {div.target}",
    ]
    if kernel_delta is not None:
        prompt_lines.append(
            f"Kernel (verdade): delta = {kernel_delta:.4f} "
            f"({_direction_pt('increase' if kernel_delta > 0 else 'decrease' if kernel_delta < 0 else 'unchanged')})"
        )
    prompt_lines.append(
        "Explica o que aconteceu ao KPI e porquê, respeitando o kernel."
    )

    chosen_bits: List[str] = []
    if kernel_delta is not None:
        chosen_bits.append(
            f"O {div.target} {_direction_pt('increase' if kernel_delta > 0 else 'decrease' if kernel_delta < 0 else 'unchanged')} "
            f"em ≈ {abs(kernel_delta):.2f}."
        )
    else:
        chosen_bits.append(f"O efeito sobre {div.target} é coerente com o kernel.")
    if div.layer == "kernel":
        chosen_bits.append("A magnitude aqui não é opinião — vem do DAG.")
    chosen = " ".join(chosen_bits)

    rejected_bits: List[str] = []
    if claim_dir:
        rejected_bits.append(f"O {div.target} {_direction_pt(claim_dir)}.")
    if claim_mag is not None:
        rejected_bits.append(f"Por aproximadamente {claim_mag:.2f}.")
    if not rejected_bits:
        rejected_bits.append(
            f"Afirmação do LLM com problema na camada {div.layer}: {div.description or 'sem detalhe'}."
        )
    rejected = " ".join(rejected_bits)

    return {
        "prompt": "\n".join(prompt_lines),
        "chosen": chosen,
        "rejected": rejected,
        "meta": {
            "source": "ablkit",
            "layer": div.layer,
            "severity": div.severity,
            "coherence": round(div.coherence, 3),
            "tenant_id": div.tenant_id,
            "commit_sha": div.commit_sha,
            "recorded_at": div.recorded_at,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════════════════════


class DivergenceStore:
    """Append-only JSONL storage + query surface.

    Small footprint on purpose: divergences are sparse (most LLM
    answers pass verification) so a single file is fine at scale. If
    the tenant actually produces thousands per week, promote this to
    a DB-backed implementation behind the same interface.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, divergences: Iterable[Divergence]) -> int:
        divergences = list(divergences)
        if not divergences:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            for div in divergences:
                fh.write(json.dumps(div.to_json(), ensure_ascii=False))
                fh.write("\n")
        logger.info(
            "ablkit: appended %d divergences to %s",
            len(divergences), self.path,
        )
        return len(divergences)

    def load_all(self) -> List[Divergence]:
        if not self.path.exists():
            return []
        rows: List[Divergence] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    rows.append(Divergence(**payload))
                except Exception as exc:  # pragma: no cover — corrupt line
                    logger.warning("ablkit: skipping malformed row: %s", exc)
        return rows

    def export_dpo(self, output_path: Path) -> int:
        """Render every stored divergence as a DPO triplet and write
        them to ``output_path``. Used by the quarterly fine-tune
        pipeline to append ABLkit pairs to the main DPO dataset.
        """
        triplets = [render_dpo_triplet(d) for d in self.load_all()]
        if not triplets:
            return 0
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            for triplet in triplets:
                fh.write(json.dumps(triplet, ensure_ascii=False))
                fh.write("\n")
        return len(triplets)


__all__ = [
    "Divergence",
    "DivergenceStore",
    "detect_divergences",
    "render_dpo_triplet",
]
