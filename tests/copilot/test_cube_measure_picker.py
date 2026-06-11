"""Picker de KPIs — catálogo de measures + cards ad-hoc (offline, sem rede).

Cobre o encanamento que abre as 127 measures do Cube ao menu da página de KPIs:
    1. `list_measure_catalog()` devolve TODAS as measures do contrato, com unit
       de apresentação coerente e ordenado por (domínio, nome).
    2. `_coerce_card_specs()` valida (rejeita fora-do-contrato, coage period,
       dedup) — a lógica do endpoint POST sem tocar no Cube.
    3. `_run_card()` reutilizado (FakeCube): ok / no_data honestos.
    4. `cube_measures_dev()` chamado directo devolve o catálogo inteiro.
"""
from __future__ import annotations

import pytest

from src.copilot.cube.client import CubeResult
from src.copilot.cube.measure_contract import (
    MEASURE_REGISTRY,
    is_fractional_measure,
    is_monetary_measure,
    list_measure_catalog,
    measure_display_unit,
)


# ────────────────────────────── 1. Catálogo ──────────────────────────────


def test_catalog_covers_every_registered_measure():
    """O catálogo do picker expõe TODAS as measures do contrato — sem buracos."""
    catalog = list_measure_catalog()
    assert len(catalog) == len(MEASURE_REGISTRY)
    assert {m["name"] for m in catalog} == set(MEASURE_REGISTRY)
    # Cada entrada tem os campos que o menu do frontend precisa.
    # Q.173.AL: sql + sql_table adicionados (fórmula + fonte para explicabilidade).
    required = {"name", "label", "unit", "domain", "dimensions", "supports_period"}
    for m in catalog:
        assert required.issubset(set(m)), f"campos em falta em {m['name']}: {required - set(m)}"
        assert m["label"]  # nunca vazio (fallback para name)
        assert m["unit"] in {"", "%", "€"}
        assert isinstance(m["dimensions"], list)
        assert isinstance(m["supports_period"], bool)
        assert isinstance(m["sql"], str)        # Q.173.AL: pode ser "" se YAML não tem
        assert isinstance(m["sql_table"], str)  # Q.173.AL: pode ser ""


def test_catalog_is_sorted_by_domain_then_name():
    catalog = list_measure_catalog()
    keys = [(m["domain"], m["name"]) for m in catalog]
    assert keys == sorted(keys)


def test_catalog_unit_mapping_matches_contract():
    """unit de apresentação espelha o contrato: € p/ DINHEIRO, % p/ FRACAO, '' resto."""
    by_name = {m["name"]: m for m in list_measure_catalog()}
    for name in MEASURE_REGISTRY:
        unit = by_name[name]["unit"]
        if is_monetary_measure(name):
            assert unit == "€", name
        elif is_fractional_measure(name):
            assert unit == "%", name
        else:
            assert unit == "", name
    # Sanidade: o registo real tem pelo menos uma € e uma % (senão o mapping
    # nunca seria exercido e o picker não distinguiria unidades).
    units = {m["unit"] for m in by_name.values()}
    assert "€" in units
    assert "%" in units


def test_catalog_supports_period_follows_tempo_dimension():
    by_name = {m["name"]: m for m in list_measure_catalog()}
    for name, spec in MEASURE_REGISTRY.items():
        assert by_name[name]["supports_period"] == ("tempo" in spec.dimensions_supported)


def test_measure_display_unit_unknown_is_blank():
    assert measure_display_unit("nao.existe") == ""


@pytest.mark.asyncio
async def test_measures_endpoint_returns_full_catalog():
    """O endpoint dev devolve o catálogo inteiro (chamada directa, sem Cube)."""
    from src.copilot.routers.ask_cube import cube_measures_dev

    resp = await cube_measures_dev()
    assert len(resp.measures) == len(MEASURE_REGISTRY)
    # Pydantic validou cada entrada no schema MeasureCatalogEntry.
    sample = resp.measures[0]
    assert sample.name and sample.label and sample.unit in {"", "%", "€"}


# ────────────────────────── 2. _coerce_card_specs ──────────────────────────


def test_coerce_rejects_unknown_measure():
    from fastapi import HTTPException

    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    with pytest.raises(HTTPException) as exc:
        _coerce_card_specs([MeasureCardRequestItem(measure="oee.inventado")])
    assert exc.value.status_code == 422
    assert "desconhecida" in str(exc.value.detail).lower()


