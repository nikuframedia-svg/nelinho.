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

    # ───────────────────────── routing (Sprint Q.9 Onda 3.6) ────────────────
    # Plan v4 §11.1 — routing templates editáveis. Phase-uses-mold and
    # default buffers come from here so the planner doesn't carry magic
    # numbers (replacing the regex in routing_resolver.py:277).
    ("routing", "phases.requires_mold",
     "LAMINAGEM,DESMOLDE,PINTURA_GEL_COAT,PREP_MOLDE", "string",
     "Comma-separated list of phase codes that need a mould slot. "
     "Override the regex inferrer in `_phase_uses_mold` once per tenant."),
    ("routing", "standards.buffer_factor", 2.0, "float",
     "Multiplier applied to FasesStandardModelos times when there is "
     "no historical data — guards against the 25× standard-vs-real drift."),
    ("routing", "ab_variant.enabled", True, "bool",
     "Sprint Q.9 — toggles the chromosome routing-variants A/B selector."),

    # ───────────────────────── alertas (Sprint Q.9 Onda 3.6) ────────────────
    # Plan §11.1 — every alert on/off + threshold + recipient is editable.
    ("alertas", "delivery_risk.window_days", 3, "int",
     "Days-of-late threshold to flip OTD into red."),
    ("alertas", "mold_health.threshold", 70, "int",
     "Mold health below this number triggers AL08 maintenance alert."),
    ("alertas", "shortage.window_days", 14, "int",
     "Forecast horizon for material shortage detection."),
    ("alertas", "default.severity", "warning", "string",
     "Fallback severity when an alert source omits one (info|warning|critical)."),
    ("alertas", "delivery.recipients_email", "", "string",
     "Comma-separated list of emails that receive delivery-risk alerts."),

    # ───────────────────────── learning rules (Sprint Q.9 Onda 3.6) ─────────
    # Plan §22-§26 — the manager toggles confidence thresholds + decides
    # how aggressively the detector promotes rules from `detected` to
    # `confirmed` automatically.
    ("learning_rules", "confidence.auto_confirm", 0.95, "float",
     "Rules above this confidence skip manual review (default conservative)."),
    ("learning_rules", "confidence.minimum", 0.70, "float",
     "Below this threshold a detected rule never reaches the operator."),
    ("learning_rules", "window.lookback_days", 30, "int",
     "Detector lookback window — match the nightly job in scheduler.py."),
    ("learning_rules", "auto_revert_after_days", 90, "int",
     "Confirmed rules auto-deactivate after this many days without reinforcement."),

    # ───────────────────────── rbac (Sprint Q.9 Onda 3.6) ───────────────────
    # Plan §11.1 last bullet — quem vê o quê. The full RBAC table lives
    # in the auth service; these defaults gate broad surfaces and let
    # the operator demote a screen without code changes.
    ("rbac", "roles.default", "operator", "string",
     "New users land in this role until promoted."),
    ("rbac", "approvals.require_role", "manager", "string",
     "Role required to approve write-gate decisions (manager|admin)."),
    ("rbac", "ceo_dashboard.allowed_roles", "ceo,manager", "string",
     "Comma-separated list of roles that can read /v1/profit/dashboard/*."),
    ("rbac", "config.editable_by", "admin", "string",
     "Role that can mutate ConfigStore keys (everyone else gets read-only UI)."),

    # ───────────────────────── system (Sprint Q.9 Onda 3.6) ─────────────────
    # Plan §11.1 — language, theme, formats, RBAC, relatórios.
    ("system", "language", "pt-PT", "string", "UI language code (pt-PT|en|de)."),
    ("system", "theme", "dark", "string", "UI theme (dark|light|auto)."),
    ("system", "format.date", "DD/MM/YYYY", "string", "Date format the UI renders."),
    ("system", "format.currency", "EUR", "string", "ISO currency code for prices and KPIs."),
    ("system", "report.daily_email_hour", 8, "int",
     "UTC hour the daily report is scheduled (0-23)."),

    # ───────────────────────── transporte (Sprint Q.9 Onda 3.6) ─────────────
    # Plan §11.1 transport — capacity + buffer + customer priority. The
    # transport_batch_service already reads tenant config; these are the
    # canonical keys it expects to find.
    ("transporte", "truck.capacity", 50, "int",
     "Boats per truck — CEO baseline. Moda histórica = 26."),
    ("transporte", "buffer.days_before_dispatch", 2, "int",
     "Days a finished boat can wait before a truck departs."),
    ("transporte", "regroup.by_client", True, "bool",
     "Suggest regrouping shipments by customer when ≥3 are split."),
    ("transporte", "completion.min_fill_ratio", 0.5, "float",
     "Trigger a fill-the-truck suggestion when a batch is below this fraction."),

    # ───────────────────── notifications (Onda 3 follow-up) ─────────────────
    # Plan §11.1 alertas → destinatários. `alertas` is the *what* (which
    # alert types fire); `notifications` is the *how* (which channels
    # carry them).
    ("notifications", "email.enabled", True, "bool",
     "Master switch for outbound email notifications."),
    ("notifications", "email.batch_window_minutes", 15, "int",
     "Coalesce non-critical alerts into batched emails on this cadence."),
    ("notifications", "slack.webhook_url", "", "string",
     "Slack incoming webhook for CRITICAL alerts. Empty = disabled."),
    ("notifications", "sms.enabled", False, "bool",
     "SMS for after-hours critical alerts. Disabled by default."),
    ("notifications", "quiet_hours.start", "22:00", "string",
     "Local time when non-critical channels go silent (HH:MM)."),
    ("notifications", "quiet_hours.end", "07:00", "string",
     "Local time when non-critical channels resume."),

    # ───────────────────── reports (Onda 3 follow-up) ───────────────────────
    # Plan §11.1 sistema — frequência de relatórios automáticos. Drives
    # the daily_feedback + future weekly digest jobs.
    ("reports", "daily.enabled", True, "bool",
     "Generate the daily ops report at the configured hour."),
    ("reports", "daily.hour_utc", 8, "int",
     "UTC hour the daily report job runs (0-23)."),
    ("reports", "weekly.enabled", True, "bool",
     "Send a weekly KPI digest every Monday."),
    ("reports", "format", "pdf", "string",
     "Export format for the dashboard: pdf | xlsx | both."),
    ("reports", "ceo.recipients", "", "string",
     "Comma-separated emails for the CEO digest. Empty = print only."),

    # ───────────────────── tablet (Onda 3 follow-up) ────────────────────────
    # Plan §10 — tablet operador (chão de fábrica). Single-purpose UI;
    # these knobs let the operator tune contrast/refresh without code.
    ("tablet", "refresh.seconds", 15, "int",
     "How often the tablet polls /v1/operador/queue."),
    ("tablet", "ui.font_scale", 1.0, "float",
     "Multiplier for default font size (1.0 = neutral, 1.25 = larger)."),
    ("tablet", "ui.kiosk_mode", True, "bool",
     "Hide navigation chrome — full-screen single-task view."),
    ("tablet", "offline.queue_size", 50, "int",
     "Maximum problem-reports buffered locally when network drops."),

    # ───────────────────── sandbox (Onda 3 follow-up) ───────────────────────
    # Plan §13 — Layer 4b scenario simulation. The module today defaults
    # to bounded budgets; expose them as configurable knobs.
    ("sandbox", "scenario.budget_seconds", 30, "int",
     "Per-scenario CPO time limit when sandbox runs the real engine."),
    ("sandbox", "scenario.max_active", 5, "int",
     "How many SIMULATING scenarios may run in parallel per tenant."),
    ("sandbox", "scenario.retention_days", 30, "int",
     "Soft-delete sandbox scenarios after this many days."),

    # ───────────────────── twin (Onda 3 follow-up) ──────────────────────────
    # Plan §13 — digital twin. Counterfactual computation defaults.
    ("twin", "scenario.default_horizon_days", 14, "int",
     "Forward-look horizon for what-if scenarios."),
    ("twin", "scenario.cache_ttl_seconds", 300, "int",
     "How long delta-view results are cached before recomputation."),
    ("twin", "comparison.max_pairs", 4, "int",
     "Maximum scenarios shown side-by-side in the comparison view."),

    # ───────────────────── ml (Onda 3 follow-up) ────────────────────────────
    # Plan §13 Layer 4b — feature extractors + retrain cadence. The ML
    # registry consumes these to gate model promotion.
    ("ml", "retrain.min_samples", 200, "int",
     "Minimum new samples required before a retrain job runs."),
    ("ml", "retrain.window_days", 90, "int",
     "Lookback window the retrainer pulls features from."),
    ("ml", "promotion.holdout_pct", 0.15, "float",
     "Fraction of the dataset reserved for the holdout score."),
    ("ml", "promotion.min_score_improvement", 0.02, "float",
     "Required uplift over the live model before a candidate is promoted."),

    # ───────────────────── kpi_targets (Onda 3 follow-up) ───────────────────
    # Plan §9 CEO dashboard — every KPI shown to the CEO has a target;
    # these keys define them so dashboards/charts don't hardcode them.
    ("kpi_targets", "otd_pct", 95.0, "float",
     "On-Time Delivery target (%). Below this triggers a warning tile."),
    ("kpi_targets", "fpy_pct", 80.0, "float",
     "First-pass yield target (%)."),
    ("kpi_targets", "rework_pct", 10.0, "float",
     "Maximum acceptable global rework rate (%)."),
    ("kpi_targets", "wip_max_boats", 540, "int",
     "WIP ceiling — Plan §2 estimated 220-540."),

    # ───────────────────── dqa (Onda 3 follow-up) ───────────────────────────
    # Plan §15 — DQA layer config (separate from the Trust *Index*
    # weights, which live in `trust`). This bucket carries pipeline +
    # baseline knobs.
    ("dqa", "drift.alert_threshold", 0.20, "float",
     "Schema drift fraction above which an alert fires."),
    ("dqa", "freshness.curated_max_age_h", 24.0, "float",
     "Hours after which curated rows are flagged stale."),
    ("dqa", "auto_repair.enabled", False, "bool",
     "Run the auto-repair pipeline on quarantined rows."),

    # ───────────────────── realtime (Onda 3 follow-up) ──────────────────────
    # Plan §13 Layer 1 — RLM event bus + SSE bridge. Operators tune the
    # bus rather than touching env vars.
    ("realtime", "sse.heartbeat_seconds", 15, "int",
     "Server-sent-event heartbeat interval to keep middlebox proxies alive."),
    ("realtime", "kafka.enabled", False, "bool",
     "Toggle the Kafka publisher. When False the outbox table buffers."),
    ("realtime", "outbox.flush_batch_size", 100, "int",
     "How many outbox events the worker flushes per tick."),

    # ───────────────────── session (Onda 3 follow-up) ───────────────────────
    # Plan §11.1 RBAC adjacency — session lifetime + step-up timeouts
    # for sensitive routes (auto-approval gates, kill switch).
    ("session", "idle_timeout_minutes", 60, "int",
     "Sign out idle sessions after this many minutes."),
    ("session", "step_up.required_for_kill_switch", True, "bool",
     "Require fresh password challenge before /governance/kill-switch."),
    ("session", "remember_me_days", 14, "int",
     "Persistent session length when 'manter ligado' is checked."),

    # ───────────────────── dispatch (Onda 3 follow-up) ──────────────────────
    # Plan §7 — Despacho rules separate from `transporte` (which is
    # truck physics). Dispatch carries policy: client priority,
    # advance/delay tolerance, regrouping aggressiveness.
    ("dispatch", "advance.max_days", 3, "int",
     "How many days early a boat may ship if the suggestion offers."),
    ("dispatch", "delay.tolerance_days", 1, "int",
     "Tolerated slip before a delay suggestion fires."),
    ("dispatch", "client_priority.enabled", True, "bool",
     "Honour the per-client priority list when suggesting regroupings."),

    # ───────────────────── explain (Onda 3 follow-up) ───────────────────────
    # Plan §13 Layer 4 — Explain catalog + causal traces. The blocked
    # metrics list lives in `factory_data_product/config.py`; this
    # category controls catalog rendering + cache.
    ("explain", "catalog.cache_ttl_seconds", 300, "int",
     "How long the metrics catalog is cached in memory."),
    ("explain", "trace.max_depth", 5, "int",
     "Mill's-method causal chain max recursion depth."),
    ("explain", "fallback.enabled", True, "bool",
     "Render the static catalog when a real causal trace is unavailable."),

    # ───────────────────── improve (Onda 3 follow-up) ───────────────────────
    # Plan — the improve module ships seed suggestions; once Camada 1
    # is wired (Onda 1) it consumes acceptance signals. These keys
    # gate that behaviour without code changes.
    ("improve", "suggestion.cooldown_days", 7, "int",
     "Don't propose the same suggestion type twice within this window."),
    ("improve", "auto_dismiss_after_days", 30, "int",
     "Suggestions ignored for this many days are soft-deleted."),
    ("improve", "min_confidence", 0.60, "float",
     "Suggestions below this confidence stay in the operator backlog."),
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
