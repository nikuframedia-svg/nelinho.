"""Q.136.B — planear a partir da FASE ATUAL (truncar a rota ao que falta).

~418 dos 777 barcos abertos estão a MEIO da produção; o CPO planeava a rota
COMPLETA (contava fases já feitas). O resolver passa a truncar a rota a
`sequence >= fase atual` (`OF_FP_ID`), com fallback seguro à rota completa
quando a fase atual está fora da rota (ex. estado "Não Laminado") ou ausente.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import (
    RoutingResolver,
    RoutingRow,
    _truncate_route_to_current,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _row(fase_id: str, seq: int) -> RoutingRow:
    return RoutingRow(
        fase_id=fase_id, fase_nome=fase_id, sequence=seq,
        duration_hours=1.0, source="history",
    )


# ---------------------------------------------------------------- helper puro

def test_truncate_none_returns_full_route():
    rota = [_row("1", 1), _row("2", 2), _row("18", 3)]
    assert [r.fase_id for r in _truncate_route_to_current(rota, None)] == ["1", "2", "18"]


def test_truncate_to_current_drops_done_phases():
    rota = [_row("1", 1), _row("2", 2), _row("18", 3), _row("40", 4)]
    out = _truncate_route_to_current(rota, "18")
    assert [r.fase_id for r in out] == ["18", "40"]  # inclui a fase atual


def test_truncate_current_out_of_route_keeps_full():
    rota = [_row("1", 1), _row("2", 2)]
    # "Não Laminado"/estado pré-produção não está na rota → rota completa
    assert [r.fase_id for r in _truncate_route_to_current(rota, "99")] == ["1", "2"]


# ---------------------------------------------------------- resolve() end-to-end

class _StubEngine:
    def __init__(self, phases):
        self._active_ingestion_id = "active"
        self._curated_data = {"active": {"order_phases": phases, "orders": [], "standards": []}}


def _phase(of_id, fase_id, ordem, horas):
    return SimpleNamespace(
        of_id=of_id, fase_id=fase_id, fase_nome=fase_id, ordem=ordem,
        horas_reais=horas, horas_finais=horas, horas_standard=None,
    )


def _resolver():
    state = FactoryState(tenant_id=TENANT)
    state.skill_matrix = {}
    return RoutingResolver(state)


def test_resolve_plans_from_current_phase(monkeypatch):
    phases = [
        _phase("O-1", "CORTE", ordem=1, horas=4.0),
        _phase("O-1", "LAM", ordem=4, horas=8.0),
        _phase("O-1", "QC", ordem=9, horas=2.0),
    ]
    r = _resolver()
    monkeypatch.setattr(r, "_semantic_engine", lambda: _StubEngine(phases))

    # barco a meio: fase atual = LAM → só LAM + QC (descarta CORTE já feito)
    ops = r.resolve({"of_id": "O-1", "modelo_id": "K1", "current_fase_id": "LAM"})
    assert [o.phase_id for o in ops] == ["LAM", "QC"]


def test_resolve_without_current_phase_full_route(monkeypatch):
    phases = [
        _phase("O-2", "CORTE", ordem=1, horas=4.0),
        _phase("O-2", "LAM", ordem=4, horas=8.0),
        _phase("O-2", "QC", ordem=9, horas=2.0),
    ]
    r = _resolver()
    monkeypatch.setattr(r, "_semantic_engine", lambda: _StubEngine(phases))

    ops = r.resolve({"of_id": "O-2", "modelo_id": "K1"})  # sem current_fase_id
    assert [o.phase_id for o in ops] == ["CORTE", "LAM", "QC"]


def test_resolve_current_phase_not_in_route_keeps_full(monkeypatch):
    phases = [
        _phase("O-3", "CORTE", ordem=1, horas=4.0),
        _phase("O-3", "LAM", ordem=4, horas=8.0),
    ]
    r = _resolver()
    monkeypatch.setattr(r, "_semantic_engine", lambda: _StubEngine(phases))

    # "NAO_LAMINADO" não está na rota → rota completa (o barco não começou)
    ops = r.resolve({"of_id": "O-3", "modelo_id": "K1", "current_fase_id": "NAO_LAMINADO"})
    assert [o.phase_id for o in ops] == ["CORTE", "LAM"]


# ---------------------------------------------------------- Q.136.A boats-only

class _CaptureResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _CaptureSession:
    """Captura o SQL gerado por _load_open_orders_db (sem BD)."""

    def __init__(self):
        self.sql_text = ""

    async def execute(self, stmt, params=None):
        self.sql_text = str(stmt)
        return _CaptureResult()


async def _captured_sql(scope: str) -> str:
    from src.plan.cpo.state import _load_open_orders_db
    sess = _CaptureSession()
    await _load_open_orders_db(sess, TENANT, scope=scope)
    return sess.sql_text


@pytest.mark.asyncio
async def test_scope_all_has_no_boats_filter_backcompat():
    """`scope=all` reproduz o legacy: SEM filtro de barco (LEFT JOIN não dropa
    linhas → mesmo conjunto que antes do Q.136)."""
    sql_all = await _captured_sql("all")
    # Q.157.H — critério deck+casco removido; scope=all nunca filtra barcos
    assert "P_QTDDECK" not in sql_all
    assert "P_QTDCASCO" not in sql_all
    assert "v_of_is_boat" not in sql_all


@pytest.mark.asyncio
async def test_scope_boats_only_applies_boat_criterion():
    """Q.157.H — scope=boats_only usa v_of_is_boat (raiz=Kayak AND OF_ID<10M),
    NÃO o critério deck+casco."""
    sql_boats = await _captured_sql("boats_only")
    # novo critério: join à view
    assert "v_of_is_boat" in sql_boats
    assert "is_boat" in sql_boats
    # critério antigo deve estar ausente
    assert "P_QTDDECK" not in sql_boats
    assert "P_QTDCASCO" not in sql_boats
    # ambos os scopes devolvem current_fase_id (planear-da-fase-atual)
    assert "current_fase_id" in sql_boats
