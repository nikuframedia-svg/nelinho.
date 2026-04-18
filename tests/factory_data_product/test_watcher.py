"""
Tests for src.factory_data_product.watcher.

Coverage:
- `_hash_file` streams SHA256 correctly
- `watcher_tick` is a no-op when env var unset (file_found=False)
- `watcher_tick` skips ingest when hash is unchanged
- `watcher_tick` triggers ingest on first run and on hash change
- `register_with_scheduler` is a no-op when env var unset
- `get_state` / `reset_state`
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.factory_data_product import watcher as watcher_mod


class _FakeIngestEngine:
    """Captures ingest calls without touching the real engine."""

    def __init__(self):
        self.calls = []
        self.last_result_id = uuid4()

    def ingest(self, file_path, source_type=None, created_by="watcher", auto_activate=False):
        self.calls.append({
            "file_path": str(file_path),
            "source_type": source_type,
            "created_by": created_by,
            "auto_activate": auto_activate,
        })
        return SimpleNamespace(
            ingestion_id=self.last_result_id,
            status=SimpleNamespace(value="succeeded"),
            total_rows_raw=100,
            total_rows_curated=80,
        )


@pytest.fixture(autouse=True)
def _reset_state():
    watcher_mod.reset_state()
    yield
    watcher_mod.reset_state()


class TestHashFile:
    def test_matches_hashlib_output(self, tmp_path):
        target = tmp_path / "sample.xlsx"
        payload = b"test content" * 1024
        target.write_bytes(payload)

        expected = hashlib.sha256(payload).hexdigest()
        assert watcher_mod._hash_file(target) == expected

    def test_handles_empty_file(self, tmp_path):
        target = tmp_path / "empty.xlsx"
        target.write_bytes(b"")
        assert watcher_mod._hash_file(target) == hashlib.sha256(b"").hexdigest()


class TestWatcherTick:
    @pytest.mark.asyncio
    async def test_no_op_when_env_unset(self, monkeypatch):
        monkeypatch.delenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, raising=False)
        summary = await watcher_mod.watcher_tick(engine=_FakeIngestEngine())
        assert summary["file_found"] is False
        assert summary["triggered_ingest"] is False
        assert summary["error"]

    @pytest.mark.asyncio
    async def test_no_op_when_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv(
            watcher_mod.DEFAULT_WATCH_PATH_ENV,
            str(tmp_path / "does_not_exist.xlsx"),
        )
        summary = await watcher_mod.watcher_tick(engine=_FakeIngestEngine())
        assert summary["file_found"] is False

    @pytest.mark.asyncio
    async def test_triggers_ingest_on_first_run(self, monkeypatch, tmp_path):
        f = tmp_path / "factory.xlsx"
        f.write_bytes(b"hello nelo")
        monkeypatch.setenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, str(f))

        engine = _FakeIngestEngine()
        summary = await watcher_mod.watcher_tick(engine=engine)

        assert summary["file_found"] is True
        assert summary["hash_changed"] is True
        assert summary["triggered_ingest"] is True
        assert summary["ingestion_id"] is not None
        assert len(engine.calls) == 1
        assert engine.calls[0]["file_path"] == str(f)

    @pytest.mark.asyncio
    async def test_skips_when_hash_unchanged(self, monkeypatch, tmp_path):
        f = tmp_path / "factory.xlsx"
        f.write_bytes(b"stable bytes")
        monkeypatch.setenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, str(f))

        engine = _FakeIngestEngine()
        await watcher_mod.watcher_tick(engine=engine)  # first tick triggers
        assert len(engine.calls) == 1

        summary2 = await watcher_mod.watcher_tick(engine=engine)  # same hash
        assert summary2["file_found"] is True
        assert summary2["hash_changed"] is False
        assert summary2["triggered_ingest"] is False
        assert len(engine.calls) == 1  # no new ingest

    @pytest.mark.asyncio
    async def test_triggers_again_when_hash_changes(self, monkeypatch, tmp_path):
        f = tmp_path / "factory.xlsx"
        f.write_bytes(b"v1")
        monkeypatch.setenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, str(f))

        engine = _FakeIngestEngine()
        await watcher_mod.watcher_tick(engine=engine)
        assert len(engine.calls) == 1

        f.write_bytes(b"v2 different content")
        await watcher_mod.watcher_tick(engine=engine)
        assert len(engine.calls) == 2

    @pytest.mark.asyncio
    async def test_respects_auto_activate_env(self, monkeypatch, tmp_path):
        f = tmp_path / "factory.xlsx"
        f.write_bytes(b"bytes")
        monkeypatch.setenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, str(f))
        monkeypatch.setenv(watcher_mod.DEFAULT_AUTO_ACTIVATE_ENV, "true")

        engine = _FakeIngestEngine()
        await watcher_mod.watcher_tick(engine=engine)
        assert engine.calls[0]["auto_activate"] is True


class TestRegistration:
    def test_no_op_when_env_unset(self, monkeypatch):
        monkeypatch.delenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, raising=False)

        added = []
        fake_scheduler = SimpleNamespace(add_job=lambda *a, **kw: added.append(kw.get("id")))
        watcher_mod.register_with_scheduler(fake_scheduler)
        assert added == []

    def test_registers_job_when_file_exists(self, monkeypatch, tmp_path):
        f = tmp_path / "factory.xlsx"
        f.write_bytes(b"x")
        monkeypatch.setenv(watcher_mod.DEFAULT_WATCH_PATH_ENV, str(f))

        added_ids = []
        fake_scheduler = SimpleNamespace(
            add_job=lambda fn, trigger=None, **kw: added_ids.append(kw["id"])
        )
        watcher_mod.register_with_scheduler(fake_scheduler, interval_minutes=15)
        assert added_ids == ["factory_data_watcher"]
