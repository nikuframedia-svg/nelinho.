"""Q.108.TEST.A — Cube YAML schema validator.

Valida 48+ ficheiros `cube/model/*.yml` com Pydantic e cross-checa contra
`MEASURE_REGISTRY`. Apanha:
  - typos em `sql:`, `type:`, `format:` antes de o Cube falhar em runtime.
  - measures declaradas no YAML que não existem em MEASURE_REGISTRY.
  - dims usadas no YAML fora de CANONICAL_DIMENSIONS.
  - bijecção inversa: cada measure em MEASURE_REGISTRY tem entrada num
    `cube/model/*.yml`.

Inspirado em src/copilot/kpi/catalog_loader.py (mesmo padrão Pydantic+yaml).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CUBE_MODEL_DIR = _REPO_ROOT / "cube" / "model"


def cube_model_dir() -> Path:
    return _CUBE_MODEL_DIR


_VALID_MEASURE_TYPES: frozenset[str] = frozenset({
    # Cube.js usa camelCase em type names (countDistinct).
    "sum", "avg", "count", "countDistinct", "count_distinct",
    "max", "min", "number",
})
_VALID_DIM_TYPES: frozenset[str] = frozenset({
    "time", "string", "number", "boolean",
})
_VALID_FORMATS: frozenset[str] = frozenset({
    "number", "percent", "currency",
})


class CubeMeasureYaml(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: Optional[str] = None
    sql: str
    type: str
    format: Optional[str] = None
    shown: Optional[bool] = None  # alguns cubes usam shown:false para esconder
    title: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in _VALID_MEASURE_TYPES:
            raise ValueError(
                f"measure type '{v}' não está em {sorted(_VALID_MEASURE_TYPES)}"
            )
        return v

    @field_validator("format")
    @classmethod
    def _check_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in _VALID_FORMATS:
            raise ValueError(
                f"measure format '{v}' não está em {sorted(_VALID_FORMATS)}"
            )
        return v


class CubeDimensionYaml(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    name: str
    description: Optional[str] = None
    sql: str
    type: str
    title: Optional[str] = None
    shown: Optional[bool] = None
    primary_key: Optional[bool] = Field(default=None, alias="primaryKey")

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in _VALID_DIM_TYPES:
            raise ValueError(
                f"dimension type '{v}' não está em {sorted(_VALID_DIM_TYPES)}"
            )
        return v


class CubeYaml(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: Optional[str] = None
    sql_table: Optional[str] = None
    sql: Optional[str] = None
    measures: list[CubeMeasureYaml] = Field(default_factory=list)
    dimensions: list[CubeDimensionYaml] = Field(default_factory=list)
    joins: Optional[list[dict]] = None  # raramente usado; aceitar opcionalmente

    @model_validator(mode="after")
    def _require_source(self) -> "CubeYaml":
        if not self.sql_table and not self.sql:
            raise ValueError(
                f"cube '{self.name}' precisa de `sql_table` OU `sql`."
            )
        if not self.measures and not self.dimensions:
            raise ValueError(
                f"cube '{self.name}' precisa de pelo menos 1 measure ou dimension."
            )
        return self


class CubeFileYaml(BaseModel):
    """Estrutura do topo do ficheiro: `cubes: [CubeYaml, ...]`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cubes: list[CubeYaml]

    @model_validator(mode="after")
    def _require_non_empty(self) -> "CubeFileYaml":
        if not self.cubes:
            raise ValueError("Ficheiro vazio — `cubes:` não pode ser vazio.")
        return self


def load_cube_yaml(path: Path) -> CubeFileYaml:
    """Lê e valida um cube/model/*.yml. Levanta `ValidationError` se mal-formado."""
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return CubeFileYaml.model_validate(raw)


def load_all_cube_yamls(root: Optional[Path] = None) -> dict[Path, CubeFileYaml]:
    """Carrega todos os cube/model/*.yml e devolve dict path → parsed.

    Levanta ValidationError no primeiro YAML malformado (fail-fast).
    """
    target = root or _CUBE_MODEL_DIR
    if not target.exists():
        raise FileNotFoundError(f"Cube model dir não encontrado: {target}")
    out: dict[Path, CubeFileYaml] = {}
    for path in sorted(target.glob("*.yml")):
        out[path] = load_cube_yaml(path)
    return out


def all_measure_full_names(parsed: dict[Path, CubeFileYaml]) -> set[str]:
    """Devolve set de `<cube>.<measure>` em todos os YAMLs."""
    names: set[str] = set()
    for cube_file in parsed.values():
        for cube in cube_file.cubes:
            for m in cube.measures:
                names.add(f"{cube.name}.{m.name}")
    return names


def all_dimension_names(parsed: dict[Path, CubeFileYaml]) -> dict[str, set[str]]:
    """Devolve dict cube_name → set de dim names declaradas no YAML."""
    out: dict[str, set[str]] = {}
    for cube_file in parsed.values():
        for cube in cube_file.cubes:
            out.setdefault(cube.name, set()).update(d.name for d in cube.dimensions)
    return out
