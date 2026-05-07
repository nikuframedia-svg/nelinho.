"""YAML policy loader (Sprint Q.17.A).

Reads + validates ``config/yaml/system_defaults.yaml`` and exposes the
flattened seed list expected by ``seed_tenant_defaults``. Keeping the legacy
tuple shape lets every existing caller continue to work unchanged while the
YAML becomes the single source of truth.

Hot-reload via watchdog and the other 9 YAMLs land in later Q.17 sub-sprints.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .rule_schema import TenantRulesYaml
from .schema import SystemDefaultsYaml

_log = logging.getLogger(__name__)

# Resolve ``config/yaml/`` relative to this file so the loader works
# regardless of the working directory the app is launched from. Layout:
#   src/governance/yaml_policy/loader.py  ->  parents[3] == repo root.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
DEFAULT_YAML_DIR: Path = _REPO_ROOT / "config" / "yaml"

ConfigSeed = tuple[str, str, Any, str, str]
"""Legacy tuple shape: (category, key, value, data_type, description)."""

SUPPORTED_VERSIONS: frozenset[int] = frozenset({1})


class YamlPolicyError(RuntimeError):
    """Raised when a YAML policy file is missing, malformed, or schema-invalid."""


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise YamlPolicyError(f"YAML policy file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise YamlPolicyError(f"YAML parse error in {path.name}: {exc}") from exc
    if raw is None:
        raise YamlPolicyError(f"{path.name} is empty")
    if not isinstance(raw, dict):
        raise YamlPolicyError(f"{path.name} top-level must be a mapping, got {type(raw).__name__}")
    return raw


def load_system_defaults(yaml_dir: Path | None = None) -> SystemDefaultsYaml:
    """Load + validate ``system_defaults.yaml``.

    Raises ``YamlPolicyError`` on missing file, parse error, schema violation,
    or unsupported ``version``.
    """
    yaml_dir = yaml_dir or DEFAULT_YAML_DIR
    path = yaml_dir / "system_defaults.yaml"
    raw = _read_yaml(path)

    try:
        doc = SystemDefaultsYaml.model_validate(raw)
    except ValidationError as exc:
        raise YamlPolicyError(f"system_defaults.yaml schema invalid: {exc}") from exc

    if doc.version not in SUPPORTED_VERSIONS:
        raise YamlPolicyError(
            f"system_defaults.yaml version {doc.version} not supported "
            f"(loader supports: {sorted(SUPPORTED_VERSIONS)})"
        )

    _log.debug(
        "loaded system_defaults.yaml: version=%s categories=%d settings=%d",
        doc.version,
        len(doc.categories),
        doc.total_settings(),
    )
    return doc


def system_defaults_to_seeds(doc: SystemDefaultsYaml) -> list[ConfigSeed]:
    """Flatten the validated YAML into the legacy seed-tuple shape.

    Order is stable: categories iterate in YAML insertion order (Python 3.7+
    dict guarantee), settings within a category preserve list order. Callers
    relying on the previous ``DEFAULT_SEEDS`` ordering keep the same iteration.
    """
    seeds: list[ConfigSeed] = []
    for category_name, cat in doc.categories.items():
        for setting in cat.settings:
            seeds.append(
                (
                    category_name,
                    setting.key,
                    setting.value,
                    setting.data_type,
                    setting.description,
                )
            )
    return seeds


def load_seeds(yaml_dir: Path | None = None) -> list[ConfigSeed]:
    """Convenience: load + flatten in one call.

    Returns ``list[(category, key, value, data_type, description)]`` —
    drop-in replacement for ``default_configs.DEFAULT_SEEDS``.
    """
    return system_defaults_to_seeds(load_system_defaults(yaml_dir))


def load_tenant_rules(yaml_dir: Path | None = None) -> TenantRulesYaml:
    """Load + validate ``tenant_rules.yaml`` (Sprint Q.17.B).

    Returns an empty TenantRulesYaml(version=1, rules=[]) when the file
    does not exist yet — fresh tenants start with no rules. The loader
    raises ``YamlPolicyError`` only on parse error or schema violation.

    The Q.17.D engine watches this file and rebuilds its rule registry
    on change (hot-reload via watchdog).
    """
    yaml_dir = yaml_dir or DEFAULT_YAML_DIR
    path = yaml_dir / "tenant_rules.yaml"
    if not path.exists():
        # Fresh tenant — no rules authored yet. Don't error, return empty.
        _log.debug("tenant_rules.yaml not found at %s; returning empty document", path)
        return TenantRulesYaml(version=1, rules=[])

    raw = _read_yaml(path)
    try:
        doc = TenantRulesYaml.model_validate(raw)
    except ValidationError as exc:
        raise YamlPolicyError(f"tenant_rules.yaml schema invalid: {exc}") from exc

    if doc.version not in SUPPORTED_VERSIONS:
        raise YamlPolicyError(
            f"tenant_rules.yaml version {doc.version} not supported "
            f"(loader supports: {sorted(SUPPORTED_VERSIONS)})"
        )

    _log.debug(
        "loaded tenant_rules.yaml: version=%s rules=%d",
        doc.version, len(doc.rules),
    )
    return doc
