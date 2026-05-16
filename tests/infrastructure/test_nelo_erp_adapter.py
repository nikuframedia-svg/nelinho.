"""Q.20.A — NeloERPAdapter unit tests (views-based).

The real Nelo ERP lives on a separate LAN server — tests run without one.
We swap the `AsyncEngine` for a tiny fake that echoes seeded rows, so the
SQL strings + param binding get exercised without `aioodbc` installed.

Q.20: the adapter now targets `vw_pp1_*` views, not raw ERP tables.
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from src.infrastructure.erp.sqlserver.nelo_erp import (
    NeloERPAdapter,
    NeloERPError,
    compare_shadow,
)


# ---------------------------------------------------------------------------
# Fake async engine — captures the SQL + params the adapter emits
# ---------------------------------------------------------------------------


class _FakeMappingsResult:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> List[Dict[str, Any]]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappingsResult:
        return _FakeMappingsResult(self._rows)

    def scalar(self) -> Any:
        if not self._rows:
            return None
        first = self._rows[0]
        if isinstance(first, dict):
            return next(iter(first.values()))
        return first


class _FakeConnection:
    def __init__(self, engine: "_FakeEngine") -> None:
        self._engine = engine

    async def __aenter__(self) -> "_FakeConnection":
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def execute(self, stmt, params=None) -> _FakeResult:
        self._engine.calls.append({"sql": str(stmt), "params": dict(params or {})})
        if self._engine.queued_rows:
            rows = self._engine.queued_rows.pop(0)
        else:
            rows = []
        return _FakeResult(rows)


class _FakeEngine:
    """Stand-in for SQLAlchemy's AsyncEngine."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.queued_rows: List[List[Dict[str, Any]]] = []
        self.disposed = False

    def queue(self, rows: List[Dict[str, Any]]) -> None:
        self.queued_rows.append(list(rows))

    def connect(self) -> _FakeConnection:
        return _FakeConnection(self)

    async def dispose(self) -> None:
        self.disposed = True


class _BoomContext:
    async def __aenter__(self):
        raise RuntimeError("cannot connect")

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def fake_engine() -> _FakeEngine:
    return _FakeEngine()


@pytest.fixture
def adapter(fake_engine: _FakeEngine) -> NeloERPAdapter:
    return NeloERPAdapter(fake_engine, query_timeout_s=15)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Construction / settings wiring
# ---------------------------------------------------------------------------


def test_from_settings_raises_when_url_missing():
    settings = SimpleNamespace(
        sqlserver_url=None, sqlserver_pool_size=5, sqlserver_query_timeout_s=30,
    )
    with pytest.raises(NeloERPError, match="sqlserver_url"):
        NeloERPAdapter.from_settings(settings)


# ---------------------------------------------------------------------------
# health_check / view_available
# ---------------------------------------------------------------------------


def test_health_check_returns_true_when_select_1_roundtrips(adapter, fake_engine):
    fake_engine.queue([{"one": 1}])
    assert asyncio.run(adapter.health_check()) is True
    assert "SELECT 1" in fake_engine.calls[0]["sql"]


def test_health_check_returns_false_on_unexpected_value(adapter, fake_engine):
    fake_engine.queue([{"one": 0}])
    assert asyncio.run(adapter.health_check()) is False


def test_health_check_returns_false_when_empty(adapter, fake_engine):
    fake_engine.queue([])
    assert asyncio.run(adapter.health_check()) is False


def test_health_check_returns_false_on_driver_error(adapter, fake_engine, monkeypatch):
    monkeypatch.setattr(fake_engine, "connect", lambda: _BoomContext())
    assert asyncio.run(adapter.health_check()) is False


def test_view_available_probes_the_view(adapter, fake_engine):
    fake_engine.queue([{"col": 1}])
    assert asyncio.run(adapter.view_available("vw_pp1_produto")) is True
    sql = fake_engine.calls[0]["sql"]
    assert "SELECT TOP 1" in sql and "vw_pp1_produto" in sql


def test_view_available_rejects_unknown_view(adapter):
    with pytest.raises(NeloERPError, match="unknown view"):
        asyncio.run(adapter.view_available("vw_pp1_nope; DROP TABLE x"))


def test_view_available_false_when_view_missing(adapter, fake_engine, monkeypatch):
    monkeypatch.setattr(fake_engine, "connect", lambda: _BoomContext())
    assert asyncio.run(adapter.view_available("vw_pp1_moldes")) is False


# ---------------------------------------------------------------------------
# fetch_products / fetch_phases / fetch_workers — SQL shape + params
# ---------------------------------------------------------------------------


