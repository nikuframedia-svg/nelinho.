"""Value objects + KPI / risk computations for `FactoryMapService`.

Holds:
* `Availability` — soft presence flags for each source the snapshot reads.
* `RiskFlag` — risk record value object (Q.172: `boat_view` foi removido;
  mantido como value object exportado pela façade).
* `RiskFlagsMixin` — `kpis()` + its DB-backed fallbacks
  (`_defect_rate_from_db`, `_bottlenecks_from_db`,
  `_bottlenecks_from_orders`), `_throughput_eur_day`, `_trust_payload`,
  plus the shortage-risk and line-load aggregates that the snapshot
  consumes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.time import local_today

logger = logging.getLogger(__name__)


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
# Mixin
# ---------------------------------------------------------------------------


class RiskFlagsMixin:
    """KPI / risk / aggregate methods consumed by snapshot + API endpoints."""

    session: AsyncSession
    tenant_id: UUID
    _semantic: Any

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

        today = local_today()
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
        """Fração de ordens com ≥1 retrabalho — uma taxa de defeito 0..1.

        A versão anterior dividia o nº total de eventos de `rework_entry`
        pelo nº de ordens, o que dava números >1 sem sentido ("63 erros
        por ordem") — o `rework_entry` regista cada não-conformidade de
        checklist, não barcos defeituosos. A "taxa de defeito" do Painel
        tem de ser uma percentagem: ordens com pelo menos um retrabalho ÷
        total de ordens. `ReworkEntry.of_id` casa com
        `ProductionOrder.legacy_id` (o nº de OF).
        """
        try:
            from sqlalchemy import String as SAString, cast
            from src.plan.models.order import ProductionOrder
            from src.quality.models.rework import ReworkEntry

            total = int(
                (
                    await self.session.execute(
                        select(func.count(ProductionOrder.id)).where(
                            ProductionOrder.tenant_id == self.tenant_id
                        )
                    )
                ).scalar_one_or_none()
                or 0
            )
            if total <= 0:
                return None

            since = datetime.now(timezone.utc) - timedelta(days=window_days)
            known_ofs = select(cast(ProductionOrder.legacy_id, SAString)).where(
                ProductionOrder.tenant_id == self.tenant_id
            )
            with_rework = int(
                (
                    await self.session.execute(
                        select(
                            func.count(func.distinct(ReworkEntry.of_id))
                        ).where(
                            and_(
                                ReworkEntry.tenant_id == self.tenant_id,
                                ReworkEntry.detected_at >= since,
                                ReworkEntry.of_id.in_(known_ofs),
                            )
                        )
                    )
                ).scalar_one_or_none()
                or 0
            )
            return round(min(with_rework / total, 1.0), 3)
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
                # A camada curada está vazia nesta instalação — cai para a
                # distribuição real de WIP das ordens de produção.
                return await self._bottlenecks_from_orders(top_n=top_n)

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

    async def _bottlenecks_from_orders(
        self, *, top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Gargalos a partir do WIP real das ordens de produção.

        Quando a camada curada está vazia, o sinal honesto de gargalo é a
        distribuição de barcos a decorrer por fase: a fase com mais WIP é
        o gargalo visível. Agrupa `ProductionOrder` IN_PROGRESS por
        `current_phase_name`. O `score` é a contagem de barcos na fase.
        """
        try:
            from src.plan.models.order import OrderStatus, ProductionOrder

            stmt = (
                select(
                    ProductionOrder.current_phase_name,
                    func.count(ProductionOrder.id),
                )
                .where(
                    and_(
                        ProductionOrder.tenant_id == self.tenant_id,
                        ProductionOrder.status == OrderStatus.IN_PROGRESS,
                    )
                )
                .group_by(ProductionOrder.current_phase_name)
            )
            rows = (await self.session.execute(stmt)).all()
            if not rows:
                return []
            counts = [int(n or 0) for _, n in rows]
            busiest = max(counts) if counts else 0
            items = [
                {
                    "fase_id": None,
                    "fase_nome": phase or "Sem fase",
                    "open_phases": int(n or 0),
                    "wip_barcos": int(n or 0),
                    "score": int(n or 0),
                    "is_critical": busiest > 0 and int(n or 0) == busiest,
                }
                for phase, n in rows
            ]
            items.sort(key=lambda x: x["score"], reverse=True)
            return items[:top_n]
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "bottlenecks order fallback failed for tenant=%s: %r",
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
