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
    # Legacy Sprint E/I weights (kept for backward compat — unit tests rely on
    # the scalar form. Blueprint v2.0 normalised weights are in the `w_*_v2`
    # block below and activated via `use_v2_weights=True`.)
    #
    # Sprint C 4.2 F3 — these weights are INTENTIONALLY un-normalised and
    # operate on raw unit scales (hours for makespan/tardiness, count for
    # setups). The 10×/1×/0.5× ratio encodes the domain preference:
    #     * 1h of tardiness hurts 10× more than 1h of makespan — tardiness
    #       is a contract breach, makespan is a marginal utilisation cost.
    #     * 1 setup hurts half as much as 1h of makespan because setups
    #       are measured in units (integer count), not hours; the 0.5
    #       factor roughly normalises to "typical setup ~30min".
    #
    # Callers that want Blueprint v2.0 normalised (sum=1.0) weights flip
    # `use_v2_weights=True` and the `w_v2_*` block below drives fitness.
    w_makespan: float = 1.0
    w_tardiness: float = 10.0
    w_setups: float = 0.5
    # Sprint A F4 — was 0.0; raised to 0.10 (Blueprint v2.0 §5.5).
    # When no predictor is wired, `schedule["quality_risk_score"]` defaults
    # to 0, so the term is 0.10 × 0 = 0 and nothing changes. Once a Sprint H
    # predictor is attached via `quality_risk_predictor`, the weight is
    # already live without a second config change.
    w_quality_risk: float = 0.10
    safety_penalty: float = 1e6

    # Sprint I.3 — quality risk hook
    quality_risk_predictor: Optional[QualityRiskPredictor] = None
    quality_risk_hard_threshold: float = 0.4
    quality_risk_hard_penalty: float = 100.0

    # ── Sprint P.6 — Blueprint v2.0 normalised weights (sum = 1.0) ─────
    # When `use_v2_weights=True`, the legacy `w_makespan/w_tardiness/w_setups/
    # w_quality_risk` values are IGNORED and the normalised set below drives
    # fitness. `tardiness_transport` replaces the old `tardiness` term to mark
    # that Blueprint v2.0 prioritises transport-date compliance specifically.
    use_v2_weights: bool = False
    w_v2_makespan: float = 0.20
    w_v2_tardiness_transport: float = 0.25
    w_v2_idle_operators: float = 0.15
    w_v2_setup_time: float = 0.15
    w_v2_quality_risk: float = 0.10
    w_v2_throughput_eur_day: float = 0.15

    # ── Sprint P.3 — truck consolidation penalty (Blueprint PL14) ──────
    truck_consolidation_weight: float = 0.0      # disabled until transport batches exist
    truck_consolidation_tolerance_h: float = 12.0

    # Cached feature extractor — filled at config creation to avoid
    # rebuilding the dict per-op at hot path time.
    _feature_extractor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = field(
        default=None, repr=False
    )

    # ── Sprint D.4 — Adaptive Weights (Camada 2) factory ─────────────────
    # Callers that want per-tenant learned weights go through this
    # classmethod instead of `FitnessConfig()`. The only thing that
    # changes is the four legacy scalar weights (w_makespan, w_tardiness,
    # w_setups, w_quality_risk); safety penalty, v2 normalised weights,
    # truck consolidation and the quality-risk hook stay on their
    # declared defaults. See
    # `src/governance/preference_learning/adaptive_weights.py`.
    @classmethod
    async def from_tenant_config(
        cls,
        session: "Any",  # AsyncSession — string-quoted to avoid an import at module top
        tenant_id: "Any",  # UUID
        **overrides: Any,
    ) -> "FitnessConfig":
        """Build a FitnessConfig with adaptive weights merged in.

        ``overrides`` lets callers pin individual fields (e.g.
        ``use_v2_weights=True``, or passing ``quality_risk_predictor``)
        without touching the adaptive lookup.

        Silent fallback: if the tenant has no adaptive weights row yet,
        this returns a config identical to ``FitnessConfig()``.
        """
        from src.governance.preference_learning import load_adaptive_weights

        adaptive = await load_adaptive_weights(session, tenant_id)
        merged = dict(adaptive)
        merged.update(overrides)
        return cls(**merged)


