"""Q.68.5.A - drop 84 unused config keys (Q.67.3.C audit).

Q.67.3.C auditou 184 keys seeded em `src/core/services/default_configs.py`
e classificou cada uma como USED / UNUSED / RUNTIME-ONLY (ver
`agent_docs/config_keys_audit.md`). As 84 UNUSED tem ZERO call-sites em
`src/`, `frontend/src/` e `tests/` (defesa em profundidade), e a sua
categoria nao tem consumidor dinamico `get_category("<cat>")`.

Esta migration apaga as 84 linhas correspondentes da tabela
`core.tenant_configuration` por (category, key). Tenants que tenham um
override custom em algumas destas keys perdem-no - mas zero call-sites
significa que ninguem ia ler o override.

O seed `DEFAULT_SEEDS` em `default_configs.py` e
`config/yaml/system_defaults.yaml` sao actualizados na mesma sub-sprint
para que re-seeding nao re-introduza as keys apagadas.

Revision ID: 061_q68_drop_unused_configs
Revises: 060_q66_e_agent_actions
Create Date: 2026-05-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "061_q68_drop_unused_configs"
down_revision = "060_q66_e_agent_actions"
branch_labels = None
depends_on = None


# 84 keys identified as UNUSED by Q.67.3.C audit.
# Ordered by category for reviewer convenience.
UNUSED_KEYS: list[tuple[str, str]] = [
    # alertas.* (5)
    ("alertas", "default.severity"),
    ("alertas", "delivery.recipients_email"),
    ("alertas", "delivery_risk.window_days"),
    ("alertas", "mold_health.threshold"),
    ("alertas", "shortage.window_days"),
    # copilot.* (2)
    ("copilot", "rate_limit.per_day"),
    ("copilot", "rate_limit.per_hour"),
    # dispatch.* (3)
    ("dispatch", "advance.max_days"),
    ("dispatch", "client_priority.enabled"),
    ("dispatch", "delay.tolerance_days"),
    # dqa.* (3)
    ("dqa", "auto_repair.enabled"),
    ("dqa", "drift.alert_threshold"),
    ("dqa", "freshness.curated_max_age_h"),
    # explain.* (3)
    ("explain", "catalog.cache_ttl_seconds"),
    ("explain", "fallback.enabled"),
    ("explain", "trace.max_depth"),
    # factory_map.* (2)
    ("factory_map", "projection.days_ahead_default"),
    ("factory_map", "shortage.horizon_days_default"),
    # improve.* (3)
    ("improve", "auto_dismiss_after_days"),
    ("improve", "min_confidence"),
    ("improve", "suggestion.cooldown_days"),
    # kpi_targets.* (4)
    ("kpi_targets", "fpy_pct"),
    ("kpi_targets", "otd_pct"),
    ("kpi_targets", "rework_pct"),
    ("kpi_targets", "wip_max_boats"),
    # learning_rules.* (4)
    ("learning_rules", "auto_revert_after_days"),
    ("learning_rules", "confidence.auto_confirm"),
    ("learning_rules", "confidence.minimum"),
    ("learning_rules", "window.lookback_days"),
    # llm.ollama.* (4) - Ollama config vem de src.shared.config.settings (env), nao do tenant DB
    ("llm", "ollama.keep_alive"),
    ("llm", "ollama.model"),
    ("llm", "ollama.num_ctx"),
    ("llm", "ollama.temperature"),
    # ml.* (4)
    ("ml", "promotion.holdout_pct"),
    ("ml", "promotion.min_score_improvement"),
    ("ml", "retrain.min_samples"),
    ("ml", "retrain.window_days"),
    # notifications.* (6)
    ("notifications", "email.batch_window_minutes"),
    ("notifications", "email.enabled"),
    ("notifications", "quiet_hours.end"),
    ("notifications", "quiet_hours.start"),
    ("notifications", "slack.webhook_url"),
    ("notifications", "sms.enabled"),
    # rbac.* (4)
    ("rbac", "approvals.require_role"),
    ("rbac", "ceo_dashboard.allowed_roles"),
    ("rbac", "config.editable_by"),
    ("rbac", "roles.default"),
    # realtime.* (3)
    ("realtime", "kafka.enabled"),
    ("realtime", "outbox.flush_batch_size"),
    ("realtime", "sse.heartbeat_seconds"),
    # reports.* (5)
    ("reports", "ceo.recipients"),
    ("reports", "daily.enabled"),
    ("reports", "daily.hour_utc"),
    ("reports", "format"),
    ("reports", "weekly.enabled"),
    # routing.* (3)
    ("routing", "ab_variant.enabled"),
    ("routing", "phases.requires_mold"),
    ("routing", "standards.buffer_factor"),
    # sandbox.* (3)
    ("sandbox", "scenario.budget_seconds"),
    ("sandbox", "scenario.max_active"),
    ("sandbox", "scenario.retention_days"),
    # session.* (3)
    ("session", "idle_timeout_minutes"),
    ("session", "remember_me_days"),
    ("session", "step_up.required_for_kill_switch"),
    # system.* (8) - rate-limits + format.date + report.daily_email_hour
    ("system", "format.date"),
    ("system", "rate_limit.copilot_respond.limit"),
    ("system", "rate_limit.copilot_respond.window_seconds"),
    ("system", "rate_limit.cpo_schedule.limit"),
    ("system", "rate_limit.cpo_schedule.window_seconds"),
    ("system", "rate_limit.preview_delta.limit"),
    ("system", "rate_limit.preview_delta.window_seconds"),
    ("system", "report.daily_email_hour"),
    # tablet.* (4)
    ("tablet", "offline.queue_size"),
    ("tablet", "refresh.seconds"),
    ("tablet", "ui.font_scale"),
    ("tablet", "ui.kiosk_mode"),
    # transporte.* (3)
    ("transporte", "buffer.days_before_dispatch"),
    ("transporte", "completion.min_fill_ratio"),
    ("transporte", "regroup.by_client"),
    # twin.* (3)
    ("twin", "comparison.max_pairs"),
    ("twin", "scenario.cache_ttl_seconds"),
    ("twin", "scenario.default_horizon_days"),
    # workforce.* (2)
    ("workforce", "shift.default_hours_per_day"),
    ("workforce", "skill.recency_months"),
]


def upgrade() -> None:
    """Delete unused keys from core.tenant_configuration.

    Idempotent - executes one DELETE per (category, key) tuple. Tenants
    that never had the row aren't affected. Re-running the migration is
    a no-op.
    """
    conn = op.get_bind()
    stmt = sa.text(
        "DELETE FROM core.tenant_configuration "
        "WHERE category = :cat AND key = :key"
    )
    for cat, key in UNUSED_KEYS:
        conn.execute(stmt, {"cat": cat, "key": key})


def downgrade() -> None:
    """No-op restore.

    If a deployment needs the keys back, bump `default_configs.py` +
    `system_defaults.yaml` to re-introduce them, then re-run
    `seed_tenant_defaults()` (idempotent). No data is preserved here
    because the audit confirmed zero call-sites.
    """
    pass
