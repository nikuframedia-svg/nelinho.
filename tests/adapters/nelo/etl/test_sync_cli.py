"""Q.20.G — ERP→Postgres sync CLI tests.

The CLI ``main()`` is exercised with ``run_nelo_sync`` mocked — no SQL
Server, no Postgres. Asserts argument parsing, the exit code contract
(0 = all ok / skipped, 1 = any mirror failed or bad args) and the
``--since`` watermark forwarding.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.adapters.nelo.etl.runner import EtlRunResult

# The CLI lives under scripts/ (not a package) — load it by path.
_CLI_PATH = Path(__file__).resolve().parents[4] / "scripts" / "sync_nelo_erp.py"
_spec = importlib.util.spec_from_file_location("sync_nelo_erp", _CLI_PATH)
sync_nelo_erp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_nelo_erp)


def _ok(source: str) -> EtlRunResult:
    r = EtlRunResult(source)
    r.status = "ok"
    r.rows_read = 10
    r.rows_inserted = 4
    return r


def _err(source: str) -> EtlRunResult:
    r = EtlRunResult(source)
    r.status = "error"
    r.error = "RuntimeError: boom"
    return r


async def test_cli_exit_0_when_all_mirrors_ok(monkeypatch, capsys):
    monkeypatch.setattr(
        sync_nelo_erp, "run_nelo_sync",
        AsyncMock(return_value=[_ok("master"), _ok("skills")]),
    )
    rc = await sync_nelo_erp.main([])
    assert rc == 0
    assert "[OK]" in capsys.readouterr().out


async def test_cli_exit_1_when_a_mirror_fails(monkeypatch, capsys):
    monkeypatch.setattr(
        sync_nelo_erp, "run_nelo_sync",
        AsyncMock(return_value=[_ok("master"), _err("quality")]),
    )
    rc = await sync_nelo_erp.main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "boom" in out


async def test_cli_exit_0_when_nothing_ran(monkeypatch, capsys):
    """sqlserver disabled → run_nelo_sync returns [] → SKIP, exit 0."""
    monkeypatch.setattr(
        sync_nelo_erp, "run_nelo_sync", AsyncMock(return_value=[]),
    )
    rc = await sync_nelo_erp.main([])
    assert rc == 0
    assert "[SKIP]" in capsys.readouterr().out


async def test_cli_rejects_bad_since(capsys):
    rc = await sync_nelo_erp.main(["--since", "not-a-date"])
    assert rc == 1
    assert "YYYY-MM-DD" in capsys.readouterr().out


async def test_cli_forwards_since_and_selectors(monkeypatch):
    spy = AsyncMock(return_value=[_ok("quality")])
    monkeypatch.setattr(sync_nelo_erp, "run_nelo_sync", spy)
    await sync_nelo_erp.main(["--only", "quality", "--since", "2026-01-15"])
    spy.assert_awaited_once()
    kwargs = spy.await_args.kwargs
    assert kwargs["only"] == ["quality"]
    assert kwargs["since"] == date(2026, 1, 15)


async def test_cli_forwards_exclude(monkeypatch):
    spy = AsyncMock(return_value=[_ok("master")])
    monkeypatch.setattr(sync_nelo_erp, "run_nelo_sync", spy)
    await sync_nelo_erp.main(["--exclude", "time_mining"])
    assert spy.await_args.kwargs["exclude"] == ["time_mining"]
