"""Pydantic schema for YAML policy files (Sprint Q.17.A).

The first YAML to land is ``system_defaults.yaml``. It carries the canonical
seed values that every tenant starts with. The shape mirrors the legacy
``default_configs.DEFAULT_SEEDS`` tuple list so the loader can return the
exact same structure to existing callers (``seed_tenant_defaults``).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Mirrors src.core.models.tenant_configuration.ALLOWED_DATA_TYPES so
# round-tripping a YAML through the loader and back into the database
# never produces an unsupported data_type.
SettingDataType = Literal[
    "int",
    "float",
    "bool",
    "string",
    "json",
    "duration",
    "currency",
]


class SettingDef(BaseModel):
    """One configurable setting (one row in tenant_configuration).

    Validation rules:
    - ``key`` is non-empty and at most 255 chars (matches DB column limit).
    - ``data_type`` is one of the ALLOWED_DATA_TYPES vocabulary.
    - ``value`` is intentionally Any: bool/int/float/str + JSON-friendly
      composites are valid, the DB column is JSONB.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=255)
    value: Any
    data_type: SettingDataType
    description: str = ""


class CategoryDef(BaseModel):
    """A bucket of related settings (e.g. ``planning``, ``trust``).

    Within a YAML file, every category lists its settings explicitly as a
    list of SettingDef rows. Order is preserved.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    settings: list[SettingDef] = Field(default_factory=list)

    def keys_set(self) -> set[str]:
        return {s.key for s in self.settings}


class SystemDefaultsYaml(BaseModel):
    """Top-level shape of ``config/yaml/system_defaults.yaml``.

    ``version`` follows the file format. Bump when the schema changes in a
    breaking way (e.g. switching ``settings`` from list to dict). The loader
    rejects unknown ``version`` values to avoid silently mis-parsing.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1)
    schema_name: str = "system_defaults.v1"
    categories: dict[str, CategoryDef]

    def total_settings(self) -> int:
        return sum(len(cat.settings) for cat in self.categories.values())

    def category_names(self) -> list[str]:
        return list(self.categories.keys())