def compute_fitness(schedule: Dict[str, Any], config: Optional[FitnessConfig] = None) -> float:
    """Compute a single scalar from a schedule result dict.

    With `use_v2_weights=False` (default), applies Sprint E/I legacy weights:
      fit = w_makespan*makespan + w_tardiness*tardiness + w_setups*setups
          + w_quality_risk*risk + safety_penalty

    With `use_v2_weights=True` (Blueprint v2.0), applies normalised weights
    (sum=1.0) over normalised KPIs:
      fit = 0.20*norm_makespan + 0.25*norm_tardiness_transport
          + 0.15*norm_idle_operators + 0.15*norm_setup_time
          + 0.10*norm_quality_risk - 0.15*norm_throughput_eur_day

    In both modes the truck_consolidation_weight * (transport_penalty_h) is
    added when `schedule["truck_consolidation_penalty_h"]` is present.
    `safety_violated` always adds `safety_penalty`.
    """
    cfg = config or FitnessConfig()

    if cfg.use_v2_weights:
        fitness = _v2_fitness(schedule, cfg)
    else:
        fitness = _legacy_fitness(schedule, cfg)

    # Sprint P.3 — truck consolidation penalty (transport-batch spread hours)
    if cfg.truck_consolidation_weight > 0:
        penalty_h = float(schedule.get("truck_consolidation_penalty_h", 0) or 0)
        fitness += cfg.truck_consolidation_weight * penalty_h

    if schedule.get("safety_violated"):
        fitness += cfg.safety_penalty

    return fitness


def _legacy_fitness(schedule: Dict[str, Any], cfg: FitnessConfig) -> float:
    fitness = 0.0
    fitness += cfg.w_makespan * float(schedule.get("makespan_hours", 0))
    fitness += cfg.w_tardiness * float(schedule.get("total_tardiness_hours", 0))
    fitness += cfg.w_setups * float(schedule.get("setups", 0))

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
            fitness += cfg.w_quality_risk * risk_scalar
    else:
        fitness += cfg.w_quality_risk * risk_scalar
    return fitness


# Normalisation reference magnitudes — tuned for NELO scale (50-500 ops,
# 1-4 week horizon). Values far beyond these cap at 1.0 so runaway KPI
# values can't dominate fitness arithmetic.
_NORM_MAKESPAN_H = 1000.0
_NORM_TARDINESS_H = 500.0
_NORM_IDLE_H = 400.0
_NORM_SETUPS = 50.0
_NORM_THROUGHPUT_EUR_DAY = 35000.0


def _v2_fitness(schedule: Dict[str, Any], cfg: FitnessConfig) -> float:
    """Blueprint v2.0 §5.5 normalised multi-objective."""
    def _norm(value: float, ref: float) -> float:
        if ref <= 0:
            return 0.0
        return max(0.0, min(1.0, float(value) / ref))

    norm_makespan = _norm(schedule.get("makespan_hours", 0) or 0, _NORM_MAKESPAN_H)
    norm_tardy = _norm(
        schedule.get("total_tardiness_transport_hours",
                     schedule.get("total_tardiness_hours", 0)) or 0,
        _NORM_TARDINESS_H,
    )
    norm_idle = _norm(schedule.get("total_idle_hours", 0) or 0, _NORM_IDLE_H)
    norm_setups = _norm(schedule.get("setups", 0) or 0, _NORM_SETUPS)
    norm_throughput = _norm(
        schedule.get("throughput_eur_day", 0) or 0, _NORM_THROUGHPUT_EUR_DAY,
    )

    # Quality-risk: mean P(error) already normalised in [0,1].
    per_op = _predict_risks_safe(cfg, schedule) if cfg.quality_risk_predictor else []
    if per_op:
        mean_risk = sum(per_op) / len(per_op)
    else:
        mean_risk = float(schedule.get("quality_risk_mean", schedule.get("quality_risk", 0)) or 0)
    hard_hits = sum(1 for r in per_op if r >= cfg.quality_risk_hard_threshold)

    fitness = (
        cfg.w_v2_makespan * norm_makespan
        + cfg.w_v2_tardiness_transport * norm_tardy
        + cfg.w_v2_idle_operators * norm_idle
        + cfg.w_v2_setup_time * norm_setups
        + cfg.w_v2_quality_risk * mean_risk
        - cfg.w_v2_throughput_eur_day * norm_throughput  # negated: higher throughput → lower fitness
    )
    if hard_hits:
        fitness += cfg.quality_risk_hard_penalty * hard_hits * cfg.w_v2_quality_risk
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
