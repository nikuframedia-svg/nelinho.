"""Q.17.F.9 — in-memory registry of active write-pauses.

The ``pause_writes`` action lets a YAML rule fail-closed a route prefix
for a bounded window — an emergency brake. This module holds the active
pauses; :class:`PauseWritesMiddleware` reads them on every write request.

The store is process-local and intentionally **not** durable: the NELO
deploy is single-worker, and a 15-minute emergency brake that evaporates
on restart is acceptable (a restart is itself a state reset). A durable
table would be a Q.18.D follow-up.

Expiry is lazy — entries are dropped when read past their ``expires_at``.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PauseInfo:
    """One active write-pause."""

    tenant_id: UUID
    route_prefix: str
    expires_at: datetime
    reason_pt: str


# (tenant_id, route_prefix) -> PauseInfo. Guarded by a lock because the
# dispatcher (rule fire) and the middleware (request thread) touch it
# concurrently.
_PAUSES: dict[tuple[UUID, str], PauseInfo] = {}
_LOCK = threading.Lock()


def register_pause(
    tenant_id: UUID,
    route_prefix: str,
    duration_minutes: int,
    reason_pt: str,
) -> datetime:
    """Register (or extend) a write-pause for ``route_prefix``.

    Returns the ``expires_at`` timestamp. Re-registering an already
    paused prefix overwrites it (idempotent — the latest rule wins).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    info = PauseInfo(
        tenant_id=tenant_id,
        route_prefix=route_prefix,
        expires_at=expires_at,
        reason_pt=reason_pt,
    )
    with _LOCK:
        _PAUSES[(tenant_id, route_prefix)] = info
    _log.warning(
        "pause_writes registered tenant=%s prefix=%s expires=%s reason=%r",
        tenant_id, route_prefix, expires_at.isoformat(), reason_pt,
    )
    return expires_at


def is_paused(tenant_id: UUID, path: str) -> PauseInfo | None:
    """Return the active pause whose ``route_prefix`` is a prefix of
    ``path`` for this tenant, or ``None``.

    Expired entries are discarded on read. When several pauses match,
    the longest (most specific) prefix wins.
    """
    now = datetime.now(timezone.utc)
    match: PauseInfo | None = None
    with _LOCK:
        for key, info in list(_PAUSES.items()):
            if info.expires_at <= now:
                del _PAUSES[key]
                continue
            if info.tenant_id != tenant_id:
                continue
            if not path.startswith(info.route_prefix):
                continue
            if match is None or len(info.route_prefix) > len(match.route_prefix):
                match = info
    return match


def active_pauses(tenant_id: UUID) -> list[PauseInfo]:
    """All non-expired pauses for a tenant — for observability/tests."""
    now = datetime.now(timezone.utc)
    with _LOCK:
        for key, info in list(_PAUSES.items()):
            if info.expires_at <= now:
                del _PAUSES[key]
        return [i for i in _PAUSES.values() if i.tenant_id == tenant_id]


def reset_for_tests() -> None:
    """Drop every registered pause — for unit tests only."""
    with _LOCK:
        _PAUSES.clear()
