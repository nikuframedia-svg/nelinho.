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
from statistics import mean
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
    # Q.115.X7 — re-balance (soma=1.0):
    #   setup 0.15→0.10 (−0.05) + throughput 0.15→0.10 (−0.05)
    #   + novo revenue_target_alignment=0.10 (+0.10) → delta net 0.
    # Pesos resultantes: 0.20+0.25+0.15+0.10+0.10+0.10+0.10 = 1.00.
    w_v2_setup_time: float = 0.10
    w_v2_quality_risk: float = 0.10
    w_v2_throughput_eur_day: float = 0.10
    w_v2_revenue_target_alignment: float = 0.10

    # ── Q.115.X7 — target diário de faturação (carregado do DB no engine) ──
    # None = sem target configurado; score de alinhamento passa a 1.0 (neutro).
    daily_revenue_target_eur: Optional[float] = None

    # ── Sprint P.3 — truck consolidation penalty (Blueprint PL14) ──────
    truck_consolidation_weight: float = 0.0      # disabled until transport batches exist
    truck_consolidation_tolerance_h: float = 12.0

    # ── Sprint E.4 — Camada 1 learned-rule enforcement ────────────────
    # When non-empty, `compute_fitness` adds the penalty computed by
    # `src.plan.cpo.preference_adapter.compute_preference_penalty`.
    # Callers typically copy this list from `FactoryState.preference_
    # rules` at engine-construction time so the GA fitness loop doesn't
    # hit the DB per evaluation.
    preference_rules: List[Dict[str, Any]] = field(default_factory=list)

    # ── Sprint Q.13.E E.1 — Capacity 1.5× factor for high-rework phases ──
    # Plan v4 §3.3: NELO's Lixagem água, Pintura Acab and Lixagem polim
    # phases run at 49.2% / 42.4% / 41.3% historical error rate. Without
    # capacity-correction the GA over-promises throughput on these
    # phases — a finished schedule that *physically* fits in 200h
    # actually consumes ~300h once rework loops are factored in. We
    # add an extra "rework capacity" term to fitness equal to
    # ``(rework_capacity_factor - 1) × Σ duration_h`` for ops whose
    # phase has ``error_rate >= rework_error_threshold``. Same units as
    # makespan (hours), so the legacy ``w_makespan`` already weights it
    # correctly; v2 mode normalises against ``_NORM_MAKESPAN_H``.
    #
    # Defaults are off (factor=1.0) so existing tests that hand-craft
    # FitnessConfig don't shift. The engine constructor flips factor to
    # 1.5 when the FactoryState carries any non-empty error_rate map,
    # picking up the wiring automatically once Sprint Q.8's
    # `historical_error_rates` populates.
    phase_error_rates: Dict[str, float] = field(default_factory=dict)
    rework_error_threshold: float = 0.40
    rework_capacity_factor: float = 1.0

    # ── Sprint I.5 — Causal entropy (flexibility preservation) ────────
    # Shannon-entropy penalty over the load distribution across
    # machines / workers / moulds. A concentrated plan pays the
    # penalty; a spread one rides free. Blueprint v2.0 §31 pegs the
    # weight at 0.05 so it nudges tie-breaks without dominating any
    # first-order cost term. Set to 0.0 to disable entirely (tests
    # that predated this change keep their exact fitness).
    w_causal_entropy: float = 0.05

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

    # Sprint E.4 — Camada 1 preference enforcement. Adds a bounded
    # soft penalty for each confirmed rule the schedule violates.
    if cfg.preference_rules:
        try:
            from src.plan.cpo.preference_adapter import compute_preference_penalty
            fitness += compute_preference_penalty(schedule, cfg.preference_rules)
        except Exception as exc:  # pragma: no cover — never let the hook crash fitness
            # Sprint Q.7 Fase 4 — was bare `pass`. Hot path: keep
            # graceful but log under DEBUG so silent learning rule bugs
            # surface during diagnosis.
            import logging as _l
            _l.getLogger(__name__).debug(
                "fitness preference_penalty failed: %s", exc,
            )

    # Sprint I.5 — causal-entropy penalty. Cheap (single pass over ops)
    # so it lives in the hot path. Guarded so a zero weight is a true
    # no-op and a buggy schedule can't take the fitness function down.
    if cfg.w_causal_entropy > 0:
        try:
            from src.plan.cpo.causal_entropy import causal_entropy_penalty
            fitness += cfg.w_causal_entropy * causal_entropy_penalty(schedule)
        except Exception as exc:  # pragma: no cover — defensive
            # Sprint Q.7 Fase 4 — was bare `pass`. Best-effort entropy
            # term; log under DEBUG.
            import logging as _l
            _l.getLogger(__name__).debug(
                "fitness causal_entropy_penalty failed: %s", exc,
            )

    # Sprint Q.13.E E.1 — capacity stolen by rework on high-error
    # phases. Same units as makespan (hours), priced via
    # `_NORM_MAKESPAN_H` in v2 mode and `cfg.w_makespan` in legacy mode.
    rework_h = _rework_penalty_hours(schedule, cfg)
    if rework_h > 0:
        if cfg.use_v2_weights:
            # Treat as additional normalised makespan with the same weight.
            ref = _NORM_MAKESPAN_H
            fitness += cfg.w_v2_makespan * max(0.0, min(1.0, rework_h / ref))
        else:
            fitness += cfg.w_makespan * rework_h

    if schedule.get("safety_violated"):
        fitness += cfg.safety_penalty

    return fitness


