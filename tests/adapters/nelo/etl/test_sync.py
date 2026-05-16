"""Q.20.A — ERP→Postgres sync orchestration tests.

The orchestrator is exercised without a SQL Server: ``run_nelo_sync``
short-circuits when ``settings.sqlserver_enabled`` is False, and the
mirror registry is a plain in-process dict.
"""

from __future__ import annotations

import pytest

from src.adapters.nelo.etl import sync as sync_mod
from src.adapters.nelo.etl.runner import EtlRunResult
from src.adapters.nelo.etl.sync import (
    register_mirror,
    registered_mirrors,
    run_nelo_sync,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Each test sees a pristine mirror registry."""
    saved = dict(sync_mod._MIRRORS)
    sync_mod._MIRRORS.clear()
    yield
    sync_mod._MIRRORS.clear()
    sync_mod._MIRRORS.update(saved)


def test_register_and_list_mirrors():
    async def _noop(**_kw):
        return EtlRunResult("x")

    register_mirror("alpha", _noop)
    register_mirror("beta", _noop)
    assert registered_mirrors() == ["alpha", "beta"]


async def test_run_nelo_sync_skipped_when_sqlserver_disabled(monkeypatch):
    """With ``sqlserver_enabled`` False the sync returns [] and never
    touches the adapter — the safe default in dev."""
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", False, raising=False)

    called = {"hit": False}

    async def _mirror(**_kw):
        called["hit"] = True
        return EtlRunResult("master")

    register_mirror("master", _mirror)

    results = await run_nelo_sync()
    assert results == []
    assert called["hit"] is False


async def test_run_nelo_sync_rejects_unknown_mirror(monkeypatch):
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", True, raising=False)
    with pytest.raises(ValueError, match="unknown mirror"):
        await run_nelo_sync(only=["does_not_exist"])
