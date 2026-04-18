"""
ProdPlan ONE — CPO v4 Fitness
==============================

Multi-objective weighted-sum fitness. Lower is better.

Objectives:
- Makespan (hours)                 — weight 1.0
- Total tardiness (hours)          — weight 10.0
- Setup count                       — weight 0.5
- **Quality risk** (Sprint I.3)     — weight default 0 (opt-in);
  pass a `quality_risk_predictor` in `FitnessConfig` to wire
  `QualityRiskModel` from Sprint H. Each scheduled op is scored and the
  mean P(error) is multiplied by `w_quality_risk`. A per-op probability
  above `quality_risk_hard_threshold` (default 0.4) contributes an
  additional hard penalty to strongly discourage unsafe assignments.
- Safety-net penalty                — weight 1e6 when candidate regresses
  vs. baseline (see `safety_net.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# A predictor takes a list of feature dicts (one per scheduled op) and
# returns a list of P(error) floats in [0, 1]. Callers adapt Sprint H's
# `QualityRiskModel.predict_proba_batch` via a thin lambda.
QualityRiskPredictor = Callable[[List[Dict[str, Any]]], List[float]]


@dataclass
class FitnessConfig:
    w_makespan: float = 1.0
    w_tardiness: float = 10.0
    w_setups: float = 0.5
    w_quality_risk: float = 0.0  # off by default — requires a predictor
    safety_penalty: float = 1e6

    # Sprint I.3 — quality risk hook
    quality_risk_predictor: Optional[QualityRiskPredictor] = None
    quality_risk_hard_threshold: float = 0.4
    quality_risk_hard_penalty: float = 100.0

    # Cached feature extractor — filled at config creation to avoid
    # rebuilding the dict per-op at hot path time.
    _feature_extractor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = field(
        default=None, repr=False
    )


def compute_fitness(schedule: Dict[str, Any], config: Optional[FitnessConfig] = None) -> float:
    """
    Compute a single scalar from a schedule result dict.

    Expected keys (all optional — missing → 0):
      makespan_hours, total_tardiness_hours, setups, quality_risk,
      safety_violated (bool), operations (list — used by the predictor).

    When `config.quality_risk_predictor` is set:
    1. Build a feature dict for each scheduled op (via the extractor or
       default projector).
    2. Call the predictor → list of P(error).
    3. Mean P(error) * w_quality_risk is added to the fitness.
    4. Each op with P(error) above `hard_threshold` triggers an extra
       `hard_penalty * w_quality_risk` (discourages unsafe assignments
       even when the weighted average looks fine).
    Predictor failures never crash the GA — they log and fall through.
    """
    cfg = config or FitnessConfig()

    fitness = 0.0
    fitness += cfg.w_makespan * float(schedule.get("makespan_hours", 0))
    fitness += cfg.w_tardiness * float(schedule.get("total_tardiness_hours", 0))
    fitness += cfg.w_setups * float(schedule.get("setups", 0))

    # Quality risk: prefer per-op prediction (Sprint I.3) when wired,
    # else fall back to a scalar the caller may have stored under "quality_risk".
    risk_scalar = float(schedule.get("quality_risk", 0))
    if cfg.quality_risk_predictor is not None and cfg.w_quality_risk > 0:
        per_op = _predict_risks_safe(cfg, schedule)
        if per_op:
            mean_risk = sum(per_op) / len(per_op)
            fitness += cfg.w_quality_risk * mean_risk
            hard_hits = sum(1 for r in per_op if r >= cfg.quality_risk_hard_threshold)
            if hard_hits:
                fitness += cfg.w_quality_risk * cfg.quality_risk_hard_penalty * hard_hits
        else:
            # Predictor unavailable this run — use the scalar fallback
            fitness += cfg.w_quality_risk * risk_scalar
    else:
        fitness += cfg.w_quality_risk * risk_scalar

    if schedule.get("safety_violated"):
        fitness += cfg.safety_penalty

    return fitness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_op_features_for_risk(op_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Default projector from a `ScheduledOp`-as-dict to the feature shape
    `QualityRiskModel.predict_proba` expects. Callers can override by
    passing their own extractor via `FitnessConfig._feature_extractor`.

    Missing fields fall back to neutral defaults so a bare schedule (no
    phase_id, no model_id) still gets a valid prediction row (possibly
    inaccurate, but non-crashing).
    """
    return {
        "modelo_id": str(op_record.get("model_id") or op_record.get("modelo_id") or ""),
        "fase_id": str(op_record.get("phase_id") or op_record.get("fase_id") or ""),
        "team_size": int(len(op_record.get("workers", [])) or 1),
        "mold_pocket_count": int(op_record.get("mold_pocket_count", 1) or 1),
        "phase_error_rate": float(op_record.get("phase_error_rate", 0.0) or 0.0),
        "queue_depth": int(op_record.get("queue_depth", 0) or 0),
    }


def _predict_risks_safe(cfg: FitnessConfig, schedule: Dict[str, Any]) -> List[float]:
    """Run the predictor, swallowing any exception so the GA keeps moving."""
    ops = schedule.get("operations") or []
    if not ops:
        return []
    extractor = cfg._feature_extractor or build_op_features_for_risk
    try:
        feature_rows = [extractor(op) for op in ops]
        probs = cfg.quality_risk_predictor(feature_rows)
        return [float(p) for p in probs]
    except Exception:
        # Fitness must never raise — log-and-zero is safer than crashing a GA.
        import logging
        logging.getLogger(__name__).warning(
            "quality_risk_predictor failed — falling back to zero-risk",
            exc_info=True,
        )
        return []
