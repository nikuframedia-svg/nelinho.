"""
ProdPlan ONE - Tenant Configuration Service (Sprint L.2)
=========================================================

Read/write façade over `TenantConfiguration`. Provides:

* **Typed access** (`get`, `get_typed`, `get_category`) with per-category in-process
  LRU cache (TTL 60s) keyed by `(tenant_id, category)`.
* **Audit-safe writes** (`set`, `bulk_set`) that close the previous row by setting
  `valid_to = now()` and create a new row with fresh `valid_from`, so history is
  preserved verbatim. A `ConfigUpdatedEvent` is published to Kafka via the outbox.
* **History & rollback** — `history()` returns all versions of a key, `rollback(id)`
  clones the payload of an old version back as the current row.
* **Snapshot import/export** for backup / fresh-tenant bootstrapping.

Consumers should prefer this service over direct ORM queries so that cache
invalidation and event emission stay consistent.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any, Optional, Sequence, Type, TypeVar
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.time import utc_now, utc_now_naive
from src.core.models.tenant_configuration import (
    ALLOWED_CATEGORIES,
    ALLOWED_DATA_TYPES,
    ALLOWED_SOURCES,
    SOURCE_DEFAULT,
    SOURCE_MANUAL,
    TenantConfiguration,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_CACHE_TTL_SECONDS = 60.0


class TenantConfigError(Exception):
    """Base class for tenant-config errors."""


class TenantConfigNotFoundError(TenantConfigError):
    """Requested key does not exist for the tenant."""


class TenantConfigValidationError(TenantConfigError):
    """Category/data_type outside the allowed vocabulary."""


# ---------------------------------------------------------------------------
# Cache (module-level, process-local)
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    values: dict[str, Any]
    expires_at: float


class _CategoryCache:
    """Thread-safe, per-(tenant, category) cache with monotonic TTL."""

    def __init__(self, ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._data: dict[tuple[UUID, str], _CacheEntry] = {}
        self._lock = Lock()

    def get(self, tenant_id: UUID, category: str) -> Optional[dict[str, Any]]:
        with self._lock:
            entry = self._data.get((tenant_id, category))
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                # Lazy eviction; avoids a background thread.
                self._data.pop((tenant_id, category), None)
                return None
            # Return a shallow copy so callers can't mutate the cache.
            return dict(entry.values)

    def put(self, tenant_id: UUID, category: str, values: dict[str, Any]) -> None:
        with self._lock:
            self._data[(tenant_id, category)] = _CacheEntry(
                values=dict(values),
                expires_at=time.monotonic() + self._ttl,
            )

    def invalidate(self, tenant_id: UUID, category: str) -> None:
        with self._lock:
            self._data.pop((tenant_id, category), None)

    def invalidate_tenant(self, tenant_id: UUID) -> None:
        with self._lock:
            keys = [k for k in self._data if k[0] == tenant_id]
            for k in keys:
                self._data.pop(k, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_CACHE = _CategoryCache()


def _reset_cache_for_tests() -> None:
    """Test-only hook. Do not call from production code."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

_MISSING = object()