def _rework_penalty_hours(schedule: Dict[str, Any], cfg: FitnessConfig) -> float:
    """Sprint Q.13.E E.1 — capacity stolen by rework on high-error phases.

    Returns 0.0 when the factor is at unity (default) or no phase
    breaches the threshold. The cost is calibrated in hours so callers
    can fold it directly into a makespan-weighted term without rescaling.
    """
    if cfg.rework_capacity_factor <= 1.0:
        return 0.0
    rates = cfg.phase_error_rates
    if not rates:
        return 0.0
    threshold = cfg.rework_error_threshold
    extra_factor = cfg.rework_capacity_factor - 1.0

    ops = schedule.get("operations") or []
    total_h = 0.0
    for op in ops:
        phase_id = op.get("phase_id")
        if not phase_id:
            continue
        rate = rates.get(str(phase_id))
        if rate is None or float(rate) < threshold:
            continue
        duration_min = float(op.get("duration_minutes") or 0)
        if duration_min <= 0:
            continue
        total_h += extra_factor * (duration_min / 60.0)
    return total_h


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

    # Q.115.X7 — alinhamento com target diário (negado: score mais alto = fitness menor)
    revenue_align_score = _revenue_target_alignment(schedule, cfg)

    fitness = (
        cfg.w_v2_makespan * norm_makespan
        + cfg.w_v2_tardiness_transport * norm_tardy
        + cfg.w_v2_idle_operators * norm_idle
        + cfg.w_v2_setup_time * norm_setups
        + cfg.w_v2_quality_risk * mean_risk
        - cfg.w_v2_throughput_eur_day * norm_throughput  # negado: throughput maior → fitness menor
        - cfg.w_v2_revenue_target_alignment * revenue_align_score  # negado: alinhamento maior → fitness menor
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


def _aggregate_throughput_by_day(schedule: Dict[str, Any]) -> Dict[str, float]:
    """Agrega throughput €/dia do schedule.

    Lê `throughput_by_day` (dict data→€) se presente; caso contrário usa
    `throughput_eur_day` (valor médio único) como substituto para um único dia.
    NÃO lê CoeficienteX directamente — trabalha só sobre agregados já calculados.
    """
    by_day: Dict[str, float] = schedule.get("throughput_by_day") or {}
    if by_day:
        return {k: float(v) for k, v in by_day.items() if float(v) >= 0}
    # Fallback: usa o valor médio como representante de um único "dia"
    avg = float(schedule.get("throughput_eur_day") or 0)
    if avg > 0:
        return {"_avg": avg}
    return {}


def _revenue_target_alignment(schedule: Dict[str, Any], cfg: FitnessConfig) -> float:
    """Score [0, 1] que mede alinhamento com o target diário de faturação.

    Q.115.X7 — soft objective. NÃO usa CoeficienteX directamente;
    trabalha sobre `throughput_by_day` / `throughput_eur_day` já calculados.

    Sem target configurado (cfg.daily_revenue_target_eur is None) devolve
    1.0 — score neutro, não penaliza nem premeia.

    Score = max(0, 1 - 2 * avg_dev_pct) onde avg_dev_pct é a média das
    desvios percentuais absolutos por dia relativamente ao target.
    Decresce linearmente: 0% desvio → 1.0; 50% desvio → 0.0; >50% → 0.0.
    """
    if cfg.daily_revenue_target_eur is None:
        return 1.0

    target = float(cfg.daily_revenue_target_eur)
    if target <= 0:
        return 1.0

    eur_per_day = _aggregate_throughput_by_day(schedule)
    if not eur_per_day:
        # Sem dados → desvio máximo (score 0)
        return 0.0

    deviations_pct = [
        abs(day_eur - target) / target
        for day_eur in eur_per_day.values()
    ]
    avg_dev_pct = mean(deviations_pct)
    score = max(0.0, 1.0 - 2.0 * avg_dev_pct)
    return score


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
