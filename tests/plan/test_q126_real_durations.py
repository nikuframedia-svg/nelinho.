"""Q.126.B — CPO lê durações + rotas reais de factory_raw.of_fp (ERP vivo).

Unit tests (sem BD) da camada de transformação dos loaders DB-backed e da
precedência de `median_duration_h` (par exato -> mediana por fase -> 2x). A
verificação contra a BD REAL está em `_audit/q126/verify_b.py` (medianas
confirmadas: Laminagem 4.32, Cura 17.38, Pintura 3.18) — aqui mockamos só o
`session.execute` para testar a lógica determinista, não os números reais.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.plan.cpo.state import (
    FactoryState,
    _load_historical_durations_routes_db,
    _load_molds_db,
    _load_skills_db,
)
from src.plan.services.routing_resolver import RoutingResolver


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Devolve resultados enfileirados por ordem de `execute` (raw text SQL)."""

    def __init__(self, *result_sets):
        self._results = list(result_sets)
        self._i = 0

    async def execute(self, *args, **kwargs):
        rows = self._results[self._i] if self._i < len(self._results) else []
        self._i += 1
        return _FakeResult(rows)


@pytest.mark.asyncio
async def test_load_durations_routes_builds_pairs_fase_and_routes():
    pair_rows = [
        {"model": "42366", "fase_id": "1", "fase_nome": "Laminagem", "seq": 10, "median_h": 4.32},
        {"model": "42366", "fase_id": "2", "fase_nome": "Cura", "seq": 11, "median_h": 17.38},
        {"model": "42366", "fase_id": "18", "fase_nome": "Pintura", "seq": 9, "median_h": 3.18},
    ]
    fase_rows = [
        {"fase_id": "1", "median_h": 4.32},
        {"fase_id": "2", "median_h": 17.38},
        {"fase_id": "18", "median_h": 3.18},
    ]
    session = _FakeSession(pair_rows, fase_rows)
    routes, by_pair, by_fase = await _load_historical_durations_routes_db(
        session, uuid4(),
    )

    assert by_pair[("1", "42366")] == pytest.approx(4.32)
    assert by_pair[("2", "42366")] == pytest.approx(17.38)
    assert by_fase["18"] == pytest.approx(3.18)
    # route ordered by FP_SEQUENCIA (Pintura seq=9 before Laminagem seq=10)
    seqs = [s["sequence"] for s in routes["42366"]]
    assert seqs == sorted(seqs)
    assert {s["fase_nome"] for s in routes["42366"]} == {"Laminagem", "Cura", "Pintura"}


@pytest.mark.asyncio
async def test_load_durations_routes_session_none_is_safe():
    routes, by_pair, by_fase = await _load_historical_durations_routes_db(
        None, uuid4(),
    )
    assert routes == {} and by_pair == {} and by_fase == {}


@pytest.mark.asyncio
async def test_load_molds_builds_by_model():
    # Q.174.F2 — o SELECT canónico devolve também em_manutencao (derivado
    # live de getMoldesAReparar: fase {13,14} com op aberta).
    rows = [
        {"molde_id": "501", "modelo_id": "42366", "em_manutencao": False, "tipo": "K1 Cinco"},
        {"molde_id": "502", "modelo_id": "42366", "em_manutencao": True, "tipo": ""},
        {"molde_id": "0", "modelo_id": "9999", "em_manutencao": False, "tipo": ""},  # mold 0 ignorado
    ]
    by_model, by_id = await _load_molds_db(_FakeSession(rows), uuid4())
    assert set(by_id) == {"501", "502"}
    assert {m.molde_id for m in by_model["42366"]} == {"501", "502"}
    assert "9999" not in by_model
    assert by_id["502"].em_manutencao is True  # molde em reparação marcado
    assert by_id["501"].em_manutencao is False


@pytest.mark.asyncio
async def test_load_skills_builds_matrix():
    rows = [
        {"fase_id": "1", "func_id": "20350"},
        {"fase_id": "1", "func_id": "20356"},
        {"fase_id": "2", "func_id": "20350"},
    ]
    matrix = await _load_skills_db(_FakeSession(rows), uuid4())
    assert matrix["1"] == {"20350", "20356"}
    assert matrix["2"] == {"20350"}


def test_median_duration_precedence_pair_then_fase_then_buffer(monkeypatch):
    monkeypatch.delenv("PRODPLAN_PLAN_STD_DURATION_BUFFER", raising=False)
    state = FactoryState(tenant_id=uuid4())
    state.historical_durations = {("1", "42366"): 4.32}
    state.historical_durations_by_fase = {"18": 3.18}

    # 1) par exato (fase, modelo) ganha
    assert state.median_duration_h("1", "42366", 99.0) == pytest.approx(4.32)
    # 2) mediana por fase (modelo desconhecido) — ainda REAL, não 2x
    assert state.median_duration_h("18", "novo_modelo", 99.0) == pytest.approx(3.18)
    # 3) sem dado real -> 2x buffer sintético
    assert state.median_duration_h("999", "999", 5.0) == pytest.approx(10.0)


def test_resolver_uses_db_route_with_history_db_source():
    state = FactoryState(tenant_id=uuid4())
    state.historical_routes_by_model = {
        "42366": [
            {"fase_id": "2", "fase_nome": "Cura", "sequence": 11, "duration_hours": 17.38},
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 10, "duration_hours": 4.32},
        ]
    }
    resolver = RoutingResolver(state)
    rows = resolver._history_for_model_db("42366")

    assert [r.fase_nome for r in rows] == ["Laminagem", "Cura"]  # ordenado por seq
    assert all(r.source == "history_db" for r in rows)
    assert rows[0].duration_hours == pytest.approx(4.32)
    # modelo sem rota DB -> lista vazia (cai no template standard)
    assert resolver._history_for_model_db("desconhecido") == []