class TenantConfigService:
    """Tenant-scoped read/write façade for `TenantConfiguration` rows."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─── read ──────────────────────────────────────────────────────────────

    async def get(
        self,
        category: str,
        key: str,
        default: Any = _MISSING,
    ) -> Any:
        """Return the unwrapped value for `(category, key)` or `default`.

        Raises `TenantConfigNotFoundError` if no default is supplied and the key
        is missing — callers that want silent fallback MUST pass `default=`.
        """
        values = await self.get_category(category)
        if key in values:
            return values[key]
        if default is _MISSING:
            raise TenantConfigNotFoundError(
                f"Config {category}.{key} not set for tenant {self.tenant_id}"
            )
        return default

    async def get_typed(
        self,
        category: str,
        key: str,
        type_: Type[T],
        default: Any = _MISSING,
    ) -> T:
        """Like `get`, but verifies the stored value `isinstance(value, type_)`."""
        value = await self.get(category, key, default=default)
        if not isinstance(value, type_):
            raise TenantConfigValidationError(
                f"Config {category}.{key} has type {type(value).__name__}, "
                f"expected {type_.__name__}"
            )
        return value

    async def get_category(self, category: str) -> dict[str, Any]:
        """Return `{key: unwrapped_value}` for all active keys in `category`."""
        _validate_category(category)

        cached = _CACHE.get(self.tenant_id, category)
        if cached is not None:
            return cached

        stmt = select(TenantConfiguration).where(
            and_(
                TenantConfiguration.tenant_id == self.tenant_id,
                TenantConfiguration.category == category,
                TenantConfiguration.valid_to.is_(None),
            )
        )
        rows: Sequence[TenantConfiguration] = (
            await self.session.execute(stmt)
        ).scalars().all()

        values = {row.key: row.raw_value for row in rows}
        _CACHE.put(self.tenant_id, category, values)
        return values

    async def history(
        self,
        category: str,
        key: str,
    ) -> list[TenantConfiguration]:
        """Return all versions of `(category, key)` ordered newest → oldest."""
        _validate_category(category)
        stmt = (
            select(TenantConfiguration)
            .where(
                and_(
                    TenantConfiguration.tenant_id == self.tenant_id,
                    TenantConfiguration.category == category,
                    TenantConfiguration.key == key,
                )
            )
            .order_by(TenantConfiguration.valid_from.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    # ─── write ─────────────────────────────────────────────────────────────

    async def set(
        self,
        category: str,
        key: str,
        value: Any,
        user_id: Optional[UUID],
        data_type: str,
        source: str = SOURCE_MANUAL,
    ) -> TenantConfiguration:
        """Insert a new active version for `(category, key)`.

        Any currently-active row for the same `(category, key)` has its
        `valid_to` closed to `now()` first, so the write is history-preserving.

        ``source`` records the provenance of the new value (Plan v4 §4.7):
        ``manual`` is the API default because every direct call from a UI
        is by definition operator-driven; the seeder passes ``default`` and
        the YAML policy ``set_config`` dispatcher passes ``learned_rule``.
        """
        _validate_category(category)
        _validate_data_type(data_type)
        _validate_source(source)

        now = utc_now_naive()
        current = await self._current_row(category, key)
        if current is not None:
            current.valid_to = now
            current.last_modified_by = user_id
            current.last_modified_at = now

        # id is generated here (not relying on the SQLAlchemy default) so that
        # callers can read `row.id` before the session is flushed by the UoW.
        new_row = TenantConfiguration(
            id=uuid4(),
            tenant_id=self.tenant_id,
            category=category,
            key=key,
            value=TenantConfiguration.wrap(value),
            data_type=data_type,
            valid_from=now,
            created_by=user_id,
            created_at=now,
            last_modified_by=user_id,
            last_modified_at=now,
            source=source,
        )
        self.session.add(new_row)
        await self.session.flush()

        _CACHE.invalidate(self.tenant_id, category)
        await self._emit_config_updated(category, [key], data_type)
        return new_row

    async def bulk_set(
        self,
        entries: list[dict],
        user_id: Optional[UUID],
    ) -> list[TenantConfiguration]:
        """Apply many `set` operations. Each entry must carry category/key/value/data_type.

        Optional ``source`` per entry; defaults to ``manual`` so callers
        without provenance context get the conservative answer (a UI
        bulk-edit is operator-driven). The seeder passes ``default``
        explicitly via the same path.
        """
        written: list[TenantConfiguration] = []
        by_category: dict[str, list[str]] = {}
        for entry in entries:
            row = await self.set(
                category=entry["category"],
                key=entry["key"],
                value=entry["value"],
                user_id=user_id,
                data_type=entry["data_type"],
                source=entry.get("source", SOURCE_MANUAL),
            )
            written.append(row)
            by_category.setdefault(entry["category"], []).append(entry["key"])
        return written

    async def rollback(
        self,
        config_id: UUID,
        user_id: Optional[UUID],
    ) -> TenantConfiguration:
        """Restore a historical version as the new current value.

        A rollback is a deliberate manual operator action — even if the
        original row was ``learned_rule``, the act of restoring it is
        manual — so the new row records ``source='manual'``.
        """
        stmt = select(TenantConfiguration).where(
            and_(
                TenantConfiguration.id == config_id,
                TenantConfiguration.tenant_id == self.tenant_id,
            )
        )
        target = (await self.session.execute(stmt)).scalar_one_or_none()
        if target is None:
            raise TenantConfigNotFoundError(
                f"Config id={config_id} not found for tenant {self.tenant_id}"
            )

        return await self.set(
            category=target.category,
            key=target.key,
            value=target.raw_value,
            user_id=user_id,
            data_type=target.data_type,
            source=SOURCE_MANUAL,
        )

    # ─── snapshot ──────────────────────────────────────────────────────────

    async def export_snapshot(self) -> dict[str, dict[str, dict]]:
        """Return `{category: {key: {value, data_type}}}` for all active keys.

        Intended for backup / fresh-tenant bootstrapping. Not a historical dump —
        closed versions are excluded.
        """
        stmt = select(TenantConfiguration).where(
            and_(
                TenantConfiguration.tenant_id == self.tenant_id,
                TenantConfiguration.valid_to.is_(None),
            )
        )
        rows: Sequence[TenantConfiguration] = (
            await self.session.execute(stmt)
        ).scalars().all()
        snapshot: dict[str, dict[str, dict]] = {}
        for row in rows:
            snapshot.setdefault(row.category, {})[row.key] = {
                "value": row.raw_value,
                "data_type": row.data_type,
            }
        return snapshot

    async def import_snapshot(
        self,
        snapshot: dict[str, dict[str, dict]],
        user_id: Optional[UUID],
    ) -> int:
        """Apply a snapshot. Returns the number of rows written."""
        count = 0
        for category, keys in snapshot.items():
            for key, entry in keys.items():
                await self.set(
                    category=category,
                    key=key,
                    value=entry["value"],
                    user_id=user_id,
                    data_type=entry["data_type"],
                )
                count += 1
        return count

    # ─── internals ─────────────────────────────────────────────────────────

    async def _current_row(self, category: str, key: str) -> Optional[TenantConfiguration]:
        stmt = select(TenantConfiguration).where(
            and_(
                TenantConfiguration.tenant_id == self.tenant_id,
                TenantConfiguration.category == category,
                TenantConfiguration.key == key,
                TenantConfiguration.valid_to.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _emit_config_updated(
        self,
        category: str,
        keys: list[str],
        data_type: str,
    ) -> None:
        """Publish a `CONFIG_UPDATED` event. Failure is logged, not raised —
        missing the notification is less bad than dropping the successful write."""
        try:
            # Lazy imports so unit tests that don't hit Kafka don't pay the cost.
            from src.shared.events import ConfigUpdatedEvent
            from src.shared.kafka_client import Topics, publish_event

            await publish_event(
                Topics.CONFIG_UPDATED,
                ConfigUpdatedEvent(
                    tenant_id=self.tenant_id,
                    payload={
                        "config_type": f"tenant_configuration.{category}",
                        "affected_entities": keys,
                        "data_type": data_type,
                        "effective_from": utc_now().isoformat(),
                    },
                ),
            )
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning(
                "Failed to publish CONFIG_UPDATED for tenant=%s category=%s: %s",
                self.tenant_id, category, exc,
            )


def _validate_category(category: str) -> None:
    if category not in ALLOWED_CATEGORIES:
        raise TenantConfigValidationError(
            f"Unknown category '{category}'. Allowed: {sorted(ALLOWED_CATEGORIES)}"
        )


def _validate_data_type(data_type: str) -> None:
    if data_type not in ALLOWED_DATA_TYPES:
        raise TenantConfigValidationError(
            f"Unknown data_type '{data_type}'. Allowed: {sorted(ALLOWED_DATA_TYPES)}"
        )


def _validate_source(source: str) -> None:
    if source not in ALLOWED_SOURCES:
        raise TenantConfigValidationError(
            f"Unknown source '{source}'. Allowed: {sorted(ALLOWED_SOURCES)}"
        )
