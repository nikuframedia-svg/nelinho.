"""
ProdPlan ONE — Secret Manager (Sprint Q.13.B / B4)
====================================================

Single source of truth for runtime secrets (JWT signing key, future
DB credentials, ERP service account password, etc.). Decouples the
process-startup ``settings.secret_key`` (loaded once via Pydantic
Settings) from the *current* secret used by request handlers.

Why this matters
----------------

Before this module, ``settings.secret_key`` was read once at boot.
Rotating the JWT signing key required a full process restart, which:

  * Invalidates every active session simultaneously (poor UX)
  * Forces a maintenance window for what should be a routine op
  * Has no graceful "old + new" overlap window so an in-flight
    request can be rejected mid-rotation

The SecretManager interface lets the operator rotate via a SIGHUP
or a config-store flip, with a configurable overlap window where
both the old and the new key are accepted (so already-issued JWTs
keep validating until they expire).

Three backends ship out of the box
-----------------------------------

* ``EnvSecretBackend`` — reads from ``PRODPLAN_SECRET_KEY`` /
  ``PRODPLAN_SECRET_KEY_PREVIOUS`` env vars. Default. Suitable for
  systemd ``EnvironmentFile=`` rotation.
* ``FileSecretBackend`` — reads from a 0600-mode file path; rereads
  on filesystem mtime change. Useful with HashiCorp Vault Agent
  rendering the secret to disk.
* ``StaticSecretBackend`` — wraps a fixed string. The fallback path
  during dev / tests so behaviour is deterministic.

A real Vault / AWS Secrets Manager / GCP Secret Manager backend can
be plugged in by implementing the ``SecretBackend`` protocol — the
interface intentionally stays small (``current()`` + ``previous()``).

Why we ship rotation infra without a real Vault yet
----------------------------------------------------

The plan v4 §11.1 doesn't list secrets management explicitly but
§11.2 audit trail + §15 trust gates implicitly require it: an
operator must be able to rotate a leaked JWT key without bringing
the app down. Shipping the *interface* now means when Vault arrives
(month X) it slots in by adding one ``VaultBackend`` class, no
caller change. The 8h budget on B4 is for the interface + envvar
backend + tests; Vault adapter is Onda 2 (~6h).

Threading
---------

All backends are read-mostly. The default ``EnvSecretBackend``
caches the env value lazily; ``FileSecretBackend`` re-reads when the
mtime advances. No locks — race between two readers picking up old
vs new is acceptable because both keys validate during the overlap
window anyway.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ─── Backend protocol ────────────────────────────────────────────────


@runtime_checkable
class SecretBackend(Protocol):
    """Minimum surface a secret source must expose. Both methods must
    return the secret as a string (not bytes) so the JWT lib path is
    identical across backends."""

    def current(self) -> str:
        """The secret to USE for new signatures."""

    def previous(self) -> Optional[str]:
        """The secret VERIFIED on tokens issued just before rotation.
        Returning None means there is no rotation window in effect.
        """


# ─── EnvSecretBackend (default) ──────────────────────────────────────


class EnvSecretBackend:
    """Reads from environment variables on every call.

    Variables:
      * ``env_var``       — current (active) signing key
      * ``previous_var``  — optional, key being rotated out

    Behaviour:
      * No caching: env can be reloaded by systemd reload or manual
        SIGHUP without restarting the process.
      * Empty string from env is treated as None for ``previous`` so
        the overlap window is naturally cleared by setting the var
        to "".
    """

    def __init__(
        self,
        env_var: str = "PRODPLAN_SECRET_KEY",
        previous_var: str = "PRODPLAN_SECRET_KEY_PREVIOUS",
        fallback: Optional[str] = None,
    ) -> None:
        self.env_var = env_var
        self.previous_var = previous_var
        self.fallback = fallback

    def current(self) -> str:
        value = os.getenv(self.env_var) or self.fallback
        if value is None:
            raise RuntimeError(
                f"SecretManager: {self.env_var} not set and no fallback supplied"
            )
        return value

    def previous(self) -> Optional[str]:
        value = os.getenv(self.previous_var)
        return value if value else None


# ─── FileSecretBackend ───────────────────────────────────────────────


class FileSecretBackend:
    """Reads the secret from a file. Suitable for Vault Agent / SOPS
    rendering. Re-reads when the file's mtime advances since the last
    read; cheap because we only touch the inode in stat(2).
    """

    def __init__(
        self,
        path: Path,
        previous_path: Optional[Path] = None,
    ) -> None:
        self.path = Path(path)
        self.previous_path = Path(previous_path) if previous_path else None
        self._cache: Optional[str] = None
        self._cache_mtime: float = 0.0
        self._cache_prev: Optional[str] = None
        self._cache_prev_mtime: float = 0.0
        self._lock = threading.Lock()

    def current(self) -> str:
        with self._lock:
            mtime = self.path.stat().st_mtime
            if self._cache is None or mtime > self._cache_mtime:
                self._cache = self.path.read_text(encoding="utf-8").strip()
                self._cache_mtime = mtime
            return self._cache

    def previous(self) -> Optional[str]:
        if self.previous_path is None or not self.previous_path.exists():
            return None
        with self._lock:
            mtime = self.previous_path.stat().st_mtime
            if self._cache_prev is None or mtime > self._cache_prev_mtime:
                self._cache_prev = self.previous_path.read_text(
                    encoding="utf-8"
                ).strip()
                self._cache_prev_mtime = mtime
            return self._cache_prev or None


# ─── StaticSecretBackend (tests + dev fallback) ──────────────────────


class StaticSecretBackend:
    """Hardcoded. Used by tests + dev when no env / file is configured."""

    def __init__(
        self,
        current: str,
        previous: Optional[str] = None,
    ) -> None:
        self._current = current
        self._previous = previous

    def current(self) -> str:
        return self._current

    def previous(self) -> Optional[str]:
        return self._previous


# ─── SecretManager — public entry point ──────────────────────────────


class SecretManager:
    """Façade in front of a `SecretBackend`. Callers (auth dependency,
    JWT validator) ALWAYS call ``manager.current()`` for issuing and
    iterate over ``manager.candidates()`` for verification — that's
    the only contract.
    """

    def __init__(self, backend: SecretBackend) -> None:
        self.backend = backend

    def current(self) -> str:
        """The signing key to USE NOW."""
        return self.backend.current()

    def previous(self) -> Optional[str]:
        """The being-rotated-out key. None when no rotation."""
        return self.backend.previous()

    def candidates(self) -> list[str]:
        """All keys that should be ACCEPTED on validation. Order:
        current first (most likely match), previous second. The JWT
        validator iterates and returns the token on the first match."""
        out: list[str] = [self.current()]
        prev = self.previous()
        if prev and prev != out[0]:
            out.append(prev)
        return out


# ─── Module-level singleton ──────────────────────────────────────────


_default_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Return the process-wide SecretManager. Lazy-initialised on
    first call so tests can swap it via ``set_secret_manager`` before
    importing.

    The default backend is ``EnvSecretBackend`` with a fallback to
    ``settings.secret_key`` so existing code paths continue to work
    until the operator opts into rotation by setting
    ``PRODPLAN_SECRET_KEY`` env var.
    """
    global _default_manager
    if _default_manager is None:
        # Lazy import — avoids circular import with src/shared/config.py
        # which itself imports nothing from this module.
        from src.shared.config import settings
        backend = EnvSecretBackend(
            env_var="PRODPLAN_SECRET_KEY",
            previous_var="PRODPLAN_SECRET_KEY_PREVIOUS",
            fallback=settings.secret_key,
        )
        _default_manager = SecretManager(backend)
    return _default_manager


def set_secret_manager(manager: Optional[SecretManager]) -> None:
    """Override the process singleton. Tests pass a StaticSecretBackend
    so they don't depend on environment state. Pass None to reset to
    the lazy default on the next ``get_secret_manager()`` call."""
    global _default_manager
    _default_manager = manager


__all__ = [
    "EnvSecretBackend",
    "FileSecretBackend",
    "SecretBackend",
    "SecretManager",
    "StaticSecretBackend",
    "get_secret_manager",
    "set_secret_manager",
]
