"""Sprint Q.13.B (B4) — SecretManager rotation contract tests.

The B4 promise is that an operator can rotate the JWT signing key
without restarting the process AND without invalidating in-flight
tokens. These tests pin the contract:

  * `current()` returns the active key
  * `previous()` returns the rotating-out key during overlap
  * `candidates()` returns both, in current-first order
  * Env-backed backend re-reads on every call (no stale cache)
  * File-backed backend re-reads when the file mtime advances
  * Static backend (tests/dev) holds whatever was passed in
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from src.shared.secret_manager import (
    EnvSecretBackend,
    FileSecretBackend,
    SecretManager,
    StaticSecretBackend,
    get_secret_manager,
    set_secret_manager,
)


# ─── StaticSecretBackend ─────────────────────────────────────────────


def test_static_backend_returns_what_it_was_given():
    b = StaticSecretBackend(current="key-A", previous="key-B")
    assert b.current() == "key-A"
    assert b.previous() == "key-B"


def test_static_backend_previous_optional():
    b = StaticSecretBackend(current="key-A")
    assert b.previous() is None


# ─── EnvSecretBackend ────────────────────────────────────────────────


def test_env_backend_reads_current_from_env(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_KEY", "env-current")
    monkeypatch.delenv("TEST_SECRET_KEY_PREVIOUS", raising=False)
    b = EnvSecretBackend(env_var="TEST_SECRET_KEY", previous_var="TEST_SECRET_KEY_PREVIOUS")
    assert b.current() == "env-current"
    assert b.previous() is None


def test_env_backend_reads_previous_when_set(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_KEY", "new")
    monkeypatch.setenv("TEST_SECRET_KEY_PREVIOUS", "old")
    b = EnvSecretBackend(env_var="TEST_SECRET_KEY", previous_var="TEST_SECRET_KEY_PREVIOUS")
    assert b.current() == "new"
    assert b.previous() == "old"


def test_env_backend_falls_back_when_env_missing(monkeypatch):
    monkeypatch.delenv("TEST_NO_SUCH_KEY", raising=False)
    b = EnvSecretBackend(env_var="TEST_NO_SUCH_KEY", fallback="fallback-key")
    assert b.current() == "fallback-key"


def test_env_backend_raises_when_no_env_and_no_fallback(monkeypatch):
    monkeypatch.delenv("TEST_NO_SUCH_KEY", raising=False)
    b = EnvSecretBackend(env_var="TEST_NO_SUCH_KEY", fallback=None)
    with pytest.raises(RuntimeError, match="not set"):
        b.current()


def test_env_backend_re_reads_on_each_call(monkeypatch):
    """Operators rotate by setenv + SIGHUP. The backend MUST NOT
    cache or the rotation never takes effect."""
    monkeypatch.setenv("TEST_SECRET_KEY", "rev1")
    b = EnvSecretBackend(env_var="TEST_SECRET_KEY")
    assert b.current() == "rev1"
    monkeypatch.setenv("TEST_SECRET_KEY", "rev2")
    assert b.current() == "rev2"


def test_env_backend_empty_previous_treated_as_none(monkeypatch):
    """Setting PREVIOUS="" is the documented way to clear the overlap
    window. Empty string MUST normalise to None."""
    monkeypatch.setenv("TEST_SECRET_KEY", "x")
    monkeypatch.setenv("TEST_SECRET_KEY_PREVIOUS", "")
    b = EnvSecretBackend(env_var="TEST_SECRET_KEY", previous_var="TEST_SECRET_KEY_PREVIOUS")
    assert b.previous() is None


# ─── FileSecretBackend ───────────────────────────────────────────────


def test_file_backend_reads_secret_from_file(tmp_path: Path):
    secret_path = tmp_path / "current.key"
    secret_path.write_text("file-key-1")
    b = FileSecretBackend(path=secret_path)
    assert b.current() == "file-key-1"


def test_file_backend_caches_until_mtime_changes(tmp_path: Path):
    secret_path = tmp_path / "current.key"
    secret_path.write_text("rev-1")
    b = FileSecretBackend(path=secret_path)
    assert b.current() == "rev-1"

    # Sleep enough to clear filesystem mtime resolution (1s on FAT,
    # microseconds elsewhere — 1.1s is safe everywhere).
    time.sleep(1.1)
    secret_path.write_text("rev-2")
    # Bump mtime explicitly so the test isn't flaky on platforms
    # with second-resolution timestamps.
    os.utime(secret_path, None)
    assert b.current() == "rev-2"


def test_file_backend_previous_optional(tmp_path: Path):
    cur = tmp_path / "current.key"
    cur.write_text("c")
    b = FileSecretBackend(path=cur)
    assert b.previous() is None


def test_file_backend_previous_when_path_supplied(tmp_path: Path):
    cur = tmp_path / "current.key"
    prev = tmp_path / "previous.key"
    cur.write_text("c")
    prev.write_text("p")
    b = FileSecretBackend(path=cur, previous_path=prev)
    assert b.previous() == "p"


# ─── SecretManager façade ────────────────────────────────────────────


def test_manager_candidates_current_first():
    backend = StaticSecretBackend(current="new", previous="old")
    mgr = SecretManager(backend)
    assert mgr.candidates() == ["new", "old"]


def test_manager_candidates_single_when_no_previous():
    backend = StaticSecretBackend(current="only")
    mgr = SecretManager(backend)
    assert mgr.candidates() == ["only"]


def test_manager_candidates_dedup_when_previous_equals_current():
    """Edge case: operator forgot to remove PREVIOUS after rotation
    completed. Manager should still emit one candidate, not duplicate."""
    backend = StaticSecretBackend(current="same", previous="same")
    mgr = SecretManager(backend)
    assert mgr.candidates() == ["same"]


# ─── Module-level singleton ──────────────────────────────────────────


def test_get_secret_manager_lazy_singleton(monkeypatch):
    set_secret_manager(None)
    monkeypatch.setenv("PRODPLAN_SECRET_KEY", "lazy-init-key")
    mgr = get_secret_manager()
    assert mgr.current() == "lazy-init-key"
    # Second call returns the same instance.
    assert get_secret_manager() is mgr
    set_secret_manager(None)  # cleanup


def test_set_secret_manager_overrides():
    fake = SecretManager(StaticSecretBackend(current="injected"))
    set_secret_manager(fake)
    assert get_secret_manager() is fake
    assert get_secret_manager().current() == "injected"
    set_secret_manager(None)
