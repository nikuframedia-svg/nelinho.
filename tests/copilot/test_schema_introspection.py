"""Tests for src.copilot.tools.schema_introspection — Q.67.4.B.

Strategy
--------

The introspection functions issue raw SQL against the live engine. We
don't want test runs to depend on a live Postgres (dev DBs go up and
down — Q.61.16 made this explicit), so we patch
``src.copilot.tools.schema_introspection`` to use a fake engine whose
``connect()`` returns a fake async connection that scripts the SQL
result for each query.

A second batch of tests is marked ``@pytest.mark.smoke_db`` and runs
against the real dev DB when reachable, skipping cleanly otherwise.
This gives us the DAMP-style "spec read on its own" without making CI
brittle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
from unittest.mock import MagicMock

import pytest

from src.copilot.tools import schema_introspection as si


# ---------------------------------------------------------------------------
# Fake engine — scripts SQL responses in order
# ---------------------------------------------------------------------------


class _FakeRow:
    """Behaves like a SQLAlchemy Row: attribute access AND ._mapping."""

    def __init__(self, mapping: Dict[str, Any]) -> None:
        self._mapping = mapping
        for k, v in mapping.items():
            setattr(self, k, v)


class _FakeResult:
    def __init__(self, rows: Sequence[Dict[str, Any]]) -> None:
        self._rows = [_FakeRow(r) for r in rows]

    def __iter__(self):
        return iter(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(
        self,
        scripted: List[Sequence[Dict[str, Any]]],
        executed: List[tuple[str, Dict[str, Any]]],
    ) -> None:
        # Both ``scripted`` and ``executed`` are SHARED lists owned by
        # the engine — every connection drains and appends to the same
        # state. This mirrors a real engine handing out connections
        # against one DB.
        self._scripted = scripted
        self.executed = executed

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, stmt: Any, params: Optional[Dict[str, Any]] = None):
        # ``stmt`` is a ``text()`` clause; we keep its compiled form for
        # assertions, but the fake plays back results by call order, not
        # by SQL inspection (keeps the test as a contract, not a
        # mirror of the implementation).
        sql_str = str(stmt)
        self.executed.append((sql_str, params or {}))
        if not self._scripted:
            return _FakeResult([])
        return _FakeResult(self._scripted.pop(0))


class _FakeEngine:
    def __init__(self, scripted: List[Sequence[Dict[str, Any]]]) -> None:
        # Mutable shared state — drained across all `connect()` calls.
        self.scripted: List[Sequence[Dict[str, Any]]] = list(scripted)
        self.executed: List[tuple[str, Dict[str, Any]]] = []
        self.last_conn: Optional[_FakeConn] = None

    def connect(self) -> _FakeConn:
        conn = _FakeConn(self.scripted, self.executed)
        self.last_conn = conn
        return conn


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts with a clean cache so we exercise the SQL path."""
    si._cache_clear()
    yield
    si._cache_clear()


def _patch_engine(monkeypatch, scripted: List[Sequence[Dict[str, Any]]]):
    """Install a fake engine that scripts SQL results in order."""
    engine = _FakeEngine(scripted)

    # The function does ``from src.shared.database import engine``
    # at call time (lazy import), so we patch the module-level name.
    fake_db_module = MagicMock()
    fake_db_module.engine = engine
    monkeypatch.setitem(
        __import__("sys").modules, "src.shared.database", fake_db_module,
    )
    return engine


# ---------------------------------------------------------------------------
# list_database_tables
# ---------------------------------------------------------------------------