def test_fetch_products_targets_the_view(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_products(limit=2000))
    call = fake_engine.calls[0]
    assert "FROM vw_pp1_produto" in call["sql"]
    assert call["params"] == {"limit": 2000}


def test_fetch_products_hydrates_rows(adapter, fake_engine):
    fake_engine.queue([
        {"product_id": "P1", "product_code": "K1V", "product_name": "K1 Vanquish"},
    ])
    rows = asyncio.run(adapter.fetch_products())
    assert rows[0]["product_code"] == "K1V"


def test_fetch_phases_targets_phase_catalogue(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_phases())
    assert "FROM vw_pp1_fases_producao" in fake_engine.calls[0]["sql"]


def test_fetch_workers_active_only_default(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_workers())
    assert "WHERE activo = 1" in fake_engine.calls[0]["sql"]


def test_fetch_workers_all_when_flag_false(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_workers(active_only=False))
    assert "WHERE" not in fake_engine.calls[0]["sql"]


# ---------------------------------------------------------------------------
# fetch_product_phases — CoeficienteX preserved verbatim (money, not time)
# ---------------------------------------------------------------------------


def test_fetch_product_phases_keeps_coeficiente_x_column(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_product_phases())
    sql = fake_engine.calls[0]["sql"]
    assert "coeficiente_x" in sql
    assert "FROM vw_pp1_produto_fase" in sql


# ---------------------------------------------------------------------------
# fetch_employee_phases / fetch_components / fetch_molds — SQL smoke
# ---------------------------------------------------------------------------


def test_fetch_employee_phases_only_approved(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_employee_phases())
    sql = fake_engine.calls[0]["sql"]
    assert "apto = 1" in sql and "FROM vw_pp1_entidade_fase" in sql


def test_fetch_components_targets_bom_view(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_components())
    assert "FROM vw_pp1_produto_componente" in fake_engine.calls[0]["sql"]


def test_fetch_molds_targets_mold_view(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_molds())
    assert "FROM vw_pp1_moldes" in fake_engine.calls[0]["sql"]


# ---------------------------------------------------------------------------
# fetch_operations / fetch_quality_problems — incremental `since` filter
# ---------------------------------------------------------------------------


def test_fetch_operations_default_has_no_where(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_operations())
    assert "WHERE" not in fake_engine.calls[0]["sql"]


def test_fetch_operations_with_since_adds_where(adapter, fake_engine):
    fake_engine.queue([])
    since = date(2025, 1, 1)
    asyncio.run(adapter.fetch_operations(since=since, limit=500))
    call = fake_engine.calls[0]
    assert "fase_of_inicio >= :since" in call["sql"]
    assert call["params"] == {"limit": 500, "since": since}


def test_fetch_quality_problems_with_since(adapter, fake_engine):
    fake_engine.queue([])
    since = date(2025, 1, 1)
    asyncio.run(adapter.fetch_quality_problems(since=since, limit=100))
    call = fake_engine.calls[0]
    assert "data_registo >= :since" in call["sql"]
    assert call["params"] == {"limit": 100, "since": since}


def test_fetch_checklists_targets_checklist_view(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_checklists())
    assert "FROM vw_pp1_of_checklist" in fake_engine.calls[0]["sql"]


# ---------------------------------------------------------------------------
# Error handling — any driver exception becomes NeloERPError
# ---------------------------------------------------------------------------


def test_query_failure_wrapped_as_neloerperror(adapter, fake_engine, monkeypatch):
    monkeypatch.setattr(fake_engine, "connect", lambda: _BoomContext())
    with pytest.raises(NeloERPError, match="query failed"):
        asyncio.run(adapter.fetch_products())


def test_close_disposes_engine(adapter, fake_engine):
    asyncio.run(adapter.close())
    assert fake_engine.disposed is True


# ---------------------------------------------------------------------------
# Shadow / reconcile helper
# ---------------------------------------------------------------------------


def test_compare_shadow_reports_symmetric_differences():
    live = [{"of_id": 1}, {"of_id": 2}, {"of_id": 3}]
    curated = [{"of_id": 2}, {"of_id": 3}, {"of_id": 4}]
    result = asyncio.run(compare_shadow(live, curated, key="of_id"))
    assert result["live_count"] == 3
    assert result["curated_count"] == 3
    assert result["match_count"] == 2
    assert result["only_in_live"] == [1]
    assert result["only_in_curated"] == [4]
    assert "compared_at" in result


def test_compare_shadow_handles_empty_inputs():
    result = asyncio.run(compare_shadow([], [], key="of_id"))
    assert result["live_count"] == 0
    assert result["curated_count"] == 0
    assert result["only_in_live"] == []
    assert result["only_in_curated"] == []
