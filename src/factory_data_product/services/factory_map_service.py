"""
ProdPlan ONE - Factory Map Service (Sprint N)
==============================================

Aggregator behind the `/v1/factory-map/*` endpoints. Composes data from
multiple existing sources — no new ORM tables — into the structures the
Factory Map UI (Sprint Z) will consume:

1. **Snapshot** (`snapshot()` — N.1)
   - WIP / bottlenecks / skills_risk from `SemanticQueriesInMemory`
   - Mold status from `CuratedMold`
   - Effective Trust Index + gates (Sprint AA)
   - Strategic KPIs (see `kpis()`)

2. **Per-boat view** (`boat_view()` — N.2)
   - ProductionOrder + its CuratedOrderPhase trajectory
   - Risk flags: LATE_VS_TRANSPORT, QUALITY_RISK_HIGH, MOLD_MAINT_DUE

3. **Projection** (`projection()` — N.3)
   - **Does NOT call CPO** (too heavy, and Sprint P's greedy pipeline
     hasn't landed). Uses historical average durations per (model, phase)
     from curated data to extrapolate a 7-day heatmap. Honest and cheap.

4. **Shortage risks** (`shortage_risks()` — N.4)
   - ROP-based check: `qty_closing` vs `ROPConfig.rop`; no BOM explosion
     (that's Sprint O.2). Surfaces the most-at-risk SKUs.

5. **Line load** (`line_load()` — N.5)
   - Aggregates `ProductionSchedule.scheduled_duration_hours` grouped by
     (phase, date).

6. **Strategic KPIs** (`kpis()` — N.6)
   - WIP, throughput_units_today, defect_rate, OTD. Throughput €/dia
     returns `"unavailable"` until Sprint Q.0 ships ProductPricing.

Design constraints
------------------
* **Read-only** — does NOT mutate any table.
* **Best-effort** — any source can be missing (no curated data ingested,
  no CPO run yet, no mold table populated); each method degrades with a
  clear `availability` block instead of raising.
* **Cache-friendly** — `snapshot()` is the expensive read and lives
  behind a short Redis TTL keyed by tenant + active ingestion.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass
class Availability:
    """Soft presence flag for each data source the snapshot depends on."""

    semantic: bool = False
    orders: bool = False
    schedule: bool = False
    molds: bool = False
    inventory: bool = False
    pricing: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "semantic": self.semantic,
            "orders": self.orders,
            "schedule": self.schedule,
            "molds": self.molds,
            "inventory": self.inventory,
            "pricing": self.pricing,
        }


@dataclass
class RiskFlag:
    code: str
    severity: str  # "LOW" | "MED" | "HIGH"
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class FactoryMapService:
    """Aggregator façade. Instantiate per request; methods are independent."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        semantic_service: Any = None,
        session_factory: Any = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        # Dependency-injected so tests can pass a stub; real callers use the
        # in-memory semantic service via `get_semantic_service()`.
        self._semantic = semantic_service
        # Q.54.C — when provided, `snapshot()` fans its independent DB reads
        # out concurrently, each on its OWN session (a single AsyncSession
        # is not safe for concurrent use). Tests pass a FakeSession and no
        # factory → the snapshot stays serial on the shared session, which
        # keeps the deterministic-queue test fixtures valid.
        self._session_factory = session_factory

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

    # ─── N.2 Per-boat view ────────────────────────────────────────────────

    async def boat_view(self, *, of_id: str) -> Optional[dict[str, Any]]:
        """Fetch the trajectory of a single order.

        Returns None when the order isn't in our tenant scope.
        """
        # Lazy imports so a non-schedule request never pulls plan deps.
        from src.plan.models.order import OrderStatus, ProductionOrder
        from src.factory_data_product.models.curated import CuratedOrderPhase

        legacy_id: Optional[int] = None
        try:
            legacy_id = int(of_id)
        except ValueError:
            pass

        conditions = [ProductionOrder.tenant_id == self.tenant_id]
        if legacy_id is not None:
            conditions.append(ProductionOrder.legacy_id == legacy_id)
        else:
            # Fall back to product_name exact match if of_id is non-numeric.
            conditions.append(ProductionOrder.product_name == of_id)

        order_row = (
            await self.session.execute(
                select(ProductionOrder).where(and_(*conditions)).limit(1)
            )
        ).scalar_one_or_none()
        if order_row is None:
            return None

        # Curated trajectory (may be empty if no curated ingest has happened).
        traj_rows = list(
            (
                await self.session.execute(
                    select(CuratedOrderPhase)
                    .where(CuratedOrderPhase.of_id == str(order_row.legacy_id))
                    .order_by(CuratedOrderPhase.ordem)
                )
            ).scalars().all()
        )

        trajectory = [
            {
                "phase_id": p.fase_id,
                "phase_name": p.fase_nome,
                "seq": p.ordem,
                "start": p.data_inicio.isoformat() if p.data_inicio else None,
                "end": p.data_fim.isoformat() if p.data_fim else None,
                "horas_reais": float(p.horas_reais) if p.horas_reais is not None else None,
                "horas_previstas": float(p.horas_previstas) if p.horas_previstas is not None else None,
                "estado": p.estado,
                "mold_id": p.molde_id,
            }
            for p in traj_rows
        ]

        # Risk flags
        flags: list[RiskFlag] = []
        if order_row.transport_date and order_row.completed_date is None:
            days_to_transport = (order_row.transport_date - date.today()).days
            if days_to_transport < 0:
                flags.append(RiskFlag(
                    code="LATE_VS_TRANSPORT",
                    severity="HIGH",
                    message=f"Transport date {days_to_transport*-1}d in the past and boat still in production",
                    evidence={"days_overdue": -days_to_transport},
                ))
            elif days_to_transport <= 3 and (
                not trajectory or any(t["end"] is None for t in trajectory)
            ):
                flags.append(RiskFlag(
                    code="AT_RISK_VS_TRANSPORT",
                    severity="MED",
                    message=f"Transport in {days_to_transport}d, open phases remain",
                    evidence={"days_to_transport": days_to_transport},
                ))

        return {
            "of_id": str(order_row.legacy_id),
            "product_name": order_row.product_name,
            "product_type": order_row.product_type,
            "current_phase": order_row.current_phase_name,
            "status": order_row.status if isinstance(order_row.status, str) else order_row.status.value,
            "created_date": order_row.created_date.isoformat() if order_row.created_date else None,
            "completed_date": order_row.completed_date.isoformat() if order_row.completed_date else None,
            "transport_date": order_row.transport_date.isoformat() if order_row.transport_date else None,
            "trajectory": trajectory,
            "risk_flags": [
                {"code": f.code, "severity": f.severity, "message": f.message, "evidence": f.evidence}
                for f in flags
            ],
        }

    # ─── N.3 Projection ───────────────────────────────────────────────────

    async def projection(self, *, days_ahead: int = 7) -> dict[str, Any]:
        """Lightweight forward heatmap.

        Takes every currently open ProductionOrder, walks its **remaining**
        phases using historical median durations per (model_id, phase_id),
        and buckets projected load into daily slots up to `days_ahead`.

        This intentionally does NOT call `CPOv4Engine.schedule()` — that
        path is multi-second and blocked on Sprint P. An honest "based on
        historical averages" view is cheaper and sufficient for the UI
        until the full CPO cascade lands.
        """
        from src.factory_data_product.models.curated import CuratedOrderPhase
        from src.plan.models.order import OrderStatus, ProductionOrder

        # Historical median duration per phase (1 round-trip).
        hist_stmt = (
            select(
                CuratedOrderPhase.fase_id,
                func.avg(CuratedOrderPhase.horas_reais).label("avg_h"),
                func.count(CuratedOrderPhase.id).label("sample"),
            )
            .where(CuratedOrderPhase.horas_reais.is_not(None))
            .group_by(CuratedOrderPhase.fase_id)
        )
        hist_rows = (await self.session.execute(hist_stmt)).all()
        median_h = {r[0]: float(r[1] or 0) for r in hist_rows if r[1] is not None}

        # Open orders
        open_orders = list(
            (
                await self.session.execute(
                    select(ProductionOrder).where(
                        and_(
                            ProductionOrder.tenant_id == self.tenant_id,
                            ProductionOrder.completed_date.is_(None),
                        )
                    )
                )
            ).scalars().all()
        )

        # Build heatmap: phase × day → projected load hours
        today = date.today()
        heatmap: dict[tuple[str, str], float] = {}
        for order in open_orders:
            current_phase = order.current_phase_name or "?"
            # For MVP we attribute the whole remaining work to the current
            # phase over the next N working days, spread linearly. Refining
            # with a full routing walk is Sprint P territory.
            duration_h = median_h.get(current_phase, 8.0)
            days_for_order = max(1, min(days_ahead, int(duration_h // 8) + 1))
            for d in range(days_for_order):
                day = today + timedelta(days=d)
                heatmap[(current_phase, day.isoformat())] = (
                    heatmap.get((current_phase, day.isoformat()), 0.0)
                    + duration_h / days_for_order
                )

        points = [
            {"phase_id": p, "date": d, "load_hours": round(h, 2)}
            for (p, d), h in sorted(heatmap.items(), key=lambda kv: (kv[0][1], kv[0][0]))
        ]
        return {
            "method": "historical_avg_durations",
            "days_ahead": days_ahead,
            "sample_size_per_phase": {
                r[0]: int(r[2]) for r in hist_rows if r[2] is not None
            },
            "open_orders_projected": len(open_orders),
            "points": points,
        }

    # ─── N.4 Shortage risks ───────────────────────────────────────────────

    async def shortage_risks(self, *, horizon_days: int = 14) -> dict[str, Any]:
        """Minimal ROP-based shortage detector.

        Compares each `ROPConfig.rop` against the most recent
        `InventoryLedgerEntry.qty_closing`. Orders are joined in lazily —
        a full BOM explosion ships in Sprint O.2.

        Output is always non-null; `items=[]` when no inventory is present.
        """
        from src.supply.models import InventoryLedgerEntry, ROPConfig

        # Latest closing qty per SKU (correlated subquery via max(date))
        latest_subq = (
            select(
                InventoryLedgerEntry.sku_id,
                func.max(InventoryLedgerEntry.date).label("latest"),
            )
            .where(InventoryLedgerEntry.tenant_id == self.tenant_id)
            .group_by(InventoryLedgerEntry.sku_id)
            .subquery()
        )
        stmt = (
            select(
                ROPConfig.sku_id,
                ROPConfig.rop,
                ROPConfig.avg_daily_demand,
                ROPConfig.lead_time_days,
                InventoryLedgerEntry.qty_closing,
            )
            .join(
                latest_subq,
                ROPConfig.sku_id == latest_subq.c.sku_id,
                isouter=True,
            )
            .join(
                InventoryLedgerEntry,
                and_(
                    InventoryLedgerEntry.sku_id == latest_subq.c.sku_id,
                    InventoryLedgerEntry.date == latest_subq.c.latest,
                ),
                isouter=True,
            )
            .where(ROPConfig.tenant_id == self.tenant_id)
        )
        rows = (await self.session.execute(stmt)).all()

        items: list[dict[str, Any]] = []
        for sku_id, rop, demand, lead_time, closing in rows:
            on_hand = float(closing or 0)
            demand_f = float(demand or 0)
            days_to_stockout = (
                on_hand / demand_f if demand_f > 0 else None
            )
            severity = "LOW"
            if rop is not None and on_hand <= float(rop):
                severity = "HIGH" if on_hand < float(rop) * 0.5 else "MED"
            items.append({
                "sku_id": str(sku_id),
                "on_hand": on_hand,
                "rop": float(rop) if rop is not None else None,
                "avg_daily_demand": demand_f,
                "lead_time_days": int(lead_time or 0),
                "days_to_stockout": (
                    round(days_to_stockout, 2) if days_to_stockout is not None else None
                ),
                "severity": severity,
            })

        # Sort most-critical first so the UI banner picks the top of the list.
        severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
        items.sort(key=lambda x: (severity_order.get(x["severity"], 3), x["on_hand"]))

        return {
            "horizon_days": horizon_days,
            "items": items,
            "counts": {
                "high": sum(1 for i in items if i["severity"] == "HIGH"),
                "med": sum(1 for i in items if i["severity"] == "MED"),
                "low": sum(1 for i in items if i["severity"] == "LOW"),
            },
        }

    # ─── N.5 Line load ────────────────────────────────────────────────────

    async def line_load(self, *, horizon_days: int = 14) -> dict[str, Any]:
        """Aggregate `ProductionSchedule` load by (operation_id, date).

        Phase-level breakdown requires joining on `Operation.phase_id`; for
        the MVP we group by `operation_id` which the frontend can resolve.
        """
        from src.plan.models.schedule import ProductionSchedule

        today = date.today()
        until = today + timedelta(days=horizon_days)

        stmt = (
            select(
                ProductionSchedule.operation_id,
                ProductionSchedule.scheduled_start_date,
                func.sum(ProductionSchedule.scheduled_duration_hours).label("load_h"),
            )
            .where(
                and_(
                    ProductionSchedule.tenant_id == self.tenant_id,
                    ProductionSchedule.scheduled_start_date >= today,
                    ProductionSchedule.scheduled_start_date <= until,
                )
            )
            .group_by(ProductionSchedule.operation_id, ProductionSchedule.scheduled_start_date)
        )
        rows = (await self.session.execute(stmt)).all()

        points = [
            {
                "operation_id": str(op_id) if op_id else None,
                "date": day.isoformat() if day else None,
                "load_hours": float(h or 0),
            }
            for op_id, day, h in rows
        ]
        return {
            "horizon_days": horizon_days,
            "has_data": len(points) > 0,
            "points": points,
        }

    # ─── N.6 Strategic KPIs ───────────────────────────────────────────────

    async def kpis(self) -> dict[str, Any]:
        """Strategic KPIs. Throughput €/dia requires Sprint Q.0 (ProductPricing)
        which hasn't shipped; returns `"unavailable"` instead of guessing.

        Q.54.E — `defect_rate` and `bottlenecks` no longer depend on the
        in-memory semantic service (which is often un-warmed → KPIs came
        back `null`/`[]`). They are now computed directly from the DB:
        rework events vs orders for the defect rate, phase backlog vs
        capacity for the bottlenecks. The semantic service is still
        consulted first when it has an answer.
        """
        orders_summary = await self._orders_summary()

        # Defect rate — prefer the semantic query, fall back to a direct
        # DB ratio of rework events over orders in a recent window.
        defect_rate = None
        quality = self._safe_semantic("get_quality")
        if quality and orders_summary["total"] > 0:
            total_errors = int(quality.get("total_errors") or 0)
            defect_rate = round(total_errors / orders_summary["total"], 3)
        if defect_rate is None:
            defect_rate = await self._defect_rate_from_db(orders_summary["total"])

        # Bottlenecks — DB fallback so `phases.bottlenecks` is never empty
        # when there is curated phase data. Carried under a private key the
        # snapshot reads and strips.
        bottlenecks_db = await self._bottlenecks_from_db()

        # Sprint Q.5 — real throughput €/dia from ThroughputService. Falls back
        # to `unavailable` when the service / table isn't wired on this tenant.
        throughput_eur_day = await self._throughput_eur_day()

        return {
            "wip": orders_summary["in_progress"],
            "orders_total": orders_summary["total"],
            "completed_today": await self._completed_count_today(),
            "defect_rate": defect_rate,
            "throughput_eur_day": throughput_eur_day,
            "_bottlenecks_db": bottlenecks_db,
        }

    async def _defect_rate_from_db(
        self, orders_total: int, *, window_days: int = 90,
    ) -> Optional[float]:
        """Rework events ÷ orders over a recent window.

        Mirrors how `QualityDashboardService` counts events: rows in
        `quality.rework_entry` with `detected_at` inside the window. The
        denominator is the total orders for the tenant — a rework rate
        per order, which is the number the Factory panel shows.
        """
        if orders_total <= 0:
            return None
        try:
            from src.quality.models.rework import ReworkEntry

            since = datetime.now(timezone.utc) - timedelta(days=window_days)
            stmt = select(func.count(ReworkEntry.id)).where(
                and_(
                    ReworkEntry.tenant_id == self.tenant_id,
                    ReworkEntry.detected_at >= since,
                )
            )
            rework_count = int(
                (await self.session.execute(stmt)).scalar_one_or_none() or 0
            )
            return round(rework_count / orders_total, 3)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "defect_rate DB fallback failed for tenant=%s: %r",
                self.tenant_id, exc,
            )
            return None

    async def _bottlenecks_from_db(
        self, *, top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Per-phase bottleneck score from curated backlog vs capacity.

        For each phase: open-phase backlog hours (`CuratedOrderPhase`
        rows whose `estado` is not a closed state) divided by the phase
        capacity (`PhaseCapacity.capacidade_horas`, falling back to an
        8h/day assumption). The score is the theoretical backlog in days;
        phases with the highest score are the gargalos. Returns `[]` when
        there's no curated phase data — an honest empty state.
        """
        try:
            from src.factory_data_product.models.curated import (
                CuratedOrderPhase,
                CuratedPhaseCapacity,
            )

            # Open-phase backlog hours per phase. `estado` for an open
            # phase is anything other than the closed markers; we count
            # rows whose data_fim is NULL (phase not finished) as the
            # backlog, which is robust to estado-string drift.
            backlog_stmt = (
                select(
                    CuratedOrderPhase.fase_id,
                    func.max(CuratedOrderPhase.fase_nome),
                    func.count(CuratedOrderPhase.id),
                    func.coalesce(
                        func.sum(CuratedOrderPhase.horas_finais), 0,
                    ),
                    func.coalesce(
                        func.sum(CuratedOrderPhase.horas_previstas), 0,
                    ),
                )
                .where(CuratedOrderPhase.data_fim.is_(None))
                .group_by(CuratedOrderPhase.fase_id)
            )
            backlog_rows = (await self.session.execute(backlog_stmt)).all()
            if not backlog_rows:
                return []

            # Capacity hours per phase (latest period available).
            cap_stmt = select(
                CuratedPhaseCapacity.fase_id,
                func.max(CuratedPhaseCapacity.capacidade_horas),
            ).group_by(CuratedPhaseCapacity.fase_id)
            cap_rows = (await self.session.execute(cap_stmt)).all()
            capacity_by_phase = {
                r[0]: float(r[1]) for r in cap_rows if r[1] is not None
            }

            items: list[dict[str, Any]] = []
            for fase_id, fase_nome, n_open, horas_finais, horas_prev in backlog_rows:
                backlog_h = float(horas_finais or 0) or float(horas_prev or 0)
                # When we have no hours at all, use an 8h/phase proxy so
                # the count of open phases still produces a signal.
                if backlog_h <= 0:
                    backlog_h = float(n_open or 0) * 8.0
                capacity_h = capacity_by_phase.get(fase_id) or 8.0
                score_days = round(backlog_h / capacity_h, 2) if capacity_h else None
                items.append({
                    "fase_id": str(fase_id) if fase_id else None,
                    "fase_nome": fase_nome,
                    "open_phases": int(n_open or 0),
                    "backlog_horas": round(backlog_h, 1),
                    "capacidade_horas": round(capacity_h, 1),
                    "score": score_days,
                    "is_critical": score_days is not None and score_days > 5,
                })

            items.sort(key=lambda x: (x["score"] or 0), reverse=True)
            return items[:top_n]
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "bottlenecks DB fallback failed for tenant=%s: %r",
                self.tenant_id, exc,
            )
            return []

    async def _throughput_eur_day(self) -> dict[str, Any]:
        try:
            from src.profit.services.throughput_service import (
                ThroughputService,
                on_target_band,
            )

            svc = ThroughputService(self.session, self.tenant_id)
            targets = await svc.load_targets()
            today = await svc.throughput_today()
            band = on_target_band(
                today, targets["min_eur_day"], targets["max_eur_day"],
            )
            return {
                "today": float(today),
                "target_min": float(targets["min_eur_day"]),
                "target_max": float(targets["max_eur_day"]),
                "on_target": band,
            }
        except Exception as exc:  # pragma: no cover — defensive
            # Onda 2.2 — full detail in server logs only; the API response
            # exposes just the exception type so we don't leak DB/role
            # internals to the Factory Map dashboard.
            logger.warning(
                "throughput_eur_day unavailable for tenant=%s: %r",
                self.tenant_id, exc,
            )
            return {
                "status": "unavailable",
                "reason": type(exc).__name__,
            }

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

    async def _trust_payload(self) -> dict[str, Any]:
        try:
            from src.dqa.trust_gates import effective_mode, load_gate_config
            from src.dqa.trust_signals import curated_signals_provider
            from src.dqa.trust_v2 import SCOPE_FACTORY, TrustIndexV2Calculator

            calc = TrustIndexV2Calculator(
                self.session, self.tenant_id,
                signals_provider=curated_signals_provider,
            )
            result = await calc.compute_for_scope(SCOPE_FACTORY)
            cfg = await load_gate_config(self.session, self.tenant_id)
            return {
                "composite": round(result.composite, 4),
                "components": {
                    k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in result.components.as_dict().items()
                },
                "effective_gates": effective_mode(result.composite, cfg),
            }
        except Exception as exc:  # pragma: no cover — defensive
            # Onda 2.2 — same rationale as _throughput_eur_day: keep raw
            # exception detail server-side; expose only the type.
            logger.warning(
                "trust payload failed for tenant=%s: %r", self.tenant_id, exc,
            )
            return {"composite": None, "error": type(exc).__name__}