def test_coerce_month_coerced_to_none_when_no_tempo():
    """period=month numa measure SEM `tempo` cai para none (timeDimension inválida)."""
    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    no_tempo = next(
        name for name, spec in MEASURE_REGISTRY.items()
        if "tempo" not in spec.dimensions_supported
    )
    specs = _coerce_card_specs([MeasureCardRequestItem(measure=no_tempo, period="month")])
    assert len(specs) == 1
    assert specs[0].period == "none"
    assert specs[0].measure == no_tempo


def test_coerce_month_kept_when_tempo_supported():
    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    with_tempo = next(
        name for name, spec in MEASURE_REGISTRY.items()
        if "tempo" in spec.dimensions_supported
    )
    specs = _coerce_card_specs([MeasureCardRequestItem(measure=with_tempo, period="month")])
    assert specs[0].period == "month"


def test_coerce_last_month_kept_when_tempo_supported():
    """period=last_month numa measure temporal mantém-se (mês anterior completo)."""
    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    with_tempo = next(
        name for name, spec in MEASURE_REGISTRY.items()
        if "tempo" in spec.dimensions_supported
    )
    specs = _coerce_card_specs([MeasureCardRequestItem(measure=with_tempo, period="last_month")])
    assert specs[0].period == "last_month"


def test_coerce_last_month_coerced_to_none_when_no_tempo():
    """period=last_month numa measure SEM `tempo` cai para none."""
    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    no_tempo = next(
        name for name, spec in MEASURE_REGISTRY.items()
        if "tempo" not in spec.dimensions_supported
    )
    specs = _coerce_card_specs([MeasureCardRequestItem(measure=no_tempo, period="last_month")])
    assert specs[0].period == "none"


def test_last_complete_month_range_is_previous_full_month():
    """O range 'mês passado' começa no dia 1 e acaba no último dia do mês anterior."""
    from datetime import date

    from src.copilot.routers.ask_cube import _last_complete_month_range

    # dia 2 de Junho → Maio inteiro (não Junho a decorrer, quase vazio).
    start, end = _last_complete_month_range(date(2026, 6, 2))
    assert start == "2026-05-01"
    assert end == "2026-05-31"
    # vira-ano: Janeiro → Dezembro do ano anterior.
    start, end = _last_complete_month_range(date(2026, 1, 15))
    assert start == "2025-12-01"
    assert end == "2025-12-31"


def test_coerce_dedups_preserving_order():
    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    a, b = list(MEASURE_REGISTRY)[:2]
    specs = _coerce_card_specs([
        MeasureCardRequestItem(measure=a),
        MeasureCardRequestItem(measure=b),
        MeasureCardRequestItem(measure=a),  # duplicado
    ])
    assert [s.measure for s in specs] == [a, b]


def test_coerce_card_unit_matches_catalog():
    """O card herda a unidade de apresentação da measure (igual ao catálogo)."""
    from src.copilot.routers.ask_cube import MeasureCardRequestItem, _coerce_card_specs

    monetary = next(name for name in MEASURE_REGISTRY if is_monetary_measure(name))
    specs = _coerce_card_specs([MeasureCardRequestItem(measure=monetary)])
    assert specs[0].unit == "€"


# ────────────────────────── 3. _run_card via FakeCube ──────────────────────────


class _FakeCube:
    """Cube fake: devolve `rows` fixas para qualquer query (sem rede)."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def load(self, payload):
        return CubeResult.model_validate({"data": self._rows, "annotation": {}, "query": payload})

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_run_card_ok_with_value():
    import datetime as _dt

    from src.copilot.routers.ask_cube import _CardSpec, _run_card

    measure = "consumo_material.custo"
    spec = _CardSpec(key=measure, label="Custo", unit="€", measure=measure, period="none")
    cube = _FakeCube([{measure: 1234.5}])
    card = await _run_card(cube, spec, _dt.date(2026, 6, 1))  # type: ignore[arg-type]
    assert card.status == "ok"
    assert card.value == 1234.5
    assert card.key == measure
    assert card.unit == "€"


@pytest.mark.asyncio
async def test_run_card_no_data_when_empty():
    import datetime as _dt

    from src.copilot.routers.ask_cube import _CardSpec, _run_card

    measure = "consumo_material.consumo"
    spec = _CardSpec(key=measure, label="Consumo", unit="", measure=measure, period="none")
    cube = _FakeCube([])  # mart vazio
    card = await _run_card(cube, spec, _dt.date(2026, 6, 1))  # type: ignore[arg-type]
    assert card.status == "no_data"
    assert card.value is None
