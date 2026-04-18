"""
ProdPlan ONE — ML Model Promotion via Governance
=================================================

Bridge between `ModelRegistry.save()` and `GovernanceService.propose_decision()`.

Every trained artifact should flow through a `DecisionRun` before becoming
active. This module wraps that flow so a `RetrainJob` can simply call
`propose_promotion(artifact, metrics)` and receive the decision id back.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from src.governance.service import GovernanceService
from src.ml.config import get_config
from src.ml.models.orm import MLModelArtifact

logger = logging.getLogger(__name__)


DECISION_TYPE = "model_promotion"


async def propose_promotion(
    governance: GovernanceService,
    artifact: MLModelArtifact,
    baseline_metrics: Optional[Dict[str, Any]] = None,
    proposed_by: str = "system",
) -> Dict[str, Any]:
    """
    Create a `DecisionRun` proposing the promotion of `artifact`.

    The governance policy `model_promotion` decides whether approval is
    auto-granted or requires a human. Decision inputs include the new
    metrics and the baseline metrics (when available) so auditors can see
    the delta.
    """
    cfg = get_config()
    new_metrics = artifact.metrics or {}
    baseline = baseline_metrics or {}

    # Auto-approval heuristic (applied by governance policy):
    # WMAPE must improve vs. baseline AND the delta must be within bounds.
    new_wmape = _safe_float(new_metrics.get("wmape"))
    old_wmape = _safe_float(baseline.get("wmape"))
    wmape_delta: Optional[float] = None
    if new_wmape is not None and old_wmape is not None:
        wmape_delta = old_wmape - new_wmape  # positive when improvement

    expected_impact = {
        "wmape_delta": wmape_delta,
        "new_metrics": new_metrics,
        "baseline_metrics": baseline,
        "auto_promote_max_delta": cfg.auto_promote_max_wmape_delta,
    }

    decision = await governance.propose_decision(
        decision_type=DECISION_TYPE,
        title=f"Promote {artifact.model_name} v{artifact.version}",
        action_data={
            "model_name": artifact.model_name,
            "version": artifact.version,
            "artifact_id": str(artifact.id),
        },
        proposed_by=proposed_by,
        description=(
            f"Trained a new version of {artifact.model_name} "
            f"(v{artifact.version}, {artifact.training_samples} samples). "
            f"WMAPE: {new_wmape} (baseline: {old_wmape}, delta: {wmape_delta})."
        ),
        expected_impact=expected_impact,
        risk_level=_classify_risk(wmape_delta, cfg.auto_promote_max_wmape_delta),
    )
    logger.info(
        f"Proposed model_promotion decision {decision.get('id')} for "
        f"{artifact.model_name} v{artifact.version}"
    )
    return decision


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _classify_risk(wmape_delta: Optional[float], max_delta: float) -> str:
    if wmape_delta is None:
        return "medium"
    if wmape_delta <= 0:
        # New model is not better than baseline
        return "high"
    if wmape_delta > max_delta:
        # Improvement so large it deserves human scrutiny
        return "medium"
    return "low"
