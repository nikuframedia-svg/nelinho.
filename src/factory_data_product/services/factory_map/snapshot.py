"""Snapshot composition + in-memory cache for `FactoryMapService`.

Holds:
* The module-level snapshot cache (TTL keyed by tenant) — its module-level
  identity matters: tests import `_snapshot_cache` directly and rewrite
  entries to force expiry.
* The `SnapshotMixin` that owns `snapshot()`, the concurrent
  `_gather_snapshot_parts()` fan-out, and the cheap per-source DB
  summaries the snapshot composes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.services.factory_map.risk_flags import (
    Availability,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory snapshot cache (Q.54.C)
# ---------------------------------------------------------------------------
# The snapshot is the heaviest read in the Factory Map (TrustIndexV2 +
# 5 DB aggregates). The Factory page blocks its first paint on this call,
# so a slow snapshot freezes the screen. We keep a short per-tenant
# in-process cache: the first request computes, the next ones (within the
# TTL) serve instantly. This is intentionally process-local — it sits
# *in front of* the Redis cache in the API layer and survives a Redis
# outage. Stale data for ~30-60s on a factory dashboard is acceptable.

_SNAPSHOT_CACHE_TTL_SECONDS = 45.0
_snapshot_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _snapshot_cache_get(tenant_id: UUID) -> Optional[dict[str, Any]]:
    entry = _snapshot_cache.get(str(tenant_id))
    if entry is None:
        return None
    expires_at, payload = entry
    if time.monotonic() >= expires_at:
        _snapshot_cache.pop(str(tenant_id), None)
        return None
    return payload


def _snapshot_cache_put(tenant_id: UUID, payload: dict[str, Any]) -> None:
    _snapshot_cache[str(tenant_id)] = (
        time.monotonic() + _SNAPSHOT_CACHE_TTL_SECONDS,
        payload,
    )


def _reset_snapshot_cache_for_tests() -> None:
    """Clear the in-memory snapshot cache — used by the test suite."""
    _snapshot_cache.clear()


class SnapshotMixin:
    """`FactoryMapService` snapshot + per-source DB summary methods."""

    # These attributes are set by `FactoryMapService.__init__`. Listed for
    # readers; mixin doesn't override `__init__`.
    session: AsyncSession
    tenant_id: UUID
    _semantic: Any
    _session_factory: Any

    # ─── N.1 Snapshot ─────────────────────────────────────────────────────

    async def snapshot(
        self,
        *,
        as_of: Optional[datetime] = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Global factory snapshot. All fields are best-effort.

        Nothing here runs the CPO engine; the heaviest operation is the
        Trust Index recompute + 5 DB aggregates.

        Q.54.C — performance. Two changes killed the ~2s freeze:
        1. A short per-tenant in-memory cache (`use_cache`): the second
           call inside the TTL window returns instantly.
        2. When a `session_factory` was injected, the five independent
           operations run concurrently via `asyncio.gather`, each on its
           own session. Without a factory (unit tests with a FakeSession)
           they stay serial on the shared session.
        """
        as_of = as_of or datetime.now(timezone.utc)

        if use_cache:
            cached = _snapshot_cache_get(self.tenant_id)
            if cached is not None:
                # Refresh only the timestamp so the UI shows "now" but the
                # heavy payload is reused.
                return {**cached, "timestamp": as_of.isoformat(), "cached": True}

        availability = Availability()

        # Semantic layer (cheap — in-memory, no DB session involved)
        wip = self._safe_semantic("get_wip")
        bottlenecks = self._safe_semantic("get_bottlenecks")
        skills_risk = self._safe_semantic("get_skills_risk")
        availability.semantic = wip is not None or bottlenecks is not None

        # The five operations below each hit the DB and are independent of
        # one another. When we have a session factory, fan them out.
        (
            orders_summary,
            molds_summary,
            trust_payload,
            load_preview,
            kpis_payload,
        ) = await self._gather_snapshot_parts()

        availability.orders = orders_summary["total"] > 0
        availability.molds = molds_summary["total"] > 0
        availability.schedule = load_preview["has_data"]

        # Bottlenecks: prefer the semantic payload, but fall back to a
        # direct DB computation so the panel is never empty when there's
        # data (Q.54.E).
        bottleneck_list = (bottlenecks or {}).get("bottlenecks", [])
        if not bottleneck_list:
            bottleneck_list = kpis_payload.get("_bottlenecks_db", [])

        payload = {
            "timestamp": as_of.isoformat(),
            "availability": availability.as_dict(),
            "trust": trust_payload,
            "boats": orders_summary,
            "phases": {
                "bottlenecks": bottleneck_list,
                "skills_risk": (skills_risk or {}).get("at_risk_phases", []),
                "wip": (wip or {}).get("open_phases_total"),
            },
            "molds": molds_summary,
            "line_load_preview": load_preview["points"][:14],  # first two weeks
            "kpis": {k: v for k, v in kpis_payload.items() if not k.startswith("_")},
        }

        if use_cache:
            _snapshot_cache_put(self.tenant_id, payload)
        return payload

    async def _gather_snapshot_parts(self) -> tuple[
        dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any],
        dict[str, Any],
    ]:
        """Compute the five independent snapshot parts.

        With a `session_factory` each part runs concurrently on its own
        `AsyncSession` (SQLAlchemy sessions are NOT concurrency-safe, so
        sharing one across `gather` tasks would corrupt state). Without a
        factory we run them serially on the shared session.
        """
        async def _serial() -> tuple[Any, Any, Any, Any, Any]:
            return (
                await self._orders_summary(),
                await self._molds_summary(),
                await self._trust_payload(),
                await self.line_load(horizon_days=7),
                await self.kpis(),
            )

        # Only fan out when we have a factory AND a real DB session. Unit
        # tests pass a FakeSession (not an AsyncSession) — those stay
        # serial on the shared session so the deterministic-queue
        # fixtures keep working.
        if self._session_factory is None or not isinstance(
            self.session, AsyncSession
        ):
            return await _serial()

        # Import locally to avoid a circular import (the façade pulls this
        # mixin at module import time).
        from src.factory_data_product.services.factory_map_service import (
            FactoryMapService,
        )

        async def _run(method_name: str, **kwargs: Any) -> Any:
            async with self._session_factory() as sub_session:
                sub = FactoryMapService(
                    sub_session, self.tenant_id,
                    semantic_service=self._semantic,
                )
                return await getattr(sub, method_name)(**kwargs)

        results = await asyncio.gather(
            _run("_orders_summary"),
            _run("_molds_summary"),
            _run("_trust_payload"),
            _run("line_load", horizon_days=7),
            _run("kpis"),
            return_exceptions=True,
        )

        # If every part blew up the session factory itself is unusable
        # (e.g. a test that injected a real factory but no real DB) — fall
        # back to the shared session rather than serving an all-empty
        # snapshot.
        if all(isinstance(r, Exception) for r in results):
            logger.warning(
                "snapshot parallel path failed wholesale; falling back to serial",
            )
            return await _serial()

        # Defensive: a single failing part degrades to its empty shape
        # rather than 500-ing the whole snapshot.
        defaults = (
            {"total": 0, "in_progress": 0, "completed": 0, "cancelled": 0},
            {"total": 0, "active": 0, "in_maintenance": 0},
            {"composite": None, "error": "unavailable"},
            {"horizon_days": 7, "has_data": False, "points": []},
            {},
        )
        out: list[Any] = []
        for idx, res in enumerate(results):
            if isinstance(res, Exception):
                logger.warning(
                    "snapshot part %d failed for tenant=%s: %r",
                    idx, self.tenant_id, res,
                )
                out.append(defaults[idx])
            else:
                out.append(res)
        return tuple(out)  # type: ignore[return-value]

    # ─── private helpers ──────────────────────────────────────────────────

    def _safe_semantic(self, method_name: str) -> Optional[dict[str, Any]]:
        """Call a method on the injected semantic service, returning None on
        any failure (including "service not injected")."""
        if self._semantic is None:
            return None
        method = getattr(self._semantic, method_name, None)
        if method is None:
            return None
        try:
            return method()
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("semantic %s failed: %s", method_name, exc)
            return None

    async def _orders_summary(self) -> dict[str, Any]:
        from src.plan.models.order import OrderStatus, ProductionOrder

        stmt = select(
            ProductionOrder.status, func.count(ProductionOrder.id),
        ).where(ProductionOrder.tenant_id == self.tenant_id).group_by(ProductionOrder.status)
        rows = (await self.session.execute(stmt)).all()

        by_status: dict[str, int] = {}
        total = 0
        for status_value, count in rows:
            status_str = status_value if isinstance(status_value, str) else status_value.value
            count_i = int(count)
            by_status[status_str] = count_i
            total += count_i
        return {
            "total": total,
            "in_progress": by_status.get(OrderStatus.IN_PROGRESS.value, 0),
            "completed": by_status.get(OrderStatus.COMPLETED.value, 0),
            "cancelled": by_status.get(OrderStatus.CANCELLED.value, 0),
        }

    async def _molds_summary(self) -> dict[str, Any]:
        from src.factory_data_product.models.curated import CuratedMold

        stmt = select(CuratedMold.em_manutencao, func.count(CuratedMold.id)).group_by(
            CuratedMold.em_manutencao,
        )
        rows = (await self.session.execute(stmt)).all()
        active = 0
        in_maint = 0
        for flag, count in rows:
            if flag:
                in_maint = int(count)
            else:
                active = int(count)
        return {"total": active + in_maint, "active": active, "in_maintenance": in_maint}

    async def _completed_count_today(self) -> int:
        from src.plan.models.order import ProductionOrder

        today = date.today()
        stmt = select(func.count(ProductionOrder.id)).where(
            and_(
                ProductionOrder.tenant_id == self.tenant_id,
                ProductionOrder.completed_date == today,
            )
        )
        return int((await self.session.execute(stmt)).scalar_one_or_none() or 0)
