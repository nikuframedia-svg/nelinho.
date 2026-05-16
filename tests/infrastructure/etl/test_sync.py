"""Q.20.A — ERP sync orchestration tests.

Covers the registry + the `sqlserver_enabled=False` short-circuit. Live
mirrors are exercised by their own per-domain tests (Q.20.B…F).
"""

from __future__ import annotations

import pytest

from src.infrastructure.erp.etl import sync as sync_mod


def test_register_and_list_mirrors():
    async def _noop(**_kw):  # pragma: no cover - never called here
        return None

    sync_mod.register_mirror("zzz_test_mirror", _noop)
    try:
        assert "zzz_test_mirror" in sync_mod.registered_mirrors()
    finally:
        sync_mod._MIRRORS.pop("zzz_test_mirror", None)


async def test_run_nelo_sync_skips_when_disabled(monkeypatch):
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", False, raising=False)
    results = await sync_mod.run_nelo_sync()
    assert results == []


async def test_run_nelo_sync_rejects_unknown_mirror(monkeypatch):
    from src.shared.config import settings

    monkeypatch.setattr(settings, "sqlserver_enabled", True, raising=False)
    monkeypatch.setattr(settings, "sqlserver_url", "mssql+aioodbc://x", raising=False)
    with pytest.raises(ValueError, match="unknown mirror"):
        await sync_mod.run_nelo_sync(only=["does_not_exist"])
