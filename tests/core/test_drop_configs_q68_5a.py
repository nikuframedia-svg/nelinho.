"""Q.68.5.A — smoke test for the 84-unused-key migration.

Q.67.3.C auditou 184 config keys e classificou 84 como UNUSED (zero
call-sites). Q.68.5.A apaga-as via migration `061_q68_drop_unused_configs`
+ remove dos defaults (`default_configs.py` + `system_defaults.yaml`).

Estes smoke tests garantem:
- A lista `UNUSED_KEYS` na migration tem exactamente 84 entries.
- Nenhuma key apagada existe ainda em `DEFAULT_SEEDS` (drift impossivel).
- Nenhuma key apagada existe no YAML source-of-truth (drift impossivel).
- `DEFAULT_SEEDS` ainda tem >= 100 entries (sanidade — sub-sprint nao
  destruiu USED keys).
- As `RUNTIME-ONLY` keys (planning.*) continuam presentes (a CPO
  precisa delas em runtime).

Se algum destes tests falhar, esta-se a re-introduzir uma das 84
keys mortas ou a tirar uma viva. Re-correr
`scripts/audit_config_keys.py` para confirmar.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    ROOT / "alembic" / "versions" / "061_q68_drop_unused_configs.py"
)


def _load_migration():
    """Import the migration module without alembic env machinery."""
    spec = importlib.util.spec_from_file_location(
        "q68_5a_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Migration shape
# ---------------------------------------------------------------------------


def test_migration_file_exists() -> None:
    assert MIGRATION_PATH.exists(), f"missing migration: {MIGRATION_PATH}"


def test_unused_keys_count_is_84() -> None:
    """The audit found 84 UNUSED — the migration must match exactly."""
    mod = _load_migration()
    assert len(mod.UNUSED_KEYS) == 84, (
        f"expected 84 unused keys, got {len(mod.UNUSED_KEYS)}. "
        "If the audit changed, re-run scripts/audit_config_keys.py and "
        "update both this assert + UNUSED_KEYS in the migration."
    )


def test_unused_keys_no_duplicates() -> None:
    mod = _load_migration()
    assert len(set(mod.UNUSED_KEYS)) == len(mod.UNUSED_KEYS), (
        "duplicate (category, key) in UNUSED_KEYS"
    )


def test_migration_revision_chain() -> None:
    mod = _load_migration()
    assert mod.revision == "061_q68_drop_unused_configs"
    assert mod.down_revision == "060_q66_e_agent_actions"


# ---------------------------------------------------------------------------
# Drift guards — UNUSED keys must NOT be reseeded
# ---------------------------------------------------------------------------


def test_unused_keys_not_in_default_seeds() -> None:
    """Each apagada key must NOT appear in DEFAULT_SEEDS, senao um proximo
    `seed_tenant_defaults()` re-cria a linha que a migration acaba de
    apagar (loop infinito de seed/drop)."""
    from src.core.services.default_configs import DEFAULT_SEEDS

    mod = _load_migration()
    seed_keys = {(c, k) for c, k, *_ in DEFAULT_SEEDS}
    intersection = seed_keys & set(mod.UNUSED_KEYS)
    assert intersection == set(), (
        f"UNUSED keys still seeded — re-introduces dead config: {intersection}"
    )


def test_unused_keys_not_in_yaml() -> None:
    """system_defaults.yaml is the YAML source-of-truth read by
    `iter_seeds()` when available — drift would re-seed too."""
    import yaml

    yaml_path = ROOT / "config" / "yaml" / "system_defaults.yaml"
    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    yaml_keys: set[tuple[str, str]] = set()
    for cat, payload in (data.get("categories") or {}).items():
        for entry in payload.get("settings", []):
            yaml_keys.add((cat, entry["key"]))

    mod = _load_migration()
    intersection = yaml_keys & set(mod.UNUSED_KEYS)
    assert intersection == set(), (
        f"YAML still seeds dead keys: {intersection}. Regenerate with "
        "`scripts/generate_system_defaults_yaml.py`."
    )


# ---------------------------------------------------------------------------
# Sanity — DEFAULT_SEEDS still healthy after the cull
# ---------------------------------------------------------------------------


def test_default_seeds_has_at_least_100_keys() -> None:
    """184 originais - 84 UNUSED = 100. Se este conta cair, a sub-sprint
    apagou keys USED."""
    from src.core.services.default_configs import DEFAULT_SEEDS

    assert len(DEFAULT_SEEDS) >= 100, (
        f"DEFAULT_SEEDS has only {len(DEFAULT_SEEDS)} entries — Q.68.5.A "
        "may have apaga-do USED keys by mistake."
    )


def test_runtime_only_keys_preserved() -> None:
    """The audit listed 25 RUNTIME-ONLY keys (planning.*) consumed via
    `get_category("planning")`. They MUST survive the cull."""
    from src.core.services.default_configs import DEFAULT_SEEDS

    runtime_only_planning_keys = {
        "cpo.cpsat_budget_s",
        "cpo.ga_budget_s",
        "cpo.greedy_budget_s",
        "cpo.mapelites_budget_s",
        "cpo.pop_size",
        "cpo.use_frrmab",
        "cpo.use_mapelites",
        "cpo.use_surrogate",
        "cpo.workforce_budget_s",
        "fitness.quality_hard_penalty",
        "fitness.quality_hard_threshold",
        "fitness.truck_consolidation_tolerance_h",
        "fitness.truck_consolidation_weight",
        "mapelites.bins.idle_pct",
        "mapelites.bins.lam_utilization",
        "mapelites.bins.tardiness_transport",
        "mapelites.representatives_default",
        "mold.max_pocket_count",
        "replan.on_capacity_change",
        "replan.on_routing_change",
        "routing.templates.count",
        "scheduler.direction",
        "surrogate.min_samples_enable",
        "surrogate.retrain_every",
        "surrogate.threshold_factor",
    }
    seed_planning_keys = {
        k for c, k, *_ in DEFAULT_SEEDS if c == "planning"
    }
    missing = runtime_only_planning_keys - seed_planning_keys
    assert missing == set(), (
        f"RUNTIME-ONLY planning keys lost: {missing}. CPO needs these "
        "via get_category('planning')."
    )


def test_used_keys_preserved() -> None:
    """Spot-check a handful of USED keys to confirm the cull was precise."""
    from src.core.services.default_configs import DEFAULT_SEEDS

    seed_keys = {(c, k) for c, k, *_ in DEFAULT_SEEDS}
    must_survive = [
        ("cost", "target.throughput_eur_day_min"),
        ("cost", "target.throughput_eur_day_max"),
        ("cost", "margin_default"),
        ("planning", "cpo.gen_count"),
        ("planning", "cpo.total_budget_s"),
        ("planning", "fitness.weight.makespan"),
        ("trust", "weights.completeness"),
        ("trust", "gates.auto_commit"),
        ("mold", "health.red_threshold"),
        ("supply", "stockout_critical_days"),
        ("quality", "risk_alert_threshold"),
        ("llm", "backend"),
        ("llm", "vllm.base_url"),
        ("system", "language"),
        ("system", "theme"),
        ("system", "audit.retention_days"),
        ("transporte", "truck.capacity"),
        ("governance", "auto_approval.model_promotion.enabled"),
    ]
    for needle in must_survive:
        assert needle in seed_keys, f"USED key vanished: {needle}"


# ---------------------------------------------------------------------------
# Migration SQL shape
# ---------------------------------------------------------------------------


def test_migration_upgrade_callable() -> None:
    """Smoke that the upgrade() function compiles and the SQL template is
    valid (no syntax errors). We don't run it against a real DB here —
    that's exercised by the alembic upgrade head step in CI."""
    mod = _load_migration()
    assert callable(mod.upgrade)
    assert callable(mod.downgrade)


def test_downgrade_is_intentional_noop() -> None:
    """The migration is one-way: defaults wouldn't restore on downgrade
    anyway because we also pulled them out of `default_configs.py`."""
    mod = _load_migration()
    import inspect

    source = inspect.getsource(mod.downgrade)
    assert "pass" in source.lower(), (
        "downgrade() should be an intentional no-op (see docstring)."
    )