class TestListDatabaseTables:
    """Q.67.4.B — tool 1: list tables with row counts + comments."""

    async def test_returns_rows_when_no_schema_filter(self, monkeypatch):
        engine = _patch_engine(
            monkeypatch,
            scripted=[
                [
                    {
                        "schema": "plan",
                        "name": "production_orders",
                        "row_count": 1234,
                        "comment": "Production orders fact table",
                    },
                    {
                        "schema": "quality",
                        "name": "rework_entry",
                        "row_count": 56,
                        "comment": None,
                    },
                ],
            ],
        )

        rows = await si.list_database_tables()

        assert len(rows) == 2
        assert rows[0] == {
            "schema": "plan",
            "name": "production_orders",
            "row_count": 1234,
            "comment": "Production orders fact table",
        }
        # No schema filter -> :schema param is None.
        _, params = engine.last_conn.executed[0]
        assert params == {"schema": None}

    async def test_filters_by_schema(self, monkeypatch):
        engine = _patch_engine(
            monkeypatch,
            scripted=[
                [
                    {
                        "schema": "plan",
                        "name": "production_orders",
                        "row_count": 1234,
                        "comment": None,
                    },
                ],
            ],
        )

        rows = await si.list_database_tables(schema="plan")

        assert len(rows) == 1
        assert rows[0]["schema"] == "plan"
        _, params = engine.last_conn.executed[0]
        assert params == {"schema": "plan"}

    async def test_cache_hit_skips_db(self, monkeypatch):
        engine = _patch_engine(
            monkeypatch,
            scripted=[
                [
                    {
                        "schema": "plan",
                        "name": "production_orders",
                        "row_count": 10,
                        "comment": None,
                    },
                ],
            ],
        )

        first = await si.list_database_tables(schema="plan")
        # Second call must NOT consume another scripted batch — if it
        # did, _FakeResult would be empty and we'd see an empty list.
        second = await si.list_database_tables(schema="plan")

        assert first == second
        # Only ONE SQL execution recorded on the original fake conn.
        assert len(engine.last_conn.executed) == 1

    async def test_cache_keyed_per_schema(self, monkeypatch):
        # Two different ``schema`` arguments are independent cache keys.
        engine = _patch_engine(
            monkeypatch,
            scripted=[
                [{"schema": "plan", "name": "a", "row_count": 1, "comment": None}],
                [{"schema": "quality", "name": "b", "row_count": 2, "comment": None}],
            ],
        )

        plan_rows = await si.list_database_tables(schema="plan")
        quality_rows = await si.list_database_tables(schema="quality")

        assert plan_rows[0]["schema"] == "plan"
        assert quality_rows[0]["schema"] == "quality"

    async def test_cache_expires_after_ttl(self, monkeypatch):
        # Drop the TTL to 0 so the second call always sees the cache as
        # stale — exercises the time-based invalidation path.
        monkeypatch.setattr(si, "_CACHE_TTL_SECONDS", 0)
        engine = _patch_engine(
            monkeypatch,
            scripted=[
                [{"schema": "plan", "name": "a", "row_count": 1, "comment": None}],
                [{"schema": "plan", "name": "a", "row_count": 2, "comment": None}],
            ],
        )

        first = await si.list_database_tables(schema="plan")
        second = await si.list_database_tables(schema="plan")

        assert first[0]["row_count"] == 1
        assert second[0]["row_count"] == 2  # cache expired, fresh value
        assert len(engine.last_conn.executed) == 2

    async def test_row_count_coerces_none_to_zero(self, monkeypatch):
        # New (empty) tables have NULL reltuples — must not crash.
        _patch_engine(
            monkeypatch,
            scripted=[
                [{"schema": "plan", "name": "x", "row_count": None, "comment": None}],
            ],
        )

        rows = await si.list_database_tables()
        assert rows[0]["row_count"] == 0


# ---------------------------------------------------------------------------
# describe_table
# ---------------------------------------------------------------------------


