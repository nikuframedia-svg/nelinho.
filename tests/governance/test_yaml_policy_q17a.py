"""Tests for src.governance.yaml_policy (Sprint Q.17.A foundation).

Coverage:
- Schema validation (positive + negative paths).
- Round-trip loader: YAML on disk → SystemDefaultsYaml → flattened seeds.
- iter_seeds() backward-compatibility: same number/set as embedded fallback.
- Fallback path when YAML is missing or malformed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.core.services.default_configs import DEFAULT_SEEDS, iter_seeds
from src.governance.yaml_policy import (
    CategoryDef,
    SettingDef,
    SystemDefaultsYaml,
    YamlPolicyError,
    load_seeds,
    load_system_defaults,
    system_defaults_to_seeds,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_setting_def_minimal():
    s = SettingDef(key="cpo.pop_size", value=100, data_type="int")
    assert s.description == ""


def test_setting_def_rejects_unknown_data_type():
    with pytest.raises(ValidationError):
        SettingDef(key="x", value=1, data_type="not_a_type")  # type: ignore[arg-type]


def test_setting_def_rejects_empty_key():
    with pytest.raises(ValidationError):
        SettingDef(key="", value=1, data_type="int")


def test_setting_def_rejects_extra_fields():
    """extra='forbid' protects against typos that would silently lose data."""
    with pytest.raises(ValidationError):
        SettingDef(
            key="x",
            value=1,
            data_type="int",
            descripton="typo",  # type: ignore[call-arg]
        )


def test_category_def_default_empty_settings():
    cat = CategoryDef()
    assert cat.settings == []
    assert cat.keys_set() == set()


def test_system_defaults_yaml_total_settings():
    doc = SystemDefaultsYaml(
        version=1,
        categories={
            "a": CategoryDef(settings=[SettingDef(key="k1", value=1, data_type="int")]),
            "b": CategoryDef(settings=[
                SettingDef(key="k2", value="x", data_type="string"),
                SettingDef(key="k3", value=True, data_type="bool"),
            ]),
        },
    )
    assert doc.total_settings() == 3
    assert doc.category_names() == ["a", "b"]


def test_system_defaults_yaml_rejects_version_zero():
    with pytest.raises(ValidationError):
        SystemDefaultsYaml(version=0, categories={})


# ---------------------------------------------------------------------------
# Loader (against the real config/yaml/system_defaults.yaml)
# ---------------------------------------------------------------------------


def test_load_system_defaults_real_file():
    """The real YAML on disk must validate and have the expected counts."""
    doc = load_system_defaults()
    assert doc.version == 1
    assert doc.schema_name == "system_defaults.v1"
    # Anchored to current state — bump if the YAML legitimately changes.
    assert doc.total_settings() == len(DEFAULT_SEEDS)
    assert len(doc.categories) == len({c for c, *_ in DEFAULT_SEEDS})


def test_loader_flattens_to_seed_tuples():
    seeds = load_seeds()
    assert len(seeds) == len(DEFAULT_SEEDS)
    # Each seed is a 5-tuple matching ConfigSeed.
    for c, k, v, dt, desc in seeds:
        assert isinstance(c, str) and c
        assert isinstance(k, str) and k
        assert dt in {"int", "float", "bool", "string", "json", "duration", "currency"}
        assert isinstance(desc, str)


def test_loader_set_equals_embedded_seeds():
    """YAML and embedded fallback must describe the same (category, key) universe.

    Order can differ (YAML groups by category), but every legacy seed must
    appear in the YAML and vice-versa.
    """
    yaml_seeds = load_seeds()

    def to_set(rows):
        return {(c, k, str(v), dt) for c, k, v, dt, _ in rows}

    assert to_set(yaml_seeds) == to_set(DEFAULT_SEEDS)


def test_loader_no_duplicate_keys():
    """A (category, key) pair must appear at most once across the whole file."""
    seeds = load_seeds()
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for c, k, *_ in seeds:
        if (c, k) in seen:
            duplicates.append((c, k))
        seen.add((c, k))
    assert duplicates == []


# ---------------------------------------------------------------------------
# Loader error paths (use temp YAML files — no global state mutation)
# ---------------------------------------------------------------------------


def _write_tmp_yaml(tmp_path: Path, body: str) -> Path:
    """Write a YAML file under tmp_path/config/yaml/system_defaults.yaml."""
    yaml_dir = tmp_path / "config" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "system_defaults.yaml").write_text(body, encoding="utf-8")
    return yaml_dir


def test_load_raises_on_missing_file(tmp_path: Path):
    yaml_dir = tmp_path / "config" / "yaml"
    yaml_dir.mkdir(parents=True)
    with pytest.raises(YamlPolicyError, match="not found"):
        load_system_defaults(yaml_dir)


def test_load_raises_on_empty_file(tmp_path: Path):
    yaml_dir = _write_tmp_yaml(tmp_path, "")
    with pytest.raises(YamlPolicyError, match="empty"):
        load_system_defaults(yaml_dir)


def test_load_raises_on_non_mapping_top_level(tmp_path: Path):
    yaml_dir = _write_tmp_yaml(tmp_path, "- 1\n- 2\n")
    with pytest.raises(YamlPolicyError, match="top-level must be a mapping"):
        load_system_defaults(yaml_dir)


def test_load_raises_on_unsupported_version(tmp_path: Path):
    body = yaml.safe_dump({"version": 99, "schema_name": "x", "categories": {}})
    yaml_dir = _write_tmp_yaml(tmp_path, body)
    with pytest.raises(YamlPolicyError, match="version"):
        load_system_defaults(yaml_dir)


def test_load_raises_on_schema_violation(tmp_path: Path):
    body = yaml.safe_dump(
        {
            "version": 1,
            "categories": {
                "x": {
                    "settings": [
                        {"key": "k", "value": 1, "data_type": "not_a_type"},
                    ]
                }
            },
        }
    )
    yaml_dir = _write_tmp_yaml(tmp_path, body)
    with pytest.raises(YamlPolicyError, match="schema invalid"):
        load_system_defaults(yaml_dir)


def test_load_raises_on_yaml_parse_error(tmp_path: Path):
    yaml_dir = _write_tmp_yaml(tmp_path, "version: 1\n  bad: indent: here:\n")
    with pytest.raises(YamlPolicyError, match="YAML parse error"):
        load_system_defaults(yaml_dir)


# ---------------------------------------------------------------------------
# Backward compatibility — iter_seeds() must keep working
# ---------------------------------------------------------------------------


def test_iter_seeds_returns_yaml_when_available():
    """iter_seeds() reads the YAML; result count matches DEFAULT_SEEDS exactly."""
    seeds = iter_seeds()
    assert len(seeds) == len(DEFAULT_SEEDS)


def test_iter_seeds_returns_same_set_as_embedded():
    """No silent drift between YAML and embedded fallback."""
    yaml_seeds = iter_seeds()

    def to_set(rows):
        return {(c, k, str(v), dt) for c, k, v, dt, _ in rows}

    assert to_set(yaml_seeds) == to_set(DEFAULT_SEEDS)


# ---------------------------------------------------------------------------
# Round-trip flatten helper — pure function, easy to test independently
# ---------------------------------------------------------------------------


def test_system_defaults_to_seeds_preserves_order_within_category():
    doc = SystemDefaultsYaml(
        version=1,
        categories={
            "alpha": CategoryDef(settings=[
                SettingDef(key="k_a", value=1, data_type="int", description="A"),
                SettingDef(key="k_b", value=2, data_type="int", description="B"),
            ]),
            "beta": CategoryDef(settings=[
                SettingDef(key="k_c", value="x", data_type="string"),
            ]),
        },
    )
    seeds = system_defaults_to_seeds(doc)
    assert seeds == [
        ("alpha", "k_a", 1, "int", "A"),
        ("alpha", "k_b", 2, "int", "B"),
        ("beta", "k_c", "x", "string", ""),
    ]
