"""Q.152 — measure diária `producao_ofs_fechadas_dia.total` + card "hoje".

Pins (offline, sem rede / sem Ollama):
    1. A measure está registada no contrato com unit/dim/sinónimos certos —
       é o que faz o retrieval surgir "quantas ofs produzidas hoje" em vez de
       o copiloto abster-se e cair no fallback SQL (que dá falso-zero).
    2. O card curado "OFs produzidas hoje" existe no dashboard com period="today".
    3. `_run_card` com period="today" constrói uma timeDimension [hoje, hoje]
       (e não o bucket do mês) e devolve o valor honesto via FakeCube.

A prova de retrieval ao vivo (top-1 sobre o índice BM25+FAISS) fica para a
verificação E2E — aqui pinamos o contrato + o card, que são determinísticos.
"""
from __future__ import annotations

import datetime as _dt

import pytest

from src.copilot.cube.client import CubeResult
from src.copilot.cube.measure_contract import (
    MEASURE_REGISTRY,
    CanonicalUnit,
    measure_display_unit,
)

MEASURE = "producao_ofs_fechadas_dia.total"


# ────────────────────────── 1. Contrato da measure ──────────────────────────


def test_daily_measure_registered():
    assert MEASURE in MEASURE_REGISTRY
    spec = MEASURE_REGISTRY[MEASURE]
    assert spec.unit is CanonicalUnit.CONTAGEM
    assert "tempo" in spec.dimensions_supported
    # CONTAGEM → unidade de apresentação em branco (nem €, nem %).
    assert measure_display_unit(MEASURE) == ""


def test_daily_measure_has_produzidas_synonyms():
    """Os sinónimos "produzidas/hoje/diário" são o que cura a abstenção do Cube."""
    spec = MEASURE_REGISTRY[MEASURE]
    blob = (spec.description + " | " + " | ".join(spec.synonyms)).lower()
    for needle in ("produzidas", "hoje", "diário", "produção do dia"):
        assert needle in blob, needle


def test_daily_distinct_from_monthly_ofs_fechadas():
    """A diária e a mensal são measures distintas (granularidades diferentes)."""
    monthly = "producao_lead_time_of.ofs_fechadas"
    assert monthly in MEASURE_REGISTRY
    assert MEASURE != monthly
    # A mensal também ganhou "produzidas" (fraseado mensal), mas continua mensal.
    assert "produzidas" in " ".join(
        MEASURE_REGISTRY[monthly].synonyms
    ).lower()


# ────────────────────────── 2. Card curado "hoje" ──────────────────────────


def test_dashboard_has_ofs_produzidas_hoje_card():
    from src.copilot.routers.ask_cube import _CARD_SPECS

    by_key = {c.key: c for c in _CARD_SPECS}
    assert "ofs_produzidas_hoje" in by_key
    card = by_key["ofs_produzidas_hoje"]
    assert card.measure == MEASURE
    assert card.period == "today"


# ────────────────────────── 3. _run_card period="today" ──────────────────────────


class _CapturingCube:
    """FakeCube que guarda o último payload e devolve `rows` fixas (sem rede)."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.last_payload: dict | None = None

    async def load(self, payload):
        self.last_payload = payload
        return CubeResult.model_validate(
            {"data": self._rows, "annotation": {}, "query": payload}
        )

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_run_card_today_builds_single_day_range_and_value():
    from src.copilot.routers.ask_cube import _CardSpec, _run_card

    spec = _CardSpec(
        key="ofs_produzidas_hoje", label="OFs produzidas hoje", unit="",
        measure=MEASURE, period="today",
    )
    cube = _CapturingCube([{MEASURE: 11}])
    today = _dt.date(2026, 6, 1)
    card = await _run_card(cube, spec, today)  # type: ignore[arg-type]

    # Valor honesto do dia (não o bucket do mês).
    assert card.status == "ok"
    assert card.value == 11.0
    assert card.unit == ""

    # A query pediu exactamente o dia de hoje (range [hoje, hoje]).
    tds = cube.last_payload["timeDimensions"]
    assert tds == [
        {"dimension": "producao_ofs_fechadas_dia.data",
         "dateRange": ["2026-06-01", "2026-06-01"]}
    ]


@pytest.mark.asyncio
async def test_run_card_today_no_data_when_empty():
    from src.copilot.routers.ask_cube import _CardSpec, _run_card

    spec = _CardSpec(
        key="ofs_produzidas_hoje", label="OFs produzidas hoje", unit="",
        measure=MEASURE, period="today",
    )
    cube = _CapturingCube([])  # nenhum fecho hoje
    card = await _run_card(cube, spec, _dt.date(2026, 6, 1))  # type: ignore[arg-type]
    assert card.status == "no_data"
    assert card.value is None
