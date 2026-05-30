"""CubeQuery Pydantic + validador contra o catálogo /meta.

O LLM gera um CubeQuery (JSON estruturado) a partir da pergunta PT-PT.
Antes de o enviar para o Cube REST, validamos contra o catálogo: nenhuma
medida/dimensão fora do universo permitido; nenhum filtro `contains` em
`material` sem agrupar por (material, unidade_id) — anti-soma-cega.

Filtros suportados (subset do que a Cube REST API aceita; expandir conforme
necessário em fases seguintes):
    equals, notEquals, contains, gt, gte, lt, lte, set, notSet.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .client import CubeCatalog
from .measure_contract import assert_dims_supported, assert_soma_safe


# Operators suportados nesta fase (subset auditável).
ALLOWED_FILTER_OPERATORS: set[str] = {
    "equals", "notEquals", "contains", "notContains",
    "gt", "gte", "lt", "lte",
    "set", "notSet",
}

# Granularidades aceitáveis em timeDimensions.
ALLOWED_TIME_GRANULARITIES: set[str] = {
    "second", "minute", "hour", "day", "week", "month", "quarter", "year",
}


class CubeFilter(BaseModel):
    """Um filtro do CubeQuery — `member operator values`."""

    model_config = ConfigDict(extra="forbid")

    member: str  # ex: "consumo_material.material"
    operator: str
    values: list[str | int | float] = Field(default_factory=list)

    @field_validator("operator")
    @classmethod
    def _validate_operator(cls, v: str) -> str:
        if v not in ALLOWED_FILTER_OPERATORS:
            raise ValueError(
                f"operator {v!r} não permitido; suportados: {sorted(ALLOWED_FILTER_OPERATORS)}"
            )
        return v


class CubeTimeDimension(BaseModel):
    """Um eixo de tempo — `dimension dateRange granularity`."""

    model_config = ConfigDict(extra="forbid")

    dimension: str  # ex: "consumo_material.data"
    date_range: list[str] = Field(default_factory=list, alias="dateRange")
    granularity: str | None = None

    @field_validator("granularity")
    @classmethod
    def _validate_granularity(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_TIME_GRANULARITIES:
            raise ValueError(
                f"granularity {v!r} não permitida; suportadas: {sorted(ALLOWED_TIME_GRANULARITIES)}"
            )
        return v


class CubeQuery(BaseModel):
    """Schema da query JSON enviada para /cubejs-api/v1/load."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[CubeFilter] = Field(default_factory=list)
    time_dimensions: list[CubeTimeDimension] = Field(
        default_factory=list, alias="timeDimensions"
    )
    order: list[list[str]] = Field(default_factory=list)  # [["member", "asc|desc"]]
    limit: int | None = None

    def to_cube_payload(self) -> dict:
        """Serializa no formato exacto que a Cube REST API aceita (camelCase)."""
        return self.model_dump(by_alias=True, exclude_none=True, exclude_defaults=False)


# ────────────────────────────── Validador anti-soma-cega ──────────────────────────────


def validate_against_catalog(
    query: CubeQuery,
    catalog: CubeCatalog,
) -> list[str]:
    """Devolve lista de violações; lista vazia = query OK para executar.

    Verifica:
      1. Medidas existem no catálogo.
      2. Dimensions existem no catálogo.
      3. filter.member existe (medida ou dimension).
      4. timeDimension.dimension existe e é do tipo `time`.
      5. ANTI-SOMA-CEGA: se algum filter em `material` é `contains` (ambíguo),
         a query TEM de incluir AMBAS as dimensões `material` E `unidade_id`
         no GROUP BY (campo `dimensions`) — caso contrário o Cube somaria
         quantidades de unidades diferentes (kg + tambor + unidades).
    """
    violations: list[str] = []

    measure_names = set(catalog.all_measure_names())
    dimension_names = set(catalog.all_dimension_names())
    all_members = measure_names | dimension_names

    # Pelo menos uma medida (Cube exige).
    if not query.measures:
        violations.append("query sem medidas — pelo menos 1 measure obrigatória")

    for m in query.measures:
        if m not in measure_names:
            violations.append(
                f"medida {m!r} não existe no catálogo; disponíveis: "
                f"{sorted(measure_names)}"
            )

    for d in query.dimensions:
        if d not in dimension_names:
            violations.append(
                f"dimensão {d!r} não existe no catálogo; disponíveis: "
                f"{sorted(dimension_names)}"
            )

    for f in query.filters:
        if f.member not in all_members:
            violations.append(
                f"filter.member {f.member!r} não existe no catálogo "
                f"(nem medida nem dimensão)"
            )

    for td in query.time_dimensions:
        dim_spec = catalog.dimension(td.dimension)
        if dim_spec is None:
            violations.append(
                f"timeDimension.dimension {td.dimension!r} não existe no catálogo"
            )
        elif dim_spec.type != "time":
            violations.append(
                f"timeDimension {td.dimension!r} não é do tipo `time` "
                f"(é {dim_spec.type!r})"
            )

    # Q.95.2 — regras de soma e unidade canónica vivem no `measure_contract`
    # (fonte única). Subsume Q.95.1 anti-soma-cega (c03) + matriz de soma
    # cross-medida (D3 preparado para OEE/horas) + caso histórico Q.93.C
    # (contains material exige material+unidade_id em dims).
    violations.extend(assert_soma_safe(query))

    # Q.97 FIX 2 — `MeasureSpec.dimensions_supported` enforced. Qualidade
    # taxa_defeitos não aceita dim material; consumo_material.* não aceita
    # dim fase; etc. O contrato declarava — agora rejeita.
    violations.extend(assert_dims_supported(query))

    return violations
