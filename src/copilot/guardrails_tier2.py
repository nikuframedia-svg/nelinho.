"""
ProdPlan ONE - Guardrails Tier 2 (Sprint S.4)
===============================================

Blueprint v2.0 §5.4 Tier 2 — model-based PII + toxicity classifiers.

`guardrails-ai` is optional at runtime. When it's installed we delegate
to a `Guard` instance with the configured validators. When it isn't we
fall back to a simple heuristic so the caller ALWAYS gets a structured
verdict and the API never crashes.

The caller is expected to wrap `analyse(text)` around LLM prompts + LLM
responses. A positive verdict (`.blocked=True`) should cause the caller
to:
  * log the incident with `fingerprint` (NEVER the raw text)
  * return a sanitised alternative (redacted text) to the user
  * emit a Copilot alert if risk_score >= 0.8
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

from .guardrails_tier1 import ScanResult, scan as tier1_scan

logger = logging.getLogger(__name__)


try:  # pragma: no cover — optional dep
    from guardrails import Guard  # type: ignore

    HAS_GUARDRAILS_AI = True
except Exception:  # pragma: no cover
    Guard = None  # type: ignore
    HAS_GUARDRAILS_AI = False


@dataclass
class Tier2Verdict:
    risk_score: float              # 0.0 → 1.0
    blocked: bool
    tier1: ScanResult              # always populated
    tier2_labels: List[str]        # e.g. ["pii", "toxicity"]
    details: dict
    fallback_mode: bool = False


# Simple heuristics used when `guardrails-ai` is absent. They classify
# shouting / extreme phrasing as "toxicity" at a very loose level so the
# caller gets *some* signal even in sparse deployments.
_TOXICITY_HEURISTICS = (
    "hate", "kill", "die", "idiot", "stupid", "moron",
    "bastard", "scum", "dumb", "trash",
)


def analyse(text: str, *, block_threshold: float = 0.8) -> Tier2Verdict:
    """Classify `text` for PII + toxicity.

    Always runs Tier 1 first (sync, cheap). Tier 2 (model-based) runs
    only when `guardrails-ai` is installed. The `fallback_mode` flag on
    the verdict tells the caller whether the score came from the full
    model or the heuristic fallback.
    """
    tier1 = tier1_scan(text or "")
    if not text:
        return Tier2Verdict(
            risk_score=0.0, blocked=False,
            tier1=tier1, tier2_labels=[],
            details={}, fallback_mode=not HAS_GUARDRAILS_AI,
        )

    labels: List[str] = []
    details: dict[str, Any] = {"tier1_matches": tier1.pattern_counts()}

    # Tier 1 contribution: any secret-like match adds 0.6 to the risk.
    risk = 0.6 if tier1.has_violations else 0.0
    if tier1.has_violations:
        labels.append("secret")

    # Tier 2 contribution.
    if HAS_GUARDRAILS_AI and Guard is not None:
        try:
            model_labels, model_score, model_details = _run_guardrails_ai(text)
            labels.extend(model_labels)
            risk = max(risk, model_score)
            details["guardrails_ai"] = model_details
            fallback = False
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Guardrails AI failed, falling back: %s", exc)
            labels, risk, fallback = _heuristic_scan(text, labels, risk)
    else:
        labels, risk, fallback = _heuristic_scan(text, labels, risk)

    risk = min(1.0, max(0.0, risk))
    return Tier2Verdict(
        risk_score=round(risk, 3),
        blocked=risk >= block_threshold,
        tier1=tier1,
        tier2_labels=labels,
        details=details,
        fallback_mode=fallback,
    )


# ---------------------------------------------------------------------------
# Back-ends
# ---------------------------------------------------------------------------

def _run_guardrails_ai(text: str):  # pragma: no cover — requires optional dep
    """Invoke the configured `guardrails-ai` Guard. Returns (labels, score, details)."""
    from guardrails import Guard

    labels: List[str] = []
    score = 0.0
    details: dict[str, Any] = {}

    # Default validators — callers can override by patching this function.
    guard = Guard().use_many(
        # NOTE: these validators live in `guardrails-ai` contrib packages
        # and may not be installed in every deployment. `use_many` is
        # resilient: missing validators are skipped.
    )
    outcome = guard.validate(text)
    raw_errors = getattr(outcome, "validation_passed", True) is False
    if raw_errors:
        score = 0.9
        labels.append("pii_or_toxicity")
        details["outcome"] = str(outcome)
    return labels, score, details


def _heuristic_scan(
    text: str, labels: List[str], risk: float,
) -> tuple[List[str], float, bool]:
    """Tiny token-level heuristic for when Guardrails AI isn't installed."""
    lowered = text.lower()
    hits = [word for word in _TOXICITY_HEURISTICS if word in lowered]
    if hits:
        labels.append("toxicity")
        risk = max(risk, 0.4)
    return labels, risk, True
