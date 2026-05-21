"""Q.61.35 — `with_advisory_lock` decorator (Postgres advisory).

Pina:
  * Decorator devolve None se acquire falha (outro processo tem lock).
  * Decorator executa fn se acquire sucede; release em finally.
  * Fora-de-Postgres (qualquer excepcao no acquire): graceful fallback
    executa sem lock + warning.
  * Lock keys sao deterministicos (mesmo nome -> mesma key).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.scheduling import scheduler_lock as sl


# ─── lock key derivation ─────────────────────────────────────────────────


def test_lock_key_is_deterministic():
    """Mesmo nome -> mesma key (essencial para multi-process consenso)."""
    assert sl._lock_key("dpo_finetune") == sl._lock_key("dpo_finetune")


def test_lock_key_different_for_different_names():
    """Nomes diferentes -> keys diferentes (sem colisao trivial)."""
    assert sl._lock_key("dpo_finetune") != sl._lock_key("causal_discovery")


def test_lock_key_fits_signed_int64():
    """Postgres `pg_try_advisory_lock` espera bigint signed."""
    key = sl._lock_key("any_name")
    assert -(2 ** 63) <= key < 2 ** 63


# ─── decorator behaviour ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_acquired_lock_runs_fn(monkeypatch):
    """Quando _try_acquire devolve True, fn corre e devolve resultado."""
    monkeypatch.setattr(sl, "_try_acquire", AsyncMock(return_value=True))
    monkeypatch.setattr(sl, "_release", AsyncMock())

    # Patch engine.connect() para nao precisar de Postgres real.
    class _FakeConn:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(sl, "engine", _FakeEngine())

    @sl.with_advisory_lock("test_job_a")
    async def my_job(x):
        return x * 2

    result = await my_job(21)
    assert result == 42


@pytest.mark.asyncio
async def test_lock_held_returns_none(monkeypatch, caplog):
    """Quando outro processo tem o lock, fn NAO corre + return None."""
    monkeypatch.setattr(sl, "_try_acquire", AsyncMock(return_value=False))
    monkeypatch.setattr(sl, "_release", AsyncMock())

    class _FakeConn:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(sl, "engine", _FakeEngine())

    called = False

    @sl.with_advisory_lock("test_job_b")
    async def my_job():
        nonlocal called
        called = True
        return "ran"

    result = await my_job()
    assert result is None
    assert called is False


@pytest.mark.asyncio
async def test_lock_released_after_fn_raises(monkeypatch):
    """Mesmo se fn() levanta, _release e chamado no finally."""
    monkeypatch.setattr(sl, "_try_acquire", AsyncMock(return_value=True))
    release_spy = AsyncMock()
    monkeypatch.setattr(sl, "_release", release_spy)

    class _FakeConn:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    monkeypatch.setattr(sl, "engine", _FakeEngine())

    @sl.with_advisory_lock("test_job_c")
    async def my_job():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await my_job()

    assert release_spy.await_count == 1


@pytest.mark.asyncio
async def test_non_postgres_fallback_runs_without_lock(monkeypatch):
    """Quando acquire crasha (driver nao suporta advisory lock),
    _try_acquire devolve True (fallback). Decorator executa na mesma."""
    async def _faulty_scalar(self, *args, **kwargs):
        raise RuntimeError("not postgres")

    class _FakeConn:
        scalar = _faulty_scalar
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    # Nao mockamos _try_acquire — queremos testar o fallback real
    monkeypatch.setattr(sl, "engine", _FakeEngine())

    @sl.with_advisory_lock("test_job_d")
    async def my_job():
        return "ran-without-lock"

    result = await my_job()
    assert result == "ran-without-lock"