class TestDescribeTable:
    """Q.67.4.B — tool 2: describe one table (cols, PK, FKs, sample)."""

    async def test_unknown_table_returns_exists_false(self, monkeypatch):
        _patch_engine(monkeypatch, scripted=[[]])  # table lookup yields nothing

        result = await si.describe_table("plan", "ghost_table")

        assert result["exists"] is False
        assert result["columns"] == []
        assert result["primary_key"] == []
        assert result["foreign_keys"] == []
        assert result["sample"] == []
        # schema/name still echoed back so the LLM can quote them.
        assert result["schema"] == "plan"
        assert result["name"] == "ghost_table"

    async def test_known_table_returns_full_metadata(self, monkeypatch):
        _patch_engine(
            monkeypatch,
            scripted=[
                # 1. table lookup
                [{"oid": 42, "comment": "Production orders"}],
                # 2. columns
                [
                    {
                        "name": "id",
                        "data_type": "uuid",
                        "udt": "uuid",
                        "is_nullable": "NO",
                        "default": "gen_random_uuid()",
                        "comment": None,
                        "pos": 1,
                    },
                    {
                        "name": "tenant_id",
                        "data_type": "uuid",
                        "udt": "uuid",
                        "is_nullable": "NO",
                        "default": None,
                        "comment": None,
                        "pos": 2,
                    },
                    {
                        "name": "boat_count",
                        "data_type": "integer",
                        "udt": "int4",
                        "is_nullable": "YES",
                        "default": "0",
                        "comment": "Number of boats",
                        "pos": 3,
                    },
                ],
                # 3. PK
                [{"name": "id"}],
                # 4. FKs
                [
                    {
                        "column": "tenant_id",
                        "ref_schema": "public",
                        "ref_table": "tenants",
                        "ref_column": "id",
                    },
                ],
                # 5. sample
                [
                    {"id": "uuid-1", "tenant_id": "t1", "boat_count": 14},
                    {"id": "uuid-2", "tenant_id": "t1", "boat_count": 15},
                    {"id": "uuid-3", "tenant_id": "t1", "boat_count": 16},
                ],
            ],
        )

        result = await si.describe_table("plan", "production_orders")

        assert result["exists"] is True
        assert result["comment"] == "Production orders"
        assert [c["name"] for c in result["columns"]] == [
            "id", "tenant_id", "boat_count",
        ]
        # nullability/default/type carried through
        assert result["columns"][0]["nullable"] is False
        assert result["columns"][0]["default"] == "gen_random_uuid()"
        assert result["columns"][2]["nullable"] is True
        assert result["columns"][2]["type"] == "integer"

        assert result["primary_key"] == ["id"]
        assert result["foreign_keys"] == [
            {
                "column": "tenant_id",
                "ref_schema": "public",
                "ref_table": "tenants",
                "ref_column": "id",
            },
        ]
        assert len(result["sample"]) == 3
        assert result["sample"][0]["boat_count"] == 14

    async def test_pii_columns_are_masked_in_sample(self, monkeypatch):
        # Column comment containing "sensitive" or "pii" triggers
        # masking — the column itself is still listed.
        _patch_engine(
            monkeypatch,
            scripted=[
                [{"oid": 1, "comment": None}],
                [
                    {
                        "name": "id",
                        "data_type": "uuid",
                        "udt": "uuid",
                        "is_nullable": "NO",
                        "default": None,
                        "comment": None,
                        "pos": 1,
                    },
                    {
                        "name": "nif",
                        "data_type": "text",
                        "udt": "text",
                        "is_nullable": "YES",
                        "default": None,
                        "comment": "PII — taxpayer number",
                        "pos": 2,
                    },
                    {
                        "name": "address",
                        "data_type": "text",
                        "udt": "text",
                        "is_nullable": "YES",
                        "default": None,
                        "comment": "Sensitive personal data",
                        "pos": 3,
                    },
                    {
                        "name": "public_note",
                        "data_type": "text",
                        "udt": "text",
                        "is_nullable": "YES",
                        "default": None,
                        "comment": "Free-form note",
                        "pos": 4,
                    },
                ],
                [],  # no PK
                [],  # no FKs
                [
                    {
                        "id": "u1",
                        "nif": "123456789",
                        "address": "Rua X",
                        "public_note": "hello",
                    },
                ],
            ],
        )

        result = await si.describe_table("hr", "employees")

        # Both PII columns surface in `columns`...
        names = [c["name"] for c in result["columns"]]
        assert "nif" in names
        assert "address" in names
        # ...but their values are masked in the sample.
        sample = result["sample"][0]
        assert sample["nif"] == "***"
        assert sample["address"] == "***"
        # Non-PII columns untouched.
        assert sample["public_note"] == "hello"
        assert sample["id"] == "u1"

    async def test_user_defined_types_resolve_to_udt(self, monkeypatch):
        # Enums / arrays: ``data_type`` is "USER-DEFINED" / "ARRAY" —
        # we should expose the udt_name instead.
        _patch_engine(
            monkeypatch,
            scripted=[
                [{"oid": 1, "comment": None}],
                [
                    {
                        "name": "status",
                        "data_type": "USER-DEFINED",
                        "udt": "order_status",
                        "is_nullable": "NO",
                        "default": None,
                        "comment": None,
                        "pos": 1,
                    },
                    {
                        "name": "tags",
                        "data_type": "ARRAY",
                        "udt": "_text",
                        "is_nullable": "YES",
                        "default": None,
                        "comment": None,
                        "pos": 2,
                    },
                ],
                [],
                [],
                [],
            ],
        )

        result = await si.describe_table("plan", "production_orders")

        assert result["columns"][0]["type"] == "order_status"
        assert result["columns"][1]["type"] == "_text"

    async def test_sample_failure_does_not_break_metadata(self, monkeypatch):
        # If the sample SELECT raises (RLS rejection, exotic types),
        # we still return columns/PK/FKs and an empty sample.
        engine = _FakeEngine(
            scripted=[
                [{"oid": 1, "comment": None}],
                [
                    {
                        "name": "id",
                        "data_type": "uuid",
                        "udt": "uuid",
                        "is_nullable": "NO",
                        "default": None,
                        "comment": None,
                        "pos": 1,
                    },
                ],
                [{"name": "id"}],
                [],
            ],
        )

        # Wrap the conn so the 5th execute (sample) raises.
        original_connect = engine.connect
        calls = {"n": 0}

        def boom_connect():
            conn = original_connect()
            orig_execute = conn.execute

            async def execute(stmt, params=None):
                calls["n"] += 1
                if calls["n"] == 5:
                    raise RuntimeError("RLS denied")
                return await orig_execute(stmt, params)

            conn.execute = execute  # type: ignore[assignment]
            return conn

        engine.connect = boom_connect  # type: ignore[assignment]

        fake_db_module = MagicMock()
        fake_db_module.engine = engine
        monkeypatch.setitem(
            __import__("sys").modules, "src.shared.database", fake_db_module,
        )

        result = await si.describe_table("plan", "production_orders")

        assert result["exists"] is True
        assert result["columns"][0]["name"] == "id"
        assert result["sample"] == []  # graceful


# ---------------------------------------------------------------------------
# Smoke against live dev DB (skipped when DB is offline)
# ---------------------------------------------------------------------------


async def _db_is_reachable() -> bool:
    try:
        from sqlalchemy import text
        from src.shared.database import engine as real_engine
        async with real_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.smoke_db
async def test_smoke_list_database_tables_against_dev_db():
    """If dev DB is up, listing tables should yield SOMETHING.

    Skipped when DB is unreachable (Q.61.16 — DB may be down during
    test runs; this is allowed)."""
    if not await _db_is_reachable():
        pytest.skip("dev DB not reachable")
    rows = await si.list_database_tables()
    assert isinstance(rows, list)
    # Bootstrapped dev DB has at least alembic_version + tenants.
    names = [(r["schema"], r["name"]) for r in rows]
    assert any(n[1] == "alembic_version" for n in names) or len(rows) >= 1
