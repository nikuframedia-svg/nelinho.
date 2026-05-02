"""
ProdPlan ONE — RetrainExplanation (Sprint R.4, Camada 2 audit)
================================================================

Camada 2 turns rejected alternatives into adaptive fitness weights.
Until R.4 the only audit was a coefficient log line — useless for the
CEO, the operator, anyone who isn't reading the source.

This module builds a deterministic, template-rendered Portuguese
explanation per KPI: which way the weight moved, by how much, and
which rejection category dominated the dataset that drove it. No LLM,
no judgement calls — same inputs always produce the same text so the
audit trail in ``TenantConfig`` history is replayable.

Used by:

* ``AdaptiveFitnessWeights.retrain`` — embeds the explanation into the
  ``RetrainResult`` it persists.
* ``GET /v1/governance/learning/weights/history`` — returns the last
  N versions of the weights payload, including these explanations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional


# Friendly labels for the rendered explanation. Matches the KPI labels
# the dashboard already shows so the human text doesn't drift from the
# numbers next to it.
_KPI_LABELS_PT: Dict[str, str] = {
    "w_makespan": "Makespan",
    "w_tardiness": "Tardiness",
    "w_setups": "Setups",
    "w_quality_risk": "Risco de qualidade",
}

# How far the weight has to move before we call it "subiu" / "desceu".
# Below this we say "estável" — keeps the explanation honest when the
# logistic regression nudged the weight by 1-2%.
_DIRECTION_THRESHOLD = 0.05  # 5%


@dataclass
class RetrainExplanation:
    """One explanation row per KPI in the adaptive bucket."""

    kpi: str                       # weight key (w_makespan, …)
    label: str                     # PT friendly label
    delta_pct: float               # current vs previous weight, percent
    direction: str                 # "up" | "down" | "stable"
    dominant_category: Optional[str]  # rejection category with most pairs
    pairs_used: int                # number of pairs that drove the fit
    human_text: str                # one-sentence PT explanation

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classify_direction(delta_pct: float) -> str:
    if delta_pct > _DIRECTION_THRESHOLD * 100:
        return "up"
    if delta_pct < -_DIRECTION_THRESHOLD * 100:
        return "down"
    return "stable"


def _direction_verb(direction: str) -> str:
    return {
        "up": "subiu",
        "down": "desceu",
        "stable": "manteve-se",
    }.get(direction, "manteve-se")


def _render_human_text(
    *,
    label: str,
    direction: str,
    delta_pct: float,
    pairs_used: int,
    dominant_category: Optional[str],
) -> str:
    """Deterministic PT template — no LLM, audit-friendly."""
    verb = _direction_verb(direction)
    if direction == "stable":
        prefix = f"Peso de **{label}** {verb} (Δ {delta_pct:+.1f}%)"
    else:
        prefix = f"Peso de **{label}** {verb} {abs(delta_pct):.1f}%"
    if pairs_used == 0:
        return f"{prefix} — sem pares novos no período."
    if dominant_category:
        return (
            f"{prefix} — categoria dominante: {dominant_category} "
            f"({pairs_used} pares analisados)."
        )
    return f"{prefix} — {pairs_used} pares analisados."


def build_retrain_explanations(
    *,
    current_weights: Mapping[str, float],
    previous_weights: Optional[Mapping[str, float]],
    pairs_used: int,
    by_category: Optional[Mapping[str, int]] = None,
) -> List[RetrainExplanation]:
    """Produce one ``RetrainExplanation`` per adaptive KPI.

    ``previous_weights`` is the snapshot from the prior retrain (what
    the GA was actually running with). On the very first retrain it
    can be ``None`` — we treat that as "no prior signal" and report
    delta_pct against defaults.
    """
    by_category = by_category or {}
    dominant = max(by_category.items(), key=lambda kv: kv[1])[0] if by_category else None

    is_first_retrain = previous_weights is None
    explanations: List[RetrainExplanation] = []
    for key, label in _KPI_LABELS_PT.items():
        current = float(current_weights.get(key) or 0.0)
        prev = float((previous_weights or {}).get(key) or 0.0)
        if is_first_retrain or prev == 0:
            # First retrain has no baseline to compare against; report
            # zero delta rather than +100% so the audit text doesn't
            # invent movement that didn't happen.
            delta_pct = 0.0
        else:
            delta_pct = (current - prev) / prev * 100.0
        direction = _classify_direction(delta_pct)
        explanations.append(RetrainExplanation(
            kpi=key,
            label=label,
            delta_pct=round(delta_pct, 2),
            direction=direction,
            dominant_category=dominant,
            pairs_used=pairs_used,
            human_text=_render_human_text(
                label=label,
                direction=direction,
                delta_pct=delta_pct,
                pairs_used=pairs_used,
                dominant_category=dominant,
            ),
        ))
    return explanations


__all__ = [
    "RetrainExplanation",
    "build_retrain_explanations",
]
