"""
ProdPlan ONE - CEO Dashboard Metrics (Sprint Q.5 / §9)
======================================================

Aggregations over the curated layer for the 6 new CEO tiles described in
PP1 NELO Plan v4 §9:

* `otd()`                    — On-Time Delivery % over a 30-day window
* `backlog_by_client()`      — pending orders × value × deadline by client
* `expeditions_next_7d()`    — `TransportBatch` window for the next week
* `first_pass_yield()`       — % of orders with zero rework events

NOTE: NELO's curated layer doesn't carry an explicit `cliente_id` column
on `CuratedOrder` yet. We use `produto_nome` as the client proxy (Plan v4
acknowledges this — proper customer wiring lands later). The grouping
key is renamed to `client_name` in the API response so the UI doesn't
have to care.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.models.curated import CuratedOrder
from src.plan.models.transport import TransportBatch, TransportBatchAssignment
from src.quality.models.rework import ReworkEntry

logger = logging.getLogger(__name__)

DEFAULT_OTD_WINDOW_DAYS = 30
DEFAULT_FPY_WINDOW_DAYS = 30
DEFAULT_EXPEDITIONS_HORIZON_DAYS = 7
BACKLOG_DEFAULT_VALUE_EUR = 2350.0  # Plan v4 §2 — €35K/day ÷ 14.9 boats/day


# ─────────────────────────────────────────────────────────────────────────
# Result shapes
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class OTDResult:
    window_days: int
    on_time: int
    late: int
    total: int
    otd_pct: float
    by_client: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_days": self.window_days,
            "on_time": self.on_time,
            "late": self.late,
            "total": self.total,
            "otd_pct": round(self.otd_pct, 2),
            "by_client": self.by_client,
        }


@dataclass
class BacklogClientRow:
    client_name: str
    pending_orders: int
    pending_value_eur: float
    earliest_deadline: Optional[date]

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_name": self.client_name,
            "pending_orders": self.pending_orders,
            "pending_value_eur": round(self.pending_value_eur, 2),
            "earliest_deadline": (
                self.earliest_deadline.isoformat() if self.earliest_deadline else None
            ),
        }


@dataclass
class ExpeditionRow:
    batch_id: str
    code: str
    transport_date: date
    truck_capacity_units: int
    assigned_orders: int
    status: str
    destination: Optional[str]
    risk: str  # "ok" | "near_capacity" | "over_capacity"

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "code": self.code,
            "transport_date": self.transport_date.isoformat(),
            "truck_capacity_units": self.truck_capacity_units,
            "assigned_orders": self.assigned_orders,
            "status": self.status,
            "destination": self.destination,
            "risk": self.risk,
        }


@dataclass
class FPYResult:
    window_days: int
    orders_total: int
    orders_with_rework: int
    first_pass_yield_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_days": self.window_days,
            "orders_total": self.orders_total,
            "orders_with_rework": self.orders_with_rework,
            "first_pass_yield_pct": round(self.first_pass_yield_pct, 2),
        }


# ─────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────

class DashboardMetricsService:
    """Read-only aggregations for the CEO dashboard."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ── OTD ────────────────────────────────────────────────────────────
    async def otd(self, *, window_days: int = DEFAULT_OTD_WINDOW_DAYS) -> OTDResult:
        """On-Time Delivery % over the last `window_days`.

        On-time iff `data_conclusao <= data_entrega_prevista`. We require
        BOTH dates to be set; rows with either missing are excluded.
        """
        since = (datetime.now(timezone.utc).date()) - timedelta(days=window_days)

        stmt = select(
            CuratedOrder.produto_nome,
            CuratedOrder.data_entrega_prevista,
            CuratedOrder.data_conclusao,
        ).where(
            and_(
                CuratedOrder.data_conclusao.is_not(None),
                CuratedOrder.data_entrega_prevista.is_not(None),
                CuratedOrder.data_conclusao >= since,
            )
        )
        rows = (await self.session.execute(stmt)).all()

        total = on_time = late = 0
        per_client: dict[str, dict[str, int]] = {}
        for client_name_raw, promised, actual in rows:
            client_name = (client_name_raw or "—").strip() or "—"
            if promised is None or actual is None:
                continue
            total += 1
            bucket = per_client.setdefault(client_name, {"on_time": 0, "late": 0, "total": 0})
            bucket["total"] += 1
            if actual <= promised:
                on_time += 1
                bucket["on_time"] += 1
            else:
                late += 1
                bucket["late"] += 1

        otd_pct = (on_time / total * 100.0) if total > 0 else 0.0

        by_client = sorted(
            (
                {
                    "client_name": name,
                    "on_time": v["on_time"],
                    "late": v["late"],
                    "total": v["total"],
                    "otd_pct": round(
                        (v["on_time"] / v["total"] * 100.0) if v["total"] > 0 else 0.0,
                        2,
                    ),
                }
                for name, v in per_client.items()
            ),
            key=lambda r: -r["total"],
        )[:20]

        return OTDResult(
            window_days=window_days,
            on_time=on_time,
            late=late,
            total=total,
            otd_pct=otd_pct,
            by_client=by_client,
        )

    # ── Backlog by client ─────────────────────────────────────────────
    async def backlog_by_client(
        self,
        *,
        limit: int = 20,
        unit_value_eur: Optional[float] = None,
    ) -> list[BacklogClientRow]:
        """Pending orders × value × earliest deadline, grouped by client.

        "Pending" = `data_conclusao IS NULL` (not yet closed). Value is
        an estimate using `unit_value_eur` because the curated layer
        doesn't carry per-order pricing — Q.6 will swap to ProductPricing.

        Sprint Q.8 Fase 5 — `unit_value_eur` is now resolved from
        TenantConfig (`cost.target.unit_value_eur`) when not provided
        explicitly by the caller. The hardcoded module-level default is
        kept as a last-resort fallback when the config store itself is
        unreachable, so the route never fails closed on a config miss.
        """
        if unit_value_eur is None:
            unit_value_eur = await self._resolve_unit_value_eur()
        stmt = select(
            CuratedOrder.produto_nome,
            func.count(CuratedOrder.id).label("pending_orders"),
            func.min(CuratedOrder.data_entrega_prevista).label("earliest_deadline"),
        ).where(
            CuratedOrder.data_conclusao.is_(None),
        ).group_by(CuratedOrder.produto_nome)

        rows = (await self.session.execute(stmt)).all()
        out: list[BacklogClientRow] = []
        for client_name_raw, pending_orders, earliest in rows:
            out.append(
                BacklogClientRow(
                    client_name=(client_name_raw or "—").strip() or "—",
                    pending_orders=int(pending_orders or 0),
                    pending_value_eur=float(pending_orders or 0) * float(unit_value_eur),
                    earliest_deadline=earliest,
                )
            )
        out.sort(key=lambda r: -r.pending_value_eur)
        return out[:limit]

    # ── Expeditions next N days ───────────────────────────────────────
    async def expeditions_next_n_days(
        self,
        *,
        horizon_days: int = DEFAULT_EXPEDITIONS_HORIZON_DAYS,
    ) -> list[ExpeditionRow]:
        today = datetime.now(timezone.utc).date()
        until = today + timedelta(days=horizon_days)

        batches_stmt = (
            select(TransportBatch)
            .where(
                and_(
                    TransportBatch.tenant_id == self.tenant_id,
                    TransportBatch.transport_date >= today,
                    TransportBatch.transport_date <= until,
                )
            )
            .order_by(TransportBatch.transport_date, TransportBatch.priority)
        )
        batches = list((await self.session.execute(batches_stmt)).scalars().all())
        if not batches:
            return []

        # Counts per batch
        counts_stmt = (
            select(
                TransportBatchAssignment.batch_id,
                func.count(TransportBatchAssignment.id),
            )
            .where(TransportBatchAssignment.tenant_id == self.tenant_id)
            .group_by(TransportBatchAssignment.batch_id)
        )
        counts: dict[UUID, int] = {
            row[0]: int(row[1] or 0)
            for row in (await self.session.execute(counts_stmt)).all()
        }

        out: list[ExpeditionRow] = []
        for b in batches:
            assigned = counts.get(b.id, 0)
            cap = b.truck_capacity_units or 0
            if cap and assigned > cap:
                risk = "over_capacity"
            elif cap and assigned >= cap * 0.85:
                risk = "near_capacity"
            else:
                risk = "ok"
            out.append(
                ExpeditionRow(
                    batch_id=str(b.id),
                    code=b.code,
                    transport_date=b.transport_date,
                    truck_capacity_units=cap,
                    assigned_orders=assigned,
                    status=b.status,
                    destination=b.destination,
                    risk=risk,
                )
            )
        return out

    # ── First-pass yield ──────────────────────────────────────────────
    async def first_pass_yield(
        self,
        *,
        window_days: int = DEFAULT_FPY_WINDOW_DAYS,
    ) -> FPYResult:
        """Percentage of orders with zero rework events in the window.

        FPY = (orders_completed - orders_with_rework) / orders_completed × 100
        """
        since = datetime.now(timezone.utc).date() - timedelta(days=window_days)

        # Total completed orders in the window
        total_stmt = select(func.count(CuratedOrder.id)).where(
            and_(
                CuratedOrder.data_conclusao.is_not(None),
                CuratedOrder.data_conclusao >= since,
            )
        )
        total = int((await self.session.execute(total_stmt)).scalar_one() or 0)

        # Distinct of_ids with rework in the window
        rework_stmt = select(func.count(func.distinct(ReworkEntry.of_id))).where(
            and_(
                ReworkEntry.tenant_id == self.tenant_id,
                ReworkEntry.detected_at >= datetime.combine(
                    since, datetime.min.time(), tzinfo=timezone.utc,
                ),
            )
        )
        with_rework = int((await self.session.execute(rework_stmt)).scalar_one() or 0)

        # FPY can never go negative even if rework count > total (different windows
        # could have detected_at outside data_conclusao window for rare cases).
        clean = max(0, total - with_rework)
        fpy = (clean / total * 100.0) if total > 0 else 0.0

        return FPYResult(
            window_days=window_days,
            orders_total=total,
            orders_with_rework=min(with_rework, total),
            first_pass_yield_pct=fpy,
        )

    # ── Helpers ───────────────────────────────────────────────────────
    async def _resolve_unit_value_eur(self) -> float:
        """Resolve `cost.target.unit_value_eur` from TenantConfig.

        Sprint Q.8 Fase 5 — was a hardcoded `2350.0` in module scope.
        Now read from the config store with the same module constant
        as last-resort fallback (so config-store outages don't break
        the dashboard endpoint, they just preserve the previous value).
        """
        try:
            from src.core.services.tenant_config_service import TenantConfigService

            svc = TenantConfigService(self.session, self.tenant_id)
            cfg = await svc.get_category("cost")
            value = cfg.get("target.unit_value_eur")
            if value is not None:
                return float(value)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "backlog_by_client: cost.target.unit_value_eur load failed (%s) "
                "— using module default %.2f",
                exc,
                BACKLOG_DEFAULT_VALUE_EUR,
            )
        return BACKLOG_DEFAULT_VALUE_EUR
