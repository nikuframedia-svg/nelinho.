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
    aggregate_by_day,
    attach_workers,
    shape_actuals_items,
    shape_expeditions,
    worker_uuid,
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

# ─────────────────────────────────────────────────────────────────────────
# Q.141.C — shape_expeditions (barcos que saíram)
# ─────────────────────────────────────────────────────────────────────────

def test_shape_expeditions_basic():
    out = shape_expeditions([
        {"of_id": "117968", "transport_date": "2026-05-08", "modelo_id": "P1", "barco_nome": "K1"},
    ])
    assert out == [{
        "of_id": "117968", "barco_nome": "K1", "modelo_id": "P1",
        "transport_date": "2026-05-08", "source": "transp_of",
    }]


def test_shape_expeditions_unresolved_boat_tolerated():
    out = shape_expeditions([{"of_id": "9", "transport_date": "2026-05-09",
                              "modelo_id": None, "barco_nome": None}])
    assert out[0]["barco_nome"] is None


def test_shape_expeditions_empty():
    assert shape_expeditions([]) == []


# ─────────────────────────────────────────────────────────────────────────
# Q.141.D — aggregate_by_day
# ─────────────────────────────────────────────────────────────────────────

def _ai(of_id, barco, phase_id, phase_nome, start, dur, worker_id=None, worker_nome=None):
    return {"of_id": of_id, "barco_nome": barco, "phase_id": phase_id,
            "phase_nome": phase_nome, "start": start, "duration_min": dur,
            "worker_id": worker_id, "worker_nome": worker_nome}


def test_aggregate_by_barco_counts_days_and_orders():
    items = [
        _ai("OF1", "K1", "5", "Pintura", "2026-05-01T08:00", 60),
        _ai("OF1", "K1", "5", "Pintura", "2026-05-01T10:00", 30),
        _ai("OF1", "K1", "1", "Laminagem", "2026-05-02T08:00", 120),
        _ai("OF2", "C2", "1", "Laminagem", "2026-05-01T08:00", 90),
    ]
    lanes = aggregate_by_day(items, "barco")
    assert [l["group_key"] for l in lanes] == ["OF1", "OF2"]  # ops_total desc
    of1 = lanes[0]
    assert of1["ops_total"] == 3
    days = {d["date"]: d for d in of1["days"]}
    assert days["2026-05-01"]["ops_count"] == 2
    assert days["2026-05-01"]["total_duration_min"] == 90.0
    assert days["2026-05-02"]["ops_count"] == 1


def test_aggregate_by_operador_groups_nulls():
    items = [
        _ai("OF1", "K1", "5", "Pintura", "2026-05-01T08:00", 60, worker_id="u1", worker_nome="Ana"),
        _ai("OF2", "C2", "2", "Cura", "2026-05-01T09:00", 30),  # sem operador
    ]
    lanes = aggregate_by_day(items, "operador")
    keys = {l["group_key"] for l in lanes}
    assert "u1" in keys and "sem-operador" in keys
    sem = next(l for l in lanes if l["group_key"] == "sem-operador")
    assert sem["group_label"] == "Sem operador"


def test_aggregate_sample_capped():
    items = [_ai("OF1", "K1", "5", "Pintura", f"2026-05-0{i}T08:00", 10) for i in range(1, 9)]
    lanes = aggregate_by_day(items, "barco", sample_size=3)
    assert len(lanes[0]["sample"]) == 3
    assert lanes[0]["ops_total"] == 8


def test_aggregate_empty():
    assert aggregate_by_day([], "barco") == []


@pytest.mark.asyncio
async def test_expeditions_none_session_is_empty():
    svc = TimelineActualsService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]
    exps, trunc = await svc.expeditions(date(2026, 5, 1), date(2026, 5, 31))
    assert exps == [] and trunc is False


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


# ─────────────────────────────────────────────────────────────────────────
# Q.141.B — attach_workers (operadores via offp_eq+entidade)
# ─────────────────────────────────────────────────────────────────────────

def _it(offp_id):
    return {"offp_id": offp_id, "worker_id": None, "worker_nome": None}


def test_attach_workers_single_operator():
    out = attach_workers(
        [_it("P1")],
        [{"offp_id": "P1", "e_id": "20363", "is_chefe": True, "nome": "Carlos"}],
    )
    assert out[0]["worker_nome"] == "Carlos"
    assert out[0]["worker_id"] == str(worker_uuid("20363"))


def test_attach_workers_crew_chefe_first():
    out = attach_workers(
        [_it("P1")],
        [
            {"offp_id": "P1", "e_id": "2", "is_chefe": False, "nome": "Bruno"},
            {"offp_id": "P1", "e_id": "1", "is_chefe": True, "nome": "Ana"},
        ],
    )
    assert out[0]["worker_nome"] == "Ana + Bruno"  # chefe primeiro
    assert out[0]["worker_id"] == str(worker_uuid("1"))


def test_attach_workers_phase_without_crew_stays_none():
    out = attach_workers([_it("P9")], [])
    assert out[0]["worker_id"] is None
    assert out[0]["worker_nome"] is None


def test_attach_workers_no_name_falls_back_to_eid():
    out = attach_workers(
        [_it("P1")], [{"offp_id": "P1", "e_id": "999", "is_chefe": True, "nome": None}],
    )
    assert out[0]["worker_nome"] == "999"


def test_worker_uuid_is_deterministic_and_distinct():
    assert worker_uuid("20363") == worker_uuid("20363")
    assert worker_uuid("1") != worker_uuid("2")


@pytest.mark.asyncio
async def test_actuals_items_truncated_flag():
    rows = [_row(f"OF{i}", "5", datetime(2026, 5, 1, 8), None, None) for i in range(3)]
    # cap=2 → service pede cap+1=3, recebe 3 → truncated=True, devolve 2.
    session = _MapSession([rows, [], []])
    svc = TimelineActualsService(session, _TENANT)  # type: ignore[arg-type]
    items, truncated = await svc.actuals_items(date(2026, 5, 1), date(2026, 5, 7), cap=2)
    assert truncated is True
    assert len(items) == 2
