"""
ProdPlan ONE - Default Tenant Configuration Seeds (Sprint L.4)
===============================================================

Canonical defaults that every tenant starts with. Values align with Blueprint
v2.0 — CPO fitness weights, Trust Index gates, mold maintenance thresholds,
throughput €/dia targets, queue time, etc. Edit this file when the blueprint
changes; the seeder is idempotent and only writes keys that don't already
exist for the tenant.

The `CATEGORY::KEY` identifiers are referenced throughout the code (Sprints
AA, M, N, O, P, Q, R). Keep names stable.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Schema: list of tuples (category, key, value, data_type, note)
# ---------------------------------------------------------------------------

ConfigSeed = tuple[str, str, Any, str, str]

DEFAULT_SEEDS: list[ConfigSeed] = [
    # ───────────────────────── governance / write-gate ──────────────────────
    ("governance", "auto_approval.reschedule_order.enabled", False, "bool",
     "WG07 — auto-approve cheap schedule changes when risk is low"),
    ("governance", "auto_approval.reschedule_order.risk_ceiling", "LOW", "string",
     "Only LOW-risk decisions auto-approve when enabled"),
    ("governance", "auto_approval.stock_adjustment.enabled", False, "bool", ""),
    ("governance", "auto_approval.stock_adjustment.risk_ceiling", "LOW", "string", ""),
    ("governance", "auto_approval.model_promotion.enabled", True, "bool", ""),
    ("governance", "auto_approval.model_promotion.risk_ceiling", "LOW", "string", ""),
    ("governance", "timeline.hide_low_risk_default", False, "bool",
     "WG08 — anti-approval-fatigue: hide LOW risk by default in timeline"),
    ("governance", "timeline.max_per_user_shown", 25, "int",
     "WG08 — cap items visible per reviewer to avoid overwhelm"),

    # ───────────────────────── trust index (Sprint AA) ──────────────────────
    ("trust", "weights.completeness", 0.15, "float", ""),
    ("trust", "weights.validity", 0.20, "float", ""),
    ("trust", "weights.freshness", 0.15, "float", ""),
    ("trust", "weights.consistency", 0.20, "float", ""),
    ("trust", "weights.provenance", 0.15, "float", ""),
    ("trust", "weights.anomaly", 0.10, "float", ""),
    ("trust", "weights.evidence", 0.05, "float", ""),
    ("trust", "gates.solver_suggestion_only", 0.50, "float",
     "Blueprint v2.0 §4.5 — below 0.50, solver runs in suggestion mode only"),
    ("trust", "gates.use_p90_durations", 0.60, "float",
     "Below 0.60, use P90 durations (larger buffers)"),
    ("trust", "gates.auto_reorder", 0.70, "float", "Below 0.70, disable automatic reorder"),
    ("trust", "gates.auto_commit", 0.75, "float", "Below 0.75, no auto-commit (human must approve)"),
    ("trust", "gates.quality_disposition", 0.80, "float", "Below 0.80, block quality disposition"),
    ("trust", "freshness.tau_seconds_curated", 86400.0, "float",
     "Freshness time-constant tau for curated data (1 day)"),
    ("trust", "consistency.kappa", 2.0, "float", "Z-score softening for consistency"),

    # ───────────────────────── planning / CPO v4.0 ──────────────────────────
    ("planning", "cpo.pop_size", 100, "int", "Blueprint v2.0 §5.5 — GA population"),
    ("planning", "cpo.gen_count", 200, "int",
     "Blueprint v2.0 — GA generations (was 50 in Sprint F; v2.0 requires 200)"),
    ("planning", "cpo.total_budget_s", 60.0, "float",
     "Target end-to-end CPO cascade budget"),
    ("planning", "cpo.greedy_budget_s", 2.0, "float",
     "Greedy 8-phase baseline budget"),
    ("planning", "cpo.ga_budget_s", 30.0, "float", ""),
    ("planning", "cpo.mapelites_budget_s", 5.0, "float", ""),
    ("planning", "cpo.cpsat_budget_s", 15.0, "float", "CP-SAT L-RHO rolling horizon"),
    ("planning", "cpo.workforce_budget_s", 3.0, "float",
     "Hungarian workforce assignment budget"),
    ("planning", "cpo.use_frrmab", True, "bool", ""),
    ("planning", "cpo.use_mapelites", True, "bool", ""),
    ("planning", "cpo.use_surrogate", False, "bool",
     "Requires ≥20 real samples before enabling"),
    ("planning", "cpo.use_cpsat_lrho", True, "bool",
     "Sprint P.10 — Rolling Horizon L-RHO (ex-deferred I.2)"),

    # Fitness weights (Blueprint v2.0 §5.5 — normalised, sum = 1.0)
    ("planning", "fitness.weight.makespan", 0.20, "float", ""),
    ("planning", "fitness.weight.tardiness_transport", 0.25, "float",
     "Transport dates are king"),
    ("planning", "fitness.weight.idle_operators", 0.15, "float", ""),
    ("planning", "fitness.weight.setup_time", 0.15, "float", ""),
    ("planning", "fitness.weight.quality_risk", 0.10, "float", ""),
    ("planning", "fitness.weight.throughput_eur_day", 0.15, "float",
     "Negated internally so throughput maximisation reduces fitness"),

    # Hard penalties
    ("planning", "fitness.quality_hard_threshold", 0.40, "float",
     "Sprint I.3 — P(error)>threshold incurs hard_penalty per op"),
    ("planning", "fitness.quality_hard_penalty", 100.0, "float", ""),
    ("planning", "fitness.truck_consolidation_weight", 2.0, "float",
     "Sprint P.3 — penalty for spreading same-batch ops over time"),
    ("planning", "fitness.truck_consolidation_tolerance_h", 12.0, "float", ""),

    # Scheduling direction + transport
    ("planning", "scheduler.direction", "backward", "string",
     "PL14 — default backward from transport_date"),
    ("planning", "transport.default_batch_size", 50, "int", "CG11 — 50 barcos/camião"),
    ("planning", "transport.delivery_buffer_h", 24.0, "float",
     "Hours before transport_date the order must be ready"),

    # Queue time and buffers (v2.0 data)
    ("planning", "queue_time.median_h", 5.2, "float",
     "PL22 — mediana 5.2h entre fases consecutivas"),
    ("planning", "queue_time.p90_h", 69.2, "float", ""),
    ("planning", "buffer.post_desmolde_h", 4.0, "float",
     "PL21 — buffer após Desmolde (ponto QC de facto)"),

    # Laminagem dual-resource (WF11)
    ("planning", "laminagem.require_pair", True, "bool",
     "WF11 — Laminagem standard sempre 2 workers (88.5% das operações "
     "históricas em FuncionariosFaseOrdemFabrico). NÃO usar CoeficienteX "
     "como critério — é prémio monetário (€), não tempo."),
    ("planning", "laminagem.require_chefe", True, "bool",
     "Pair must include an experienced worker (chefe)"),

    # Mold pocket count hard cap (v2.0: 7 pockets max observed)
    ("planning", "mold.max_pocket_count", 7, "int", ""),

    # Routing — 61 unique routing patterns by sequence (Blueprint v2.0 §3.1).
    # 39 if ignoring order, 61 when preserving phase sequence. The CPO uses
    # 61 because ordering matters for scheduling. Count updated from 50 in
    # Sprint A after the curated ingest re-sequenced the patterns.
    ("planning", "routing.templates.count", 61, "int",
     "PL08/CG07 — 61 padrões únicos de routing por sequência (v2.0 §3.1)"),

    # Replan triggers (PL16)
    ("planning", "replan.on_capacity_change", True, "bool", ""),
    ("planning", "replan.on_routing_change", True, "bool", ""),

    # MAP-Elites 3D grid (Sprint P.11)
    ("planning", "mapelites.bins.lam_utilization", 10, "int",
     "v2.0 §5.5 — X axis bins (utilização laminagem 0-100%)"),
    ("planning", "mapelites.bins.tardiness_transport", 10, "int",
     "Y axis bins (atraso máximo vs transporte 0 a +14 dias)"),
    ("planning", "mapelites.bins.idle_pct", 5, "int",
     "Z axis bins (operadores idle 0-50%)"),
    ("planning", "mapelites.representatives_default", 8, "int",
     "WG10 — alternativas mostradas no Timeline"),

    # Surrogate
    ("planning", "surrogate.threshold_factor", 1.2, "float",
     "Skip candidates >1.2x worse than best-known"),
    ("planning", "surrogate.retrain_every", 50, "int",
     "Re-train surrogate every N real GA evaluations"),
    ("planning", "surrogate.min_samples_enable", 20, "int", ""),

    # ───────────────────────── supply / stock ───────────────────────────────
    ("supply", "safety_multiplier", 1.0, "float",
     "MR05 — multiplier on calculated reorder points"),
    ("supply", "stockout_critical_days", 3, "int",
     "Days-to-stockout below which MATERIAL_STOCKOUT_IMMINENT fires"),
    ("supply", "adjust.auto_approve_threshold_qty", 5.0, "float",
     "|qty_delta| above this requires governance approval (MR06 / ST01)"),

    # ───────────────────────── quality + mold ──────────────────────────────
    ("quality", "risk_alert_threshold", 0.40, "float",
     "QA07 — emit preventive alert when P(error) > threshold"),
    ("quality", "rework_buffer_pct.sanding_water", 0.20, "float",
     "QA11 — buffer 20% pós Lixagem água (19.149 retornos histórico)"),
    ("quality", "rework_buffer_pct.sanding_polish", 0.20, "float",
     "QA11 — buffer 20% pós Lixagem polimento (16.221 retornos)"),
    ("quality", "rework_buffer_pct.painting_finishing", 0.18, "float",
     "QA11 — buffer 18% pós Pintura Acabamento (12.826 retornos)"),
    ("quality", "skill_bottleneck_threshold", 25, "int",
     "WF12 — fases com < N workers aptos flagged as skill bottleneck "
     "(Pintura=22, Colagem Golas=13, Desmolde=16)"),

    # Sprint Q.8 (CEO confirmation 2026-04-26): NELO has no numeric
    # maintenance policy — molds go to maintenance after visual inspection.
    # Default 0 disables the MOLD_MAINT_DUE auto-alert; the scheduler and
    # health calculator keep working. Tenants can override to a positive
    # integer if they later adopt a cycle-based policy. The manual fluxo
    # is exposed via POST /v1/molds/{id}/maintenance.
    ("mold", "maintenance_threshold_cycles", 0, "int",
     "QA10/CG12/AL08 — cycles before MOLD_MAINT_DUE alert. ≤0 disables "
     "(NELO default). Override per-tenant if a numeric policy exists."),
    ("mold", "health_weight.cycles", 0.40, "float", ""),
    ("mold", "health_weight.defects_90d", 0.20, "float", ""),
    ("mold", "health_weight.days_since_maint", 0.20, "float", ""),
    ("mold", "health_weight.rework_rate", 0.20, "float", ""),
    ("mold", "health.red_threshold", 40, "int",
     "Health score below this flags the mold RED"),
    ("mold", "health.yellow_threshold", 70, "int",
     "Health score below this flags YELLOW"),

    # ───────────────────────── cost / throughput ────────────────────────────
    ("cost", "target.throughput_eur_day_min", 30000.0, "currency",
     "CS05 — Blueprint v2.0 §2.8 target €30K/dia"),
    ("cost", "target.throughput_eur_day_max", 35000.0, "currency", ""),
    ("cost", "margin_default", 1.40, "float",
     "Fallback margin when ProductPricing.sale_value_default_eur is missing"),
    ("cost", "target.unit_value_eur", 2350.0, "currency",
     "Sprint Q.8 — €/order used for backlog estimates "
     "(€35K/day ÷ 14.9 boats/day). Lift to ProductPricing in Q.9."),

    # ───────────────────────── copilot / llm ────────────────────────────────
    ("copilot", "rate_limit.per_hour", 60, "int", ""),
    ("copilot", "rate_limit.per_day", 300, "int", ""),

    ("llm", "backend", "ollama", "string",
     "Sprint S.2 — flip to 'vllm' when vLLM container is ready"),
    ("llm", "ollama.model", "gemma4:e4b", "string", ""),
    ("llm", "ollama.num_ctx", 8192, "int", ""),
    ("llm", "ollama.temperature", 0.1, "float", ""),
    ("llm", "ollama.keep_alive", "30m", "string", ""),
    ("llm", "vllm.base_url", "http://vllm:8000", "string", ""),
    ("llm", "vllm.model", "Qwen2.5-7B-Instruct-AWQ", "string", ""),

    # ───────────────────────── factory map ──────────────────────────────────
    ("factory_map", "snapshot.cache_ttl_seconds", 30, "int", ""),
    ("factory_map", "shortage.horizon_days_default", 14, "int", ""),
    ("factory_map", "projection.days_ahead_default", 7, "int", ""),

    # ───────────────────────── workforce ────────────────────────────────────
    ("workforce", "skill_tier.junior_max_months", 5, "int",
     "WF05 — tier boundary: junior < 5 months"),
    ("workforce", "skill_tier.mid_max_months", 12, "int",
     "WF05 — tier boundary: mid < 12 months"),
    ("workforce", "shift.default_hours_per_day", 8.0, "float",
     "95% turno único manhã per blueprint §2.8"),
]


def iter_seeds() -> list[ConfigSeed]:
    """Return a shallow copy of the canonical seed list."""
    return list(DEFAULT_SEEDS)


async def seed_tenant_defaults(
    service,  # TenantConfigService — forward-ref avoids circular import
    user_id=None,
    skip_existing: bool = True,
) -> int:
    """Write every default seed that is not yet present for the tenant.

    Returns the number of rows written. Safe to call repeatedly — with
    `skip_existing=True` (the only supported mode in L.4), existing keys are
    left untouched.
    """
    if not skip_existing:
        raise NotImplementedError(
            "Non-idempotent seeding is intentionally disabled. Use "
            "TenantConfigService.set() directly to override individual keys."
        )

    import logging as _logging
    _seed_logger = _logging.getLogger(__name__)

    written = 0
    for category, key, value, data_type, _note in DEFAULT_SEEDS:
        try:
            await service.get(category, key)
            # exists → skip
            continue
        except Exception as exc:
            # Sprint Q.7 Fase 4 — was bare `pass`. The intent is "key
            # not yet seeded → write below". Log under DEBUG so DB-level
            # failures (vs. real "not found") still surface.
            _seed_logger.debug(
                "seed_tenant_defaults: get(%s.%s) raised %s — assuming missing, will write",
                category, key, exc,
            )
        await service.set(
            category=category,
            key=key,
            value=value,
            user_id=user_id,
            data_type=data_type,
        )
        written += 1
    return written
