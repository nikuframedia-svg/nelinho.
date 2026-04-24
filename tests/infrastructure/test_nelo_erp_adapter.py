"""Sprint B.3 — NeloERPAdapter unit tests.

The real Nelo ERP lives on a separate LAN server — tests must run
without one. We swap the `AsyncEngine` for a tiny fake that echoes the
rows we seed, so SQL strings and param binding get exercised without
needing `aioodbc` installed.
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

    def first(self) -> Optional[Any]:
        return self._rows[0] if self._rows else None

    def scalar(self) -> Any:
        if not self._rows:
            return None
        first = self._rows[0]
        # Health check seeds [{"one": 1}] — return the first value so
        # `result.scalar()` behaves like SQLAlchemy's real Result.
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
        self._engine.calls.append({
            "sql": str(stmt),
            "params": dict(params or {}),
        })
        # Use the head of the queued rows (or empty) for this call.
        if self._engine.queued_rows:
            rows = self._engine.queued_rows.pop(0)
        else:
            rows = []
        return _FakeResult(rows)


class _FakeEngine:
    """Stand-in for SQLAlchemy's AsyncEngine.

    Queue rows the next `execute(...)` should return; read `calls` to
    assert how the adapter phrased its query.
    """

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.queued_rows: List[List[Dict[str, Any]]] = []
        self.disposed = False

    def queue(self, rows: List[Dict[str, Any]]) -> None:
        self.queued_rows.append(list(rows))

    def connect(self) -> _FakeConnection:
        # SQLAlchemy's `engine.connect()` returns an async context manager;
        # our fake is itself one.
        return _FakeConnection(self)

    async def dispose(self) -> None:
        self.disposed = True


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
# health_check
# ---------------------------------------------------------------------------


def test_health_check_returns_true_when_select_1_roundtrips(adapter, fake_engine):
    fake_engine.queue([{"one": 1}])
    assert asyncio.run(adapter.health_check()) is True
    # Verify the adapter issued the SELECT 1 probe, not some other query.
    call = fake_engine.calls[0]
    assert "SELECT 1" in call["sql"]


def test_health_check_returns_false_on_unexpected_value(adapter, fake_engine):
    fake_engine.queue([{"one": 0}])
    assert asyncio.run(adapter.health_check()) is False


def test_health_check_returns_false_when_empty(adapter, fake_engine):
    fake_engine.queue([])
    assert asyncio.run(adapter.health_check()) is False


def test_health_check_returns_false_on_driver_error(adapter, fake_engine, monkeypatch):
    async def _boom(*_a, **_kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(fake_engine, "connect", lambda: _BoomContext())
    assert asyncio.run(adapter.health_check()) is False


class _BoomContext:
    async def __aenter__(self):
        raise RuntimeError("cannot connect")

    async def __aexit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# fetch_orders — SQL shape + params
# ---------------------------------------------------------------------------


def test_fetch_orders_default_has_no_where_clause(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_orders())
    call = fake_engine.calls[0]
    # No since filter → no WHERE clause; the TOP binding is always present.
    assert "WHERE" not in call["sql"]
    assert call["params"] == {"limit": 1000}


def test_fetch_orders_with_since_adds_where_clause(adapter, fake_engine):
    fake_engine.queue([])
    since = date(2024, 1, 1)
    asyncio.run(adapter.fetch_orders(since=since, limit=50))
    call = fake_engine.calls[0]
    assert "WHERE Of_DataCriacao >= :since" in call["sql"]
    assert call["params"] == {"limit": 50, "since": since}


def test_fetch_orders_returns_rows_as_dicts(adapter, fake_engine):
    fake_engine.queue([
        {"of_id": 1, "numero": "OF-001", "estado": "Aberta"},
        {"of_id": 2, "numero": "OF-002", "estado": "Em Producao"},
    ])
    rows = asyncio.run(adapter.fetch_orders())
    assert len(rows) == 2
    assert rows[0]["numero"] == "OF-001"
    assert rows[1]["estado"] == "Em Producao"


# ---------------------------------------------------------------------------
# fetch_workers — active_only toggle
# ---------------------------------------------------------------------------


def test_fetch_workers_active_only_default(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_workers())
    assert "WHERE Func_Activo = 1" in fake_engine.calls[0]["sql"]


def test_fetch_workers_all_when_flag_false(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_workers(active_only=False))
    assert "WHERE" not in fake_engine.calls[0]["sql"]


# ---------------------------------------------------------------------------
# fetch_standard_times — CoeficienteX preserved as `coeficiente_x`
# ---------------------------------------------------------------------------


def test_fetch_standard_times_includes_coeficiente_x_column(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_standard_times())
    sql = fake_engine.calls[0]["sql"]
    # Column list must carry the alias the profit module expects.
    assert "ProdutoFase_CoeficienteX AS coeficiente_x" in sql
    assert "ProdutoFase_Coeficiente  AS coeficiente" in sql


def test_fetch_standard_times_hydrates_to_dicts_with_cx(adapter, fake_engine):
    fake_engine.queue([
        {
            "produto_id": "P1", "fase_id": "LAM", "sequencia": 4,
            "coeficiente": 8.0, "coeficiente_x": 6.10,
        },
    ])
    rows = asyncio.run(adapter.fetch_standard_times())
    assert rows[0]["coeficiente_x"] == 6.10


# ---------------------------------------------------------------------------
# fetch_skill_matrix / fetch_molds / fetch_errors — SQL smoke
# ---------------------------------------------------------------------------


def test_fetch_skill_matrix_only_approved(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_skill_matrix())
    assert "FFA_Apto = 1" in fake_engine.calls[0]["sql"]


def test_fetch_molds_production_only_by_default(adapter, fake_engine):
    fake_engine.queue([])
    asyncio.run(adapter.fetch_molds())
    assert "Molde_Estado = 'Em Producao'" in fake_engine.calls[0]["sql"]


def test_fetch_errors_with_since(adapter, fake_engine):
    fake_engine.queue([])
    since = date(2025, 1, 1)
    asyncio.run(adapter.fetch_errors(since=since, limit=100))
    call = fake_engine.calls[0]
    assert "Erro_DataRegisto >= :since" in call["sql"]
    assert call["params"] == {"limit": 100, "since": since}


# ---------------------------------------------------------------------------
# Error handling — any driver exception becomes NeloERPError
# ---------------------------------------------------------------------------


def test_query_failure_wrapped_as_neloerperror(adapter, fake_engine, monkeypatch):
    async def _boom_connect(*_a, **_kw):
        raise RuntimeError("ODBC driver missing")

    monkeypatch.setattr(fake_engine, "connect", lambda: _BoomContext())

    with pytest.raises(NeloERPError, match="query failed"):
        asyncio.run(adapter.fetch_orders())


# ---------------------------------------------------------------------------
# close() disposes the engine
# ---------------------------------------------------------------------------


def test_close_disposes_engine(adapter, fake_engine):
    asyncio.run(adapter.close())
    assert fake_engine.disposed is True


# ---------------------------------------------------------------------------
# Shadow-mode compare helper
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
