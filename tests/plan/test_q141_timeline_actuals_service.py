"""Q.141.A — TimelineActualsService: fases realizadas (barcos&fases) por intervalo.

A lógica de SHAPING é pura (sem BD) e é o foco dos testes; o caminho SQL é só
smoke com FakeSession (queue de mappings). Confirma o contrato dos items e o
comportamento best-effort. DAMP > DRY.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from src.plan.services.timeline_actuals_service import (
    TimelineActualsService,
    shape_actuals_items,
)

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _row(of_id, phase_id, inicio, fim, dur):
    return {"of_id": of_id, "phase_id": phase_id, "fase_inicio": inicio,
            "fase_fim": fim, "duration_min": dur}


# ─────────────────────────────────────────────────────────────────────────
# shape_actuals_items — puro
# ─────────────────────────────────────────────────────────────────────────

def test_shape_resolves_boat_and_phase_names():
    rows = [_row("OF1", "5", datetime(2026, 5, 1, 8), datetime(2026, 5, 1, 12), 240)]
    items = shape_actuals_items(
        rows, barco_by_of={"OF1": "K1 Vanquish"}, modelo_by_of={"OF1": "P99"},
        fase_by_id={"5": "Pintura Acabamento"},
    )
    assert len(items) == 1
    it = items[0]
    assert it["of_id"] == "OF1"
    assert it["barco_nome"] == "K1 Vanquish"
    assert it["modelo_id"] == "P99"
    assert it["phase_nome"] == "Pintura Acabamento"
    assert it["start"] == "2026-05-01T08:00:00"
    assert it["end"] == "2026-05-01T12:00:00"
    assert it["duration_min"] == 240.0
    assert it["source"] == "fase"
    assert it["worker_id"] is None and it["worker_nome"] is None


def test_shape_unresolved_boat_is_none_tolerated():
    rows = [_row("OFX", "9", datetime(2026, 5, 2, 8), None, None)]
    items = shape_actuals_items(rows, {}, {}, {})
    assert items[0]["barco_nome"] is None
    assert items[0]["modelo_id"] is None


def test_shape_missing_phase_name_falls_back_to_phase_id():
    rows = [_row("OF1", "77", datetime(2026, 5, 1, 8), datetime(2026, 5, 1, 9), 60)]
    items = shape_actuals_items(rows, {"OF1": "Recreio"}, {"OF1": "P1"}, fase_by_id={})
    assert items[0]["phase_nome"] == "77"  # cai no phase_id


def test_shape_in_progress_phase_has_no_end():
    rows = [_row("OF2", "1", datetime(2026, 5, 3, 7), None, None)]
    items = shape_actuals_items(rows, {"OF2": "K2"}, {"OF2": "P2"}, {"1": "Laminagem"})
    assert items[0]["end"] is None
    assert items[0]["duration_min"] is None
    assert items[0]["start"] == "2026-05-03T07:00:00"


def test_shape_empty_rows_is_empty():
    assert shape_actuals_items([], {}, {}, {}) == []


# ─────────────────────────────────────────────────────────────────────────
# Service — best-effort
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_actuals_items_none_session_is_empty():
    svc = TimelineActualsService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]
    items, truncated = await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7))
    assert items == []
    assert truncated is False


# O serviço usa `.execute(...).mappings().all()`; um fake mínimo que devolve
# por ordem as filas enfileiradas cobre o caminho SQL sem BD real.
class _MapResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)


class _MapSession:
    def __init__(self, queues):
        self._queues = list(queues)

    async def execute(self, *_a, **_k):
        return _MapResult(self._queues.pop(0) if self._queues else [])


@pytest.mark.asyncio
async def test_actuals_items_smoke_with_fake_session():
    session = _MapSession([
        # 1ª execute → fases_of_history; 2ª → nomes OF; 3ª → nomes fase.
        [_row("OF1", "5", datetime(2026, 5, 1, 8), datetime(2026, 5, 1, 12), 240)],
        [{"of_id": "OF1", "modelo_id": "P99", "barco_nome": "K1"}],
        [{"fase_id": "5", "fase_nome": "Pintura Acabamento"}],
    ])

    svc = TimelineActualsService(session, _TENANT)  # type: ignore[arg-type]
    items, truncated = await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7), cap=100)

    assert truncated is False
    assert len(items) == 1
    assert items[0]["barco_nome"] == "K1"
    assert items[0]["phase_nome"] == "Pintura Acabamento"


@pytest.mark.asyncio
async def test_actuals_items_truncated_flag():
    rows = [_row(f"OF{i}", "5", datetime(2026, 5, 1, 8), None, None) for i in range(3)]
    # cap=2 → service pede cap+1=3, recebe 3 → truncated=True, devolve 2.
    session = _MapSession([rows, [], []])
    svc = TimelineActualsService(session, _TENANT)  # type: ignore[arg-type]
    items, truncated = await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7), cap=2)
    assert truncated is True
    assert len(items) == 2
