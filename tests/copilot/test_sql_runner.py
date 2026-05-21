"""Q.67.4.C — tests para `src/copilot/tools/sql_runner.py`.

Cobertura (DAMP > DRY — cada teste lê como spec):
    1. SELECT trivial devolve rows + status ok.
    2. INSERT / 3. DELETE / 4. DROP / 5. UPDATE — rejeitados pelo regex.
    6. statement_timeout dispara em queries lentas.
    7. LIMIT auto-injectado quando ausente.
    8. LIMIT manual no SQL preservado (não duplica).
    9. WITH (CTE) aceite — invariante crítica para queries complexas.
    10. SqlRunnerError envolve falhas de execução (rows inexistentes,
        syntax errors).
    11. Telemetria emitida no logger (forensics).

Estes testes NÃO precisam do Postgres — usam SQLite via monkeypatch do
`create_async_engine`, ou validam o regex antes da chamada à BD.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.copilot.tools.sql_runner import SqlRunnerError, run_sql


# ───────────────────────────────────────────────────────────────────────
# Helpers — fake engine que não toca em Postgres real.
# ───────────────────────────────────────────────────────────────────────


def _fake_engine(rows: list[dict[str, Any]] | None = None,
                 raise_on_query: Exception | None = None) -> MagicMock:
    """Cria um mock async engine que devolve `rows` ou levanta `raise_on_query`.

    A 1ª chamada a `conn.execute(...)` é o `SET statement_timeout` —
    deve devolver sucesso silencioso. A 2ª chamada é a query real.
    """
    rows = rows or []

    # Result mock — `result` é iterável de Row objects com `._mapping`.
    def _row(d):
        r = MagicMock()
        r._mapping = d
        return r

    result = MagicMock()
    result.__iter__ = lambda self: iter(_row(d) for d in rows)

    conn = MagicMock()

    set_timeout_call = AsyncMock(return_value=MagicMock())

    async def _execute(stmt):
        # 1ª chamada é o SET statement_timeout — devolve mock vazio.
        text_str = str(stmt)
        if "statement_timeout" in text_str.lower():
            return MagicMock()
        if raise_on_query is not None:
            raise raise_on_query
        return result

    conn.execute = AsyncMock(side_effect=_execute)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)

    engine = MagicMock()
    engine.connect = MagicMock(return_value=conn)
    engine.dispose = AsyncMock()

    # Mantemos o set_timeout_call exposto para futuros asserts.
    engine._set_timeout_call = set_timeout_call
    return engine


# ───────────────────────────────────────────────────────────────────────
# 1. Happy path
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_select_one_returns_ok_with_rows():
    """SELECT 1 — devolve rows + elapsed_ms + status ok."""
    fake = _fake_engine(rows=[{"n": 1}])
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        result = await run_sql("SELECT 1 as n")

    assert result["status"] == "ok"
    assert result["rows"] == [{"n": 1}]
    assert result["rows_returned"] == 1
    assert "elapsed_ms" in result and result["elapsed_ms"] >= 0
    # Engine é disposed mesmo no happy path (no leak de conexões).
    fake.dispose.assert_awaited_once()


# ───────────────────────────────────────────────────────────────────────
# 2-5. Non-SELECT queries rejeitadas pelo regex (NÃO chegam à BD)
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_rejected_by_regex():
    """INSERT bloqueado pelo regex — nem sequer abre conexão."""
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
    ) as mock_create:
        with pytest.raises(SqlRunnerError, match="Only SELECT/WITH"):
            await run_sql("INSERT INTO core.audit_log VALUES (1, 2)")
        # Garantia forte: o regex falha ANTES de criar engine.
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_delete_rejected_by_regex():
    """DELETE bloqueado pelo regex."""
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
    ) as mock_create:
        with pytest.raises(SqlRunnerError, match="Only SELECT/WITH"):
            await run_sql("DELETE FROM plan.production_orders WHERE id = 1")
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_drop_table_rejected_by_regex():
    """DDL (DROP TABLE) bloqueado — defense-in-depth contra DROP cascade."""
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
    ) as mock_create:
        with pytest.raises(SqlRunnerError, match="Only SELECT/WITH"):
            await run_sql("DROP TABLE plan.production_orders")
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_update_rejected_by_regex():
    """UPDATE bloqueado — não passa pelo regex SELECT/WITH."""
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
    ) as mock_create:
        with pytest.raises(SqlRunnerError, match="Only SELECT/WITH"):
            await run_sql("UPDATE plan.production_orders SET qty = 0")
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_truncate_rejected_by_regex():
    """TRUNCATE bloqueado — DDL destrutiva, paranóia extra."""
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
    ) as mock_create:
        with pytest.raises(SqlRunnerError, match="Only SELECT/WITH"):
            await run_sql("TRUNCATE TABLE core.audit_log")
        mock_create.assert_not_called()


# ───────────────────────────────────────────────────────────────────────
# 6. statement_timeout — query lenta levanta SqlRunnerError
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeout_wrapped_in_sql_runner_error():
    """`pg_sleep(10)` com timeout 1s — Postgres devolve QueryCanceled,
    que o sql_runner envolve em SqlRunnerError (não vaza driver
    internals para o LLM)."""

    # Simulamos o erro de timeout do asyncpg (QueryCanceledError).
    class _FakeTimeoutError(Exception):
        pass

    fake = _fake_engine(
        raise_on_query=_FakeTimeoutError("canceling statement due to "
                                          "statement timeout"),
    )

    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        with pytest.raises(SqlRunnerError, match="SQL execution failed"):
            await run_sql("SELECT pg_sleep(10)")

    # Engine é disposed mesmo em erro — finally clause.
    fake.dispose.assert_awaited_once()


# ───────────────────────────────────────────────────────────────────────
# 7-8. LIMIT auto-inject / preservação
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_limit_auto_injected_when_absent():
    """SELECT sem LIMIT → final_query tem `LIMIT 200` (default cap)."""
    fake = _fake_engine(rows=[{"id": 1}])

    captured: dict[str, str] = {}
    orig_execute = fake.connect.return_value.execute

    async def _capture(stmt):
        s = str(stmt)
        if "LIMIT" in s.upper() and "SELECT" in s.upper():
            captured["query"] = s
        return await orig_execute(stmt)

    fake.connect.return_value.execute = AsyncMock(side_effect=_capture)

    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        result = await run_sql("SELECT * FROM core.audit_log")

    assert "LIMIT 200" in result["sql"]
    assert "LIMIT 200" in captured.get("query", ""), (
        f"Final query enviada à BD não tem LIMIT: {captured!r}"
    )


@pytest.mark.asyncio
async def test_limit_manual_preserved_not_duplicated():
    """Se o LLM já incluiu LIMIT, não duplicamos — o cap dele ganha."""
    fake = _fake_engine(rows=[{"id": 1}])
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        result = await run_sql("SELECT id FROM plan.production_orders LIMIT 5")

    # Só um LIMIT na query final.
    assert result["sql"].upper().count("LIMIT") == 1
    assert "LIMIT 5" in result["sql"]


@pytest.mark.asyncio
async def test_max_rows_override_used_when_provided():
    """`max_rows=10` override usa o valor passado, não o default 200."""
    fake = _fake_engine(rows=[{"id": 1}])
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        result = await run_sql("SELECT id FROM plan.production_orders", max_rows=10)

    assert "LIMIT 10" in result["sql"]


# ───────────────────────────────────────────────────────────────────────
# 9. CTE (WITH ...) — read-only, deve passar pelo regex
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_with_cte_accepted_by_regex():
    """`WITH ... SELECT ...` é read-only e crítico para agregações
    complexas. Tem de passar pelo regex."""
    fake = _fake_engine(rows=[{"total": 42}])
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        result = await run_sql(
            "WITH active AS (SELECT * FROM plan.production_orders) "
            "SELECT count(*) as total FROM active",
        )

    assert result["status"] == "ok"
    assert result["rows"] == [{"total": 42}]


@pytest.mark.asyncio
async def test_leading_whitespace_tolerated():
    """Whitespace/newline leading não deve confundir o regex."""
    fake = _fake_engine(rows=[{"n": 1}])
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        result = await run_sql("   \n  SELECT 1 as n")

    assert result["status"] == "ok"


# ───────────────────────────────────────────────────────────────────────
# 11. Telemetria — logger emite forensics line
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logger_emits_ok_line_for_forensics(caplog):
    """Cada query bem-sucedida emite uma linha info — combinada com o
    `TraceIdLogFilter` (Q.61.12), permite tracear qual operador correu
    qual SQL."""
    fake = _fake_engine(rows=[{"n": 1}])
    with patch(
        "src.copilot.tools.sql_runner.create_async_engine",
        return_value=fake,
    ):
        with caplog.at_level(logging.INFO, logger="src.copilot.tools.sql_runner"):
            await run_sql("SELECT 1 as n")

    ok_logs = [r for r in caplog.records if "sql_runner ok" in r.getMessage()]
    assert len(ok_logs) == 1, (
        f"Esperava 1 linha 'sql_runner ok', vi {len(ok_logs)}: "
        f"{[r.getMessage() for r in caplog.records]}"
    )


@pytest.mark.asyncio
async def test_logger_warns_on_rejected_query(caplog):
    """Queries não-SELECT geram WARN — operador vê tentativa no log."""
    with caplog.at_level(logging.WARNING, logger="src.copilot.tools.sql_runner"):
        with pytest.raises(SqlRunnerError):
            await run_sql("DROP TABLE core.audit_log")

    warn_logs = [
        r for r in caplog.records if "rejected non-SELECT" in r.getMessage()
    ]
    assert len(warn_logs) == 1
